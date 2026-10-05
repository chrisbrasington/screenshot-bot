#!/usr/bin/env python3
"""Steam screenshot lookup and download, with no Discord dependency.

The Steam Web API is the default path: one or two quick API calls plus CDN
image downloads. The Selenium scraper below is the slow but proven fallback,
used only when the API path fails.
"""
import os, logging
import time, urllib.parse
import subprocess, shutil
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

API_BASE = 'https://api.steampowered.com'
API_TIMEOUT = 10
IMAGE_TIMEOUT = 30
# IPublishedFileService file type for screenshots (5 returns workshop items)
SCREENSHOT_FILETYPE = 4

class FirefoxWebDriverSingleton:
    _instance = None
    _profile_dir = None

    def __init__(self):
        if not FirefoxWebDriverSingleton._instance:
            print("Creating new instance of Firefox WebDriver")
        else:
            print("Using existing instance of Firefox WebDriver")

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            options = Options()
            # options.add_argument('-headless')

            profile = FirefoxProfile()
            profile.set_preference("browser.cache.disk.enable", False)
            profile.set_preference("browser.cache.memory.enable", False)
            profile.set_preference("browser.cache.offline.enable", False)
            profile.set_preference("browser.privatebrowsing.autostart", True)

            # Create a temporary directory for the profile
            cls._profile_dir = profile.path

            cls._instance = webdriver.Firefox(options=options, firefox_profile=profile)
        return cls._instance

    @classmethod
    def quit(cls):
        if cls._instance:
            try:
                print('Quitting Firefox WebDriver instance')
                cls._instance.quit()
            except Exception as ex:
                print(f'Error quitting Firefox WebDriver: {ex}')
            finally:
                cls._instance = None
                time.sleep(5)
                cls.delete_temporary_folder()

    @classmethod
    def delete_temporary_folder(cls):
        if cls._profile_dir and os.path.exists(cls._profile_dir):
            try:
                print(f'Deleting temporary profile folder: {cls._profile_dir}')
                shutil.rmtree(cls._profile_dir)
            except Exception as ex:
                print(f'Error deleting {cls._profile_dir}, continuing')
                print(ex)
            finally:
                cls._profile_dir = None

def kill_firefox_processes():
    result = subprocess.run(["pkill", "-f", "firefox-esr"], capture_output=True, text=True)

    if result.returncode == 0:
        print("Firefox processes terminated.")
    elif result.returncode == 1:
        print("No matching Firefox processes found.")
    else:
        print(f"Error occurred while terminating Firefox processes: {result.stderr}")

# get steam url
def get_steam_url(username):
    try:
        steam_id = int(username)
        steam_url = f"https://steamcommunity.com/profiles/{steam_id}/screenshots/view=grid"
    except ValueError:
        steam_url = f"https://steamcommunity.com/id/{username}/screenshots/view=grid"

    return steam_url

# get steam screenshots
def get_steam_uploads(username, count=1):
    page_load_wait = 10  # max wait time for page load in seconds

    try:
        url = get_steam_url(username)
        print(url)

        browser = FirefoxWebDriverSingleton().get_instance()

        browser.get(url)

        WebDriverWait(browser, page_load_wait).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, 'profile_media_item'))
        )

        soup = BeautifulSoup(browser.page_source, 'html.parser')
        
        if not soup:
            logging.error('Failed to create BeautifulSoup object')
            return []

        profile_media_items = soup.find_all(attrs={'class': 'profile_media_item'})

        steam_data = []
        i = 0

        for item in profile_media_items:
            href = item.get('href')

            if not href:
                continue

            parsed_url = urllib.parse.urlparse(href)
            query_parameters = urllib.parse.parse_qs(parsed_url.query)
            id_value = query_parameters.get('id', None)

            if not id_value:
                id_value = 'unknown'
                print("ID not found in URL")

            # Check for spoiler within the profile_media_item
            spoiler = bool(item.find('div', class_='image_wall_spoiler_cover'))

            browser.get(href)
            detail_page_soup = BeautifulSoup(browser.page_source, "html.parser")
            actual_media_ctn = detail_page_soup.find(attrs={'class': 'actualmediactn'})
            image_link = actual_media_ctn.find('a').get('href')

            title = detail_page_soup.select_one('div.screenshotAppName > a').text
            print(f'{href} - {title}')

            a_tag = detail_page_soup.select_one('div.screenshotAppName > a')
            full_url = a_tag['href']
            
            # Remove '/screenshots/' from the URL
            base_url = full_url.rsplit('/screenshots/', 1)[0]
            print(base_url)

            steam_data.append({'id': id_value[0], 'img_urls': [image_link], 'timestamp': time.time(), 
                               'title': title, 'app_url': base_url, 'spoiler': spoiler})

            i += 1
            if i >= count:
                break

        return steam_data
    except Exception as e:
        print(e)
        return []

# resolve a vanity name or steamID64 to a steamID64
def resolve_steam_id(username, key):
    try:
        return str(int(username))
    except ValueError:
        pass

    start = time.time()
    response = requests.get(f'{API_BASE}/ISteamUser/ResolveVanityURL/v1/',
                            params={'key': key, 'vanityurl': username}, timeout=API_TIMEOUT)
    response.raise_for_status()
    result = response.json().get('response', {})

    if result.get('success') != 1:
        raise LookupError(f"could not resolve vanity name '{username}': {result.get('message', result)}")

    print(f"[api] resolved vanity '{username}' -> {result['steamid']} ({time.time() - start:.2f}s)")
    return result['steamid']

# get steam screenshots via the Steam Web API, newest first
def get_latest_via_api(username, count=1):
    key = os.environ.get('STEAM_API_KEY')
    if not key:
        raise RuntimeError('STEAM_API_KEY is not set')

    steam_id = resolve_steam_id(username, key)

    start = time.time()
    response = requests.get(f'{API_BASE}/IPublishedFileService/GetUserFiles/v1/',
                            params={'key': key, 'steamid': steam_id, 'appid': 0,
                                    'filetype': SCREENSHOT_FILETYPE, 'sortmethod': 'created',
                                    'numperpage': count, 'page': 1},
                            timeout=API_TIMEOUT)
    response.raise_for_status()
    result = response.json().get('response', {})
    files = result.get('publishedfiledetails') or []

    if not files:
        raise LookupError(f'no screenshots returned for {steam_id} (private profile?)')

    steam_data = []
    for item in files[:count]:
        if not item.get('file_url'):
            raise LookupError(f"screenshot {item.get('publishedfileid')} has no file_url")

        steam_data.append({'id': item['publishedfileid'], 'img_urls': [item['file_url']],
                           'timestamp': time.time(), 'title': item.get('app_name'),
                           'app_url': f"https://steamcommunity.com/app/{item.get('consumer_appid')}",
                           'spoiler': bool(item.get('spoiler_tag'))})

    newest = steam_data[0]
    print(f"[api] GetUserFiles: {result.get('total')} total, got {len(steam_data)}, "
          f"newest {newest['id']} {newest['title']} ({time.time() - start:.2f}s)")
    return steam_data

# download every image of every post, raising on any failure
def download_posts(posts):
    for post in posts:
        post['data'] = []
        for img_url in post['img_urls']:
            start = time.time()
            response = requests.get(img_url, timeout=IMAGE_TIMEOUT)
            if response.status_code != 200:
                raise IOError(f"image {post['id']} returned HTTP {response.status_code}")

            post['data'].append(response.content)
            print(f"[download] {post['id']} {len(response.content) // 1024} KB in {time.time() - start:.2f}s")
    return posts

# get screenshots with image bytes: API first, Selenium on any failure
def fetch_screenshots(username, count=1):
    start = time.time()
    print(f"[fetch] {count} screenshot(s) for '{username}'")

    try:
        posts = download_posts(get_latest_via_api(username, count))
        method = 'api'
    except Exception as e:
        print(f'[fallback] api failed: {e!r}; using browser')
        try:
            posts = download_posts(get_steam_uploads(username, count))
            method = 'browser'
        finally:
            FirefoxWebDriverSingleton.quit()

    print(f'[done] {len(posts)} image(s) via {method} in {time.time() - start:.2f}s')
    return posts, method
