#!/usr/bin/env python3
import json
import asyncio
import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

print('running...')

with open("config.json") as config_file:
    config = json.load(config_file)

# Configure Discord bot
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
bot = commands.Bot(command_prefix="!", intents=intents)

first_run = True

def get_tweets(username):
    print(f'getting tweets from @{username}')
    options = Options()
    # options.add_argument('-headless')
    browser = webdriver.Firefox(options=options)
    url = f'https://mobile.twitter.com/{username}'
    print(url)
    browser.get(url)
    soup = BeautifulSoup(browser.page_source, 'html.parser')
    browser.quit()

    print('soup...........')

    tweets = soup.find_all('div', attrs={'data-testid': 'tweet'})

    print(tweets)

    tweet_data = []
    for tweet in tweets:
        tweet_id = tweet['data-tweet-id']
        img_urls = [img['src'] for img in tweet.find_all('img') if 'profile_images' not in img['src']]
        tweet_data.append({'id': tweet_id, 'img_urls': img_urls})

    return tweet_data

async def post_images(username, discord_user_id, channel_id, last_tweet_id):
    global first_run

    tweets = get_tweets(username)
    new_last_tweet_id = last_tweet_id

    print(tweets)

    for tweet in tweets:
        print(tweet)
        if tweet['id'] == last_tweet_id:
            break

        new_last_tweet_id = max(new_last_tweet_id, tweet['id'])
        mention = f'<@{discord_user_id}>'

        for img_url in tweet['img_urls']:
            channel = bot.get_channel(channel_id)
            if not first_run:
                await channel.send(f'{mention}\n{img_url}')

    return new_last_tweet_id

@tasks.loop(minutes=5)
async def check_twitter():
    global first_run
    print('checking twitter...', end='')
    for user in config["users"]:
        print(user)
        username = user["twitter_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = 1043730244747677857
        last_tweet_id_key = f'{username}_last_tweet_id'

        last_tweet_id = bot.get_cog('Data').data.get(last_tweet_id_key, '0')
        new_last_tweet_id = None

        new_last_tweet_id = await post_images(username, discord_user_id, channel_id, last_tweet_id)

        if new_last_tweet_id is None or new_last_tweet_id != last_tweet_id:
            bot.get_cog('Data').data[last_tweet_id_key] = new_last_tweet_id

    first_run = False

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