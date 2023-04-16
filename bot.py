#!/usr/bin/env python3
import json
import asyncio
import discord, requests
import time, sys, io
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

with open("config.json") as config_file:
    config = json.load(config_file)

# Configure Discord bot
bot = commands.Bot(
    command_prefix="/",
    case_insensitive=True,
    intents=discord.Intents.all())

def get_tweets(username):
    print(f'reading tweets from @{username}...')
    options = Options()
    options.add_argument('-headless')
    browser = webdriver.Firefox(options=options)
    url = f'https://mobile.twitter.com/{username}'
    browser.get(url)
    time.sleep(5)  # Add a 5-second wait
    soup = BeautifulSoup(browser.page_source, 'html.parser')
    browser.quit()

    if not soup:
        logging.error('Failed to create BeautifulSoup object')
        return []

    tweets = soup.select('[data-testid="tweet"]')

    tweet_data = []
    for tweet in tweets:
        tweet_id = tweet['aria-labelledby'].split()[0]
        img_urls = [img['src'] for img in tweet.find_all('img') if 'profile_images' not in img['src']]
        timestamp_element = tweet.find('time')
        if timestamp_element:
            timestamp = timestamp_element['datetime']
        else:
            timestamp = None
        tweet_data.append({'id': tweet_id, 'img_urls': img_urls, 'timestamp': timestamp})

    return tweet_data

async def post_images(username, discord_user_id, channel_id, last_tweet_id):
    global bot
    channel = bot.get_channel(channel_id)
    if channel:
        print(f'Channel found: {channel.name}')
    else:
        print(f'Channel not found for ID: {channel_id}')

    first_run = last_tweet_id == '0'

    tweets = get_tweets(username)
    new_last_tweet_id = last_tweet_id

    for tweet in tweets:
        print(tweet)
        if tweet['id'] == last_tweet_id:
            break

        new_last_tweet_id = max(new_last_tweet_id, tweet['id'])
        print(new_last_tweet_id)
        mention = f'<@{discord_user_id}>'

        for img_url in tweet['img_urls']:
            channel = bot.get_channel(channel_id)
            response = requests.get(img_url)
            if response.status_code == 200:
                
                file = discord.File(io.BytesIO(response.content), filename="image.jpg")
                if not first_run:
                    await channel.send(f'From: {mention}', file=file)
                else:
                    print('first run, setting latest..')

        break

    return new_last_tweet_id

@tasks.loop(seconds=20)
async def check_twitter():
    print('checking twitter... ', end='')
    for user in config["users"]:
        print(user)
        username = user["twitter_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = config['channel_id']
        last_tweet_id_key = f'{username}_last_tweet_id'

        last_tweet_id = bot.get_cog('Data').data.get(last_tweet_id_key, '0')
        new_last_tweet_id = None

        new_last_tweet_id = await post_images(username, discord_user_id, channel_id, last_tweet_id)

        if new_last_tweet_id is None or new_last_tweet_id != last_tweet_id:
            bot.get_cog('Data').data[last_tweet_id_key] = new_last_tweet_id

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    check_twitter.start()

class Data(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = {}

bot.add_cog(Data(bot))
bot.run(config['discord_token'])
