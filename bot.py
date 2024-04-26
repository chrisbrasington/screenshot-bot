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
        # intents.members = True
        # intents.message_content = True
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

            # only if clear is needed
            # tree.clear_commands(guild = guild)
            await tree.sync(guild = guild)
            commands = await tree.fetch_commands(guild = guild)

            # print commands
            for command in commands:
                print(f'Command: {command.name}')

            print('Ready')        

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

def get_steam_url(username):
    """
    Generate the Steam URL for accessing screenshots based on the provided username or Steam ID.
    
    Args:
    - username (str): The username or Steam ID
    
    Returns:
    - str: The generated Steam URL
    """
    try:
        # Try converting the username to an integer (Steam ID)
        steam_id = int(username)
        # If successful, construct URL with Steam ID
        steam_url = f"https://steamcommunity.com/profiles/{steam_id}/screenshots/view=grid"
    except ValueError:
        # If conversion fails, assume it's a custom username
        steam_url = f"https://steamcommunity.com/id/{username}/screenshots/view=grid"
    
    return steam_url


# get steam screenshots
def get_steam_uploads(username):
    page_load_wait = 0

    try:
        url = get_steam_url(username)
        print(url)

        browser = FirefoxWebDriverSingleton().get_instance()

        # with selenium, read from firefox headless

        browser.get(url)
        time.sleep(page_load_wait) # wait for page load

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
async def post_images(username, interaction, testing = False):
    global bot, processed_posts

    await interaction.response.send_message(content='Loading...')

    channel = bot.get_channel(interaction.channel_id) 
    mention = interaction.user.mention

    posts = get_steam_uploads(username)

    # for each steam images
    for post in posts:

        # for each image
        for img_url in post['img_urls']:

            print(f'Downloading... {img_url}')

            # download image            
            try:
                response = requests.get(img_url)
                if response.status_code == 200:
                    
                    # send to discord channel
                    file = discord.File(io.BytesIO(response.content), filename="image.jpg")
                    
                    title = post['title']

                    from_msg = f'{mention}'

                    if testing:
                        from_msg = f' testing steam id ({username})'

                    if title is not None:
                        from_msg += f' playing {title}'

                    print('Responding...')
                    print(from_msg)

                    message = await interaction.original_response()          

                    if from_msg is not None:
                        # 
                        await message.edit(content=from_msg, attachments=[file])
                        # await channel.send(from_msg, file=file)
                    else:
                        await channel.send(file=file)
                    
            except Exception as e:
                # handle the exception gracefully
                error = f'An exception occurred: {e}'
                print(error)
                await message.edit(content=error)   

            print('Done.')

# check steam once
async def check_steam():
    global first_run

    # for each user in config
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

    # processed posts (steam images / tweets)
    pickle_path = 'data/state.pickle'

    state = {}

    if os.path.exists(pickle_path):
        print('Loaded saved state')
        state = pickle.load(open(pickle_path, 'rb'))
        print(state)
    else:
        print('no saved state found')

    # configs for paring steam/discord users
    with open("config-steam.json") as config_file:
        steam_config = json.load(config_file)

    guild_id = steam_config['guild_id']
    guild = discord.Object(id = guild_id)

    return bot, tree, guild, steam_config['discord_token'], state

bot, tree, guild, token, state = setup()

@tree.command(guild=guild, description='Register steam id')
async def register(interaction, steam: str):
    if interaction.user.id in state:
        # remove dictionary entry
        del state[interaction.user.id]

    # add key interaction.user.id, value steam
    state[interaction.user.id] = steam

    # save pickle 
    with open('data/state.pickle', 'wb') as f:
        pickle.dump(state, f)

    response = f'Registered steam id: {steam} to {interaction.user.mention}'
    response += f'\n{get_steam_url(steam)}'
    await interaction.response.send_message(response)

@tree.command(guild=guild, description='steam screenshots')
async def screenshot(interaction):

    # if interaction.user.id in state
    if interaction.user.id in state:

        steam_id = state[interaction.user.id]
        
        await post_images(steam_id, interaction)
        
        return
    else:
        # register steam id with register command
        await interaction.response.send_message(f'Register steam id with /register command')

@tree.command(guild=guild, description='Test any steam id')
async def test(interaction, steam: str):
    await post_images(steam, interaction, True)

@tree.command(guild=guild, description='Get help and learn about available commands.')
async def help(interaction):
    """
    Get help and learn about available commands.
    """

    help_message = """Hi, I'm screenshot-bot!
    
I allow you to register your Steam ID to access your Steam screenshots directly within Discord.

Here are the available commands:

/register [your_steam_id] - Register your Steam ID. Integer guarenteed to work, some usernames work.
/screenshot - View your registered Steam screenshots. Use this command to get a link to your latest Steam screenshot.
/help - Get help and learn about available commands.

Example usage:
/register 1234567890
/register raylinth
/screenshot
/help

For further assistance, feel free to contact the bot developer.
"""
    await interaction.response.send_message(help_message)



bot.run(token)