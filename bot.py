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

processed_tweets = set()

first_run = True

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

async def post_images(username, discord_user_id, channel_id):
    global bot, first_run, processed_tweets
    channel = bot.get_channel(channel_id)
    if channel:
        print(f'Channel found: {channel.name}')
    else:
        print(f'Channel not found for ID: {channel_id}')

    tweets = get_tweets(username)

    for tweet in tweets:

        if first_run:
            print(f"first run, adding to processed: {tweet['timestamp']}")
            processed_tweets.add(tweet['timestamp'])        
            continue

        if tweet['timestamp'] in processed_tweets:
            print(f"already processed: {tweet['timestamp']}")
            continue

        print(f'new: {tweet}')
        processed_tweets.add(tweet['id'])

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

    first_run = False

@tasks.loop(seconds=20)
async def check_twitter():
    global first_run
    print('checking twitter... ', end='')
    for user in config["users"]:
        print(user)
        username = user["twitter_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = config['channel_id']

        await post_images(username, discord_user_id, channel_id)
    print('done.')

@bot.event
async def on_ready():
    global first_run 
    print(f'Logged in as {bot.user.name}')
    check_twitter.start()

bot.run(config['discord_token'])
