#!/usr/bin/env python3
import json, pickle, os, logging
import asyncio, aiohttp
import discord, requests
import time, sys, io, re, time, urllib.parse
import urllib.parse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
import subprocess
from urllib.parse import urlparse, parse_qs, urlunparse
import glob, shutil
import datetime
from discord import app_commands

# Configure Discord bot
class bot_client(discord.Client):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        self.synced = False

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')

        await self.wait_until_ready()
        if not self.synced:
            with open("config-steam.json") as config_file:
                steam_config = json.load(config_file)

            guild = self.get_guild(steam_config['guild_id'])

            print(f'Syncing commands to {guild.name}...')

            await tree.sync(guild=guild)
            commands = await tree.fetch_commands(guild=guild)

            for command in commands:
                print(f'Command: {command.name}')

            print('Ready')

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
    page_load_wait = 0

    try:
        url = get_steam_url(username)
        print(url)

        browser = FirefoxWebDriverSingleton().get_instance()

        browser.get(url)
        time.sleep(page_load_wait)

        soup = BeautifulSoup(browser.page_source, 'html.parser')
        
        if not soup:
            logging.error('Failed to create BeautifulSoup object')
            return []

        profile_media_items = soup.find_all(attrs={'class': 'profile_media_item'})

        steam_data = []
        i = 0

        for item in profile_media_items:
            href = item.get('href')

            parsed_url = urllib.parse.urlparse(href)
            query_parameters = urllib.parse.parse_qs(parsed_url.query)
            id_value = query_parameters.get('id', None)

            if not id_value:
                id_value = 'unknown'
                print("ID not found in URL")

            
            detail_page_response = browser.get(href)
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
                               'title': title, 'app_url': base_url})

            i += 1
            if i >= count:
                break

        return steam_data
    except Exception as e:
        print(e)
        return []

# post image to discord
async def post_images(username, interaction, count=1, testing=False):
    global bot, processed_posts

    await interaction.response.send_message(content='Loading...')

    mention = interaction.user.mention
    posts = get_steam_uploads(username, count)
    attachments = []
    titles = set()
    apps = set()

    for post in posts:
        for img_url in post['img_urls']:
            print(f'Downloading... {img_url}')

            try:
                response = requests.get(img_url)
                if response.status_code == 200:
                    file = discord.File(io.BytesIO(response.content), filename="image.jpg")
                    attachments.append(file)

                    title = post['title']
                    if title and title not in titles:
                        titles.add(title)
                        apps.add(f"[{title}]({post['app_url']})")

            except Exception as e:
                error = f'An exception occurred: {e}'
                print(error)
                await interaction.followup.send(content=error)
                return

    if attachments:
        print('Responding...')

        # Reverse the order of attachments
        attachments.reverse()

        # Create the from_msg string
        title_list = list(titles)
        print(title_list)
        title_msg = " and ".join(title_list)

        if testing:
            print('Testing...')
            from_msg = f'{title_msg}' if title_msg else mention
        else:
            from_msg = f'{mention} playing {title_msg}' if title_msg else mention

        print(from_msg)
        # title=f"Steam Screenshots"
        embed = discord.Embed(description=f"From {', '.join(apps)}")

        message = await interaction.original_response()
        await message.edit(content=from_msg, attachments=attachments, embed=embed)
        print('Done.')
    else:
        await interaction.followup.send(content='No images found.')

    # Quit the Firefox WebDriver instance
    FirefoxWebDriverSingleton.quit()


# check steam once
async def check_steam():
    global first_run

    for user in steam_config["users"]:
        print('~~~~~~~')
        print('checking steam... ', end='')
        print(user)
        username = user["steam_username"]
        channel_id = twitter_config['channel_id']

        await post_images(username, channel_id, True)
    print('done.')

def setup():
    global bot, tree, state

    bot = bot_client()
    tree = app_commands.CommandTree(bot)

    pickle_path = 'data/state.pickle'

    state = {}

    if os.path.exists(pickle_path):
        print('Loaded saved state')
        state = pickle.load(open(pickle_path, 'rb'))
        print(state)
    else:
        print('no saved state found')

    with open("config-steam.json") as config_file:
        steam_config = json.load(config_file)

    guild_id = steam_config['guild_id']
    guild = discord.Object(id=guild_id)

    return bot, tree, guild, steam_config['discord_token'], state

bot, tree, guild, token, state = setup()

@tree.command(guild=guild, description='Register steam id')
async def register(interaction, steam: str):
    if interaction.user.id in state:
        del state[interaction.user.id]

    state[interaction.user.id] = steam

    with open('data/state.pickle', 'wb') as f:
        pickle.dump(state, f)

    response = f'Registered steam id: {steam} to {interaction.user.mention}'
    response += f'\n{get_steam_url(steam)}'
    await interaction.response.send_message(response)

@tree.command(guild=guild, description='steam screenshots')
async def screenshot(interaction):
    if interaction.user.id in state:
        steam_id = state[interaction.user.id]
        await post_images(steam_id, interaction)
        return
    else:
        await interaction.response.send_message(f'Register steam id with /register command')

@tree.command(guild=guild, description='Test any steam id')
async def test(interaction, steam: str):
    await post_images(steam, interaction, 1, True)

@tree.command(guild=guild, description='Get help and learn about available commands.')
async def help(interaction):
    help_message = """Hi, I'm screenshot-bot!
    
I allow you to register your Steam ID to access your Steam screenshots directly within Discord.

Here are the available commands:

/register [steamID64] - Lookup your steamID64: https://steamid.io
/register [custom_url] - If you go to your steam edit profile and set a custom URL, you can use that instead of your steamID64
/screenshot - View your registered Steam screenshots. Use this command to get a link to your latest Steam screenshot.
/multiple [number] - View the specified number of your registered Steam screenshots.
/help - Get help and learn about available commands.

Example usage:
/register steamID64
/screenshot
/multiple 3
/help
"""
    await interaction.response.send_message(help_message)

@tree.command(guild=guild, description='Get multiple steam screenshots')
async def multiple(interaction, number: int):
    if number > 10:
        await interaction.response.send_message(f'The maximum number of screenshots you can request is 10.')
        return

    if interaction.user.id in state:
        steam_id = state[interaction.user.id]
        await post_images(steam_id, interaction, count=number)
        return
    else:
        await interaction.response.send_message(f'Register steam id with /register command')

bot.run(token)