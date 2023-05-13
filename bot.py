#!/usr/bin/env python3
import json, pickle, os, logging
import asyncio, aiohttp
import discord, requests
import time, sys, io, re, time, urllib.parse
import urllib.parse
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
import subprocess
from urllib.parse import urlparse, parse_qs, urlunparse
import glob, shutil
import datetime

# Configure Discord bot
bot = commands.Bot(
    command_prefix="/",
    case_insensitive=True,
    intents=discord.Intents.all())

# single instance of firefox webdriver
class FirefoxWebDriverSingleton:
    _instance = None

    def __init__(self):
        if not FirefoxWebDriverSingleton._instance:
            print("Creating new instance of Firefox WebDriver")
        else:
            print("Using existing instance of Firefox WebDriver")

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            options = Options()
            options.add_argument('-headless')

            # Create Firefox profile that deletes temporary files
            profile = FirefoxProfile()
            profile.set_preference("browser.cache.disk.enable", False)
            profile.set_preference("browser.cache.memory.enable", False)
            profile.set_preference("browser.cache.offline.enable", False)
            profile.set_preference("browser.privatebrowsing.autostart", True)

            # Create Firefox webdriver instance with the profile
            cls._instance = webdriver.Firefox(options=options,firefox_profile=profile)
        return cls._instance
    
    @classmethod
    def quit(cls):
        if cls._instance:
            print('Quitting Firefox WebDriver instance')
            cls._instance.service.stop()
            cls._instance.quit()
            cls._instance = None
            time.sleep(5)
            cls.delete_temporary_folder()

    @classmethod
    def delete_temporary_folder(cls):
        dir = '/tmp'
        try:
            print('Deleting temporary folder')
            if os.path.exists(dir):
                shutil.rmtree(dir)
        except Exception as ex:
            print('Error deleting /tmp, continuing')
            print(ex)
        
        if not os.path.exists(dir):
            os.makedirs(dir)

def kill_firefox_processes():
    result = subprocess.run(["pkill", "-f", "firefox-esr"], capture_output=True, text=True)

    if result.returncode == 0:
        print("Firefox processes terminated.")
    elif result.returncode == 1:
        print("No matching Firefox processes found.")
    else:
        print(f"Error occurred while terminating Firefox processes: {result.stderr}")

# get tweets
def get_tweets(username):
    global sleep_duration_seconds

    try:

        browser = FirefoxWebDriverSingleton().get_instance()

        print(f'reading tweets from @{username}...')

        url = f'https://mobile.twitter.com/{username}'
        browser.get(url)
        time.sleep(sleep_duration_seconds)  # wait for page load

        # parse html
        soup = BeautifulSoup(browser.page_source, 'html.parser')

        if not soup:
            logging.error('Failed to create BeautifulSoup object')
            return []

        # filter page elements for array of tweets
        tweets = soup.select('[data-testid="tweet"]')

        tweet_data = []

        # for each tweet
        for tweet in tweets:

            # if it's video, skip atm (haven't written downloader)
            is_video = tweet.select('[data-testid="videoComponent"]')

            if len(is_video) > 0:
                print('skipping video')
                continue

            # get metadata
            # tweet_id = tweet['aria-labelledby'].split()[0]
            img_urls = []
            for img in tweet.find_all('img'):
                if 'profile_images' not in img['src']:
                    img_url = img['src'].split('?')[0] + '?format=jpg&name=large'
                    img_urls.append(img_url)
                    print(img_url)

            timestamp_element = tweet.find('time')
            timestamp = None
            if timestamp_element:
                original_timestamp = timestamp_element['datetime']
                dt = datetime.datetime.strptime(original_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                truncated_timestamp = dt.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
                timestamp = truncated_timestamp
                
            tweet_id = timestamp

            # get tweet text
            text_element = tweet.select('[lang]')
            if text_element:
                tweet_text = text_element[0].text
            else:
                tweet_text = None

            print(f'tweet text: {tweet_text}')

            # append to array tweet information, mostly image url array and timestamp as unique identifier
            tweet_data.append({'id': tweet_id, 'img_urls': img_urls, 'timestamp': timestamp, 'title': tweet_text})

            break # only one

        return tweet_data
    except Exception as e:
        print(e)
        return []


# get steam screenshots
def get_steam_uploads(username):
    global sleep_duration_seconds

    try:
        browser = FirefoxWebDriverSingleton().get_instance()

        # with selenium, read from firefox headless
        url = f'https://steamcommunity.com/id/{username}/screenshots/?appid=0&sort=newestfirst&browsefilter=myfiles&view=grid'
        browser.get(url)
        time.sleep(sleep_duration_seconds) # wait for page load

        # parse html
        soup = BeautifulSoup(browser.page_source, 'html.parser')
        
        if not soup:
            logging.error('Failed to create BeautifulSoup object')
            return []

        # filter page elements for array of tweets
        profile_media_items = soup.find_all(attrs={'class': 'profile_media_item'})

        steam_data = []
        i = 0

        # print(f'steam screenshots: {len(profile_media_items)}')

        for item in profile_media_items:

            href = item.get('href')

            # Parse the URL to get the query string
            parsed_url = urllib.parse.urlparse(href)

            # Parse the query string to get the id parameter value
            query_parameters = urllib.parse.parse_qs(parsed_url.query)
            id_value = query_parameters.get('id', None)

            if not id_value:
                id_value = 'unknown'
                print("ID not found in URL")

            detail_page_response = browser.get(href)
            # time.sleep(sleep_duration_seconds)
            detail_page_soup = BeautifulSoup(browser.page_source, "html.parser")
            # Find the element with the class 'actualmediactn' and get the href attribute of the child 'a' tag
            actual_media_ctn = detail_page_soup.find(attrs={'class': 'actualmediactn'})
            image_link = actual_media_ctn.find('a').get('href')

            # print(detail_page_soup)
            # print(actual_media_ctn)
            # print(image_link)

            # Find the div element with class apphub_AppName and get its text
            title = detail_page_soup.find(attrs={'class': 'apphub_AppName'}).text
            print(title)

            steam_data.append({'id': id_value[0], 'img_urls': [image_link], 'timestamp': time.time(), 'title': title})

            # break
            i += 1
            # print(i)
            if i>= 1:
                break

        return steam_data
    except Exception as e:
        print(e)
        return []

# post image to discord
async def post_images(username, discord_user_id, channel_id, is_steam):
    global bot, processed_posts

    # search for upload discord channel
    channel = bot.get_channel(channel_id)
    # await channel.send('test')
    if not channel:
        print(f'Channel not found for ID: {channel_id}')

    # get tweets for single user (video skipped, not in resulting [])
    if is_steam:
        posts = get_steam_uploads(username)
    else:
        posts = get_tweets(username)

    # for each tweet
    for post in posts:

        # if first run, mark latest, do not re-upload to discord
        if(first_run):
            print('since pickle was created, this is the first run')
            print(f"first run, adding to processed: {post['id']}")
            processed_posts.add(post['id'])        
            continue

        # already processed
        if post['id'] in processed_posts:
            print(f"already processed: {post['id']}")
            continue

        # not already processed, add
        print(f'new: {post}')
        processed_posts.add(post['id'])

        # mention
        mention = f'<@{discord_user_id}>'

        first = True

        # for each image
        for img_url in post['img_urls']:

            print(img_url)

            # upload channel
            channel = bot.get_channel(channel_id)

            print('downloading...')

            # download image            
            try:
                response = requests.get(img_url)
                if response.status_code == 200:
                    
                    # send to discord channel
                    file = discord.File(io.BytesIO(response.content), filename="image.jpg")
                    if not first_run:

                        title = post['title']

                        from_msg = None

                        if first:
                            from_msg = f'From: {mention}'

                            if title is not None:
                                from_msg += f' playing {title}'

                        if from_msg is not None:
                            await channel.send(from_msg, file=file)
                        else:
                            await channel.send(file=file)

                        first = False
                    else:
                        if is_steam:
                            print('first run, setting latest of steam..')
                        else:
                            print('first run, setting latest of twitter..')
            except Exception as e:
                # handle the exception gracefully
                print("An exception occurred:", e)         

            print('sent to discord...')

# check twitter once
async def check_twitter():
    global first_run

    # for each user in config
    for user in twitter_config["users"]:
        print('~~~~~~~')
        print('checking twitter... ', end='')
        print(user)
        username = user["twitter_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = twitter_config['channel_id']

        await post_images(username, discord_user_id, channel_id, False)
    print('done.')

# check steam once
async def check_steam():
    global first_run

    # for each user in config
    for user in steam_config["users"]:
        print('~~~~~~~')
        print('checking steam... ', end='')
        print(user)
        username = user["steam_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = twitter_config['channel_id']

        await post_images(username, discord_user_id, channel_id, True)
    print('done.')

# bot on ready
@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online)
    print(f'Logged in as {bot.user.name}')

    try:
        await check_twitter()
    except RuntimeError as e:
        print('already running twitter task')
    except Exception as e:
        print(e)
    try:
        await check_steam()
    except RuntimeError as e:
        print('already running steam task')
    except Exception as e:
        print(e)

    save_processed_posts(processed_posts, pickle_path)

    print('quitting firefox')
    FirefoxWebDriverSingleton.quit()

    # kill firefox processes
    kill_firefox_processes()

    print('stopping bot')
    # bye bye bot
    await bot.close()

# Save the set to a file
def save_processed_posts(processed_posts, file_path):
    print('saving processed posts set')
    with open(file_path, 'wb') as file:
        pickle.dump(processed_posts, file)

# Load the set from a file
def load_processed_posts(file_path):
    try:
        with open(file_path, 'rb') as file:
            return pickle.load(file)
    except FileNotFoundError:
        return set()

# processed posts (steam images / tweets)
pickle_path = 'processed_posts.pickle'

first_run = True

# Check if the file exists, otherwise use an empty set
if os.path.exists(pickle_path):
    first_run = False
    print('subsequent run, existing pickle - loading processed posts set')
    print('anything found will be added to the pickle (and discord)')
    processed_posts = load_processed_posts(pickle_path)
else:
    print('first run, new pickle - creating processed posts set')
    processed_posts = set()

sleep_duration_seconds = 20

# configs for paring twitter/discord users
with open("config-twitter.json") as config_file:
    twitter_config = json.load(config_file)

# configs for paring steam/discord users
with open("config-steam.json") as config_file:
    steam_config = json.load(config_file)

bot.run(twitter_config['discord_token'])