#!/usr/bin/env python3
import pickle, os, logging
import asyncio, aiohttp
import discord, requests
import time, sys, io, re, urllib.parse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import glob, shutil
import datetime
from discord import app_commands
from steam_download import FirefoxWebDriverSingleton, get_steam_url, fetch_screenshots

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
            guild = self.get_guild(int(os.environ['GUILD_ID']))

            print(f'Syncing commands to {guild.name}...')

            await tree.sync(guild=guild)

            await tree.sync(guild=None)

            commands = await tree.fetch_commands(guild=guild)

            for command in commands:
                print(f'Command: {command.name}')

            print('Ready')

# post image to discord
async def post_images(username, interaction, count=1, testing=False, comment='', reverse=False):
    global bot, processed_posts, last_message

    # do opposite interpretation (reverse by default), aka chronilogical order
    reverse = not bool(reverse)

    await interaction.response.defer(ephemeral=True, thinking=True)

    mention = interaction.user.mention

    try:
        loop = asyncio.get_running_loop()
        posts, method = await loop.run_in_executor(None, fetch_screenshots, username, count)
    except Exception as e:
        error = f'An exception occurred: {e}'
        print(error)
        await interaction.followup.send(content=error, ephemeral=True)
        return

    attachments = []
    titles = set()
    apps = set()

    for post in posts:
        for data in post['data']:
            file = discord.File(io.BytesIO(data), filename="image.jpg", spoiler=post.get('spoiler', False))
            attachments.append(file)

            title = post['title']
            if title and title not in titles:
                titles.add(title)
                apps.add(f"[{title}]({post['app_url']})")

    if attachments:
        print('Responding...')

        # Reverse the order of attachments
        if reverse:
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

        # print comment to console
        print('Comment:', comment)

        if(not testing and comment != ''):
            from_msg = f'> {comment}\n says {mention} while playing {title_msg}' 

        print(from_msg)
        # title=f"Steam Screenshots"
        embed = discord.Embed(description=f"{', '.join(apps)}")

        last_message = await interaction.channel.send(content=from_msg, files=attachments, embed=embed)
        await interaction.delete_original_response()
        print('Done.')
    else:
        await interaction.followup.send(content='No images found.', ephemeral=True)

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

    guild_id = int(os.environ['GUILD_ID'])
    guild = discord.Object(id=guild_id)

    return bot, tree, guild, os.environ['DISCORD_TOKEN'], state

bot, tree, guild, token, state = setup()

# last screenshot message posted, for /undo
last_message = None

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
async def screenshot(interaction, comment: str = ''):
    if interaction.user.id in state:
        steam_id = state[interaction.user.id]
        await post_images(steam_id, interaction, 1, False, comment=comment)
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
/screenshot [comment: optional] - View your registered Steam screenshots. Use this command to get a link to your latest Steam screenshot. Optional comment.
/multiple [number] - View the specified number of your registered Steam screenshots.
/get [url] - Get a single Steam screenshot from a Steam Community URL.
/delete [message_id] - Delete one of my messages in this channel.
/undo - Delete the last screenshot message I posted.
/help - Get help and learn about available commands.

Example usage:
/register steamID64
/screenshot
/multiple 3
/help
"""
    await interaction.response.send_message(help_message)

@tree.command(guild=guild, description='Get multiple steam screenshots')
async def multiple(interaction, number: int, reverse: bool = False):
    if number > 10:
        await interaction.response.send_message(f'The maximum number of screenshots you can request is 10.')
        return

    if interaction.user.id in state:
        steam_id = state[interaction.user.id]
        await post_images(steam_id, interaction, count=number, testing=False, comment='', reverse=reverse)

        return
    else:
        await interaction.response.send_message(f'Register steam id with /register command')

@tree.command(guild=guild, description='Show your registered Steam profile')
async def whoami(interaction):
    if interaction.user.id in state:
        steam_id = state[interaction.user.id]
        steam_url = get_steam_url(steam_id)
        response = f'Your registered Steam profile: {steam_url}'
    else:
        response = f'You have not registered a Steam ID. Use `/register [steamID64 or custom URL]` to register your Steam ID.'

    await interaction.response.send_message(response)

@tree.command(guild=guild, description='Delete a bot message by ID')
async def delete(interaction, message_id: str):
    try:
        message_id = int(message_id)
    except ValueError:
        await interaction.response.send_message('Invalid message ID.', ephemeral=True)
        return

    try:
        message = await interaction.channel.fetch_message(message_id)
    except discord.NotFound:
        await interaction.response.send_message('Message not found in this channel.', ephemeral=True)
        return

    if message.author.id != bot.user.id:
        await interaction.response.send_message('I can only delete my own messages.', ephemeral=True)
        return

    await message.delete()
    print(f'Deleted message {message_id} for {interaction.user}')
    await interaction.response.send_message('Message deleted.', ephemeral=True)

@tree.command(guild=guild, description='Delete the last screenshot message posted')
async def undo(interaction):
    global last_message

    if last_message is None:
        await interaction.response.send_message('Nothing to undo.', ephemeral=True)
        return

    message, last_message = last_message, None

    try:
        await message.delete()
    except discord.NotFound:
        await interaction.response.send_message('That message was already deleted.', ephemeral=True)
        return

    print(f'Undo: deleted message {message.id} for {interaction.user}')
    await interaction.response.send_message('Last message deleted.', ephemeral=True)

@tree.command(guild=guild, description='Get a single Steam screenshot from URL')
async def get(interaction, url: str):
    if 'steamcommunity.com' not in url:
        await interaction.response.send_message('Invalid URL. Please provide a valid Steam Community URL.')
        return
    
    # loading..
    await interaction.response.send_message('Loading...')

    try:
        browser = FirefoxWebDriverSingleton().get_instance()
        browser.get(url)

        # Wait for the breadcrumbs to load
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'breadcrumbs'))
        )

        soup = BeautifulSoup(browser.page_source, 'html.parser')
        breadcrumbs = soup.find('div', class_='breadcrumbs')
        if not breadcrumbs:
            await interaction.response.send_message('Failed to find breadcrumbs on the provided URL.')
            return

        # Extract username and game title from breadcrumbs
        username = breadcrumbs.find_all('a')[-1].text.strip()
        # remove "'s Screenshots" from the username
        username = re.sub(r"'s Screenshots", "", username)

        game_title = breadcrumbs.find_all('a')[-3].text.strip()

        # Fetch the image URL
        actual_media_ctn = soup.find('div', class_='actualmediactn')
        if not actual_media_ctn:
            await interaction.response.send_message('Failed to find image on the provided URL.')
            return

        img_tag = actual_media_ctn.find('img', class_='screenshotEnlargeable')
        if not img_tag:
            await interaction.response.send_message('Failed to find image tag on the provided URL.')
            return

        img_url = img_tag['src']

        response = requests.get(img_url)
        if response.status_code == 200:
            file = discord.File(io.BytesIO(response.content), filename="image.jpg")
            embed = discord.Embed()
            embed.set_image(url=f"attachment://image.jpg")

            message = await interaction.original_response()
            
            await message.edit(content=f"{username} playing {game_title}", attachments=[file], embed=embed)
        else:
            await interaction.response.send_message('Failed to fetch image from the provided URL.')
    except Exception as e:
        await interaction.response.send_message(f'An error occurred: {str(e)}')
    finally:
        FirefoxWebDriverSingleton.quit()

bot.run(token)
