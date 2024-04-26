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

# get steam screenshots
def get_steam_uploads(username):
    global sleep_duration_seconds

    try:
        browser = FirefoxWebDriverSingleton().get_instance()

        # with selenium, read from firefox headless
        url = f'https://steamcommunity.com/id/{username}/screenshots/?appid=0&sort=newestfirst&browsefilter=myfiles&view=grid'
        
        console.log(url)

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
async def post_images(username, discord_user_id, channel):
    global bot, processed_posts

    # # search for upload discord channel
    # channel = bot.get_channel(channel_id)
    # # await channel.send('test')
    # if not channel:
    #     print(f'Channel not found for ID: {channel_id}')

    posts = get_steam_uploads(username)

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

def setup():
    global bot, tree, state

    bot = bot_client()
    tree = app_commands.CommandTree(bot)

    # processed posts (steam images / tweets)
    pickle_path = 'state.pickle'

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
    with open('state.pickle', 'wb') as f:
        pickle.dump(state, f)

    await interaction.response.send_message(f'Registered steam id: {steam} to {interaction.user.mention}')

@tree.command(guild=guild, description='steam screenshots')
async def screenshot(interaction):

    # if interaction.user.id in state
    if interaction.user.id in state:

        steam_id = state[interaction.user.id]
        
        await post_images(steam_id, interaction.user.id, interaction.channel_id)
        
        return
    else:
        # register steam id with register command
        await interaction.response.send_message(f'Register steam id with /register command')


@tree.command(guild = guild, description='Check bot status')
async def test(interaction):
    await interaction.response.send_message('Test successful!')

bot.run(token)