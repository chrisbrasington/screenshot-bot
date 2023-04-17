#!/usr/bin/env python3
import json
import asyncio, aiohttp
import discord, requests
import time, sys, io, re, time, urllib.parse
import urllib.parse
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

# processed posts (steam images / tweets)
processed_posts = set()

# first run
first_run_twitter = True
first_run_steam = True

# configs for paring twitter/discord users
with open("config-twitter.json") as config_file:
    twitter_config = json.load(config_file)

# configs for paring steam/discord users
with open("config-steam.json") as config_file:
    steam_config = json.load(config_file)

# Configure Discord bot
bot = commands.Bot(
    command_prefix="/",
    case_insensitive=True,
    intents=discord.Intents.all())

# get tweets
def get_tweets(username):

    try:
        print(f'reading tweets from @{username}...')

        # with selenium, read from firefox headless
        options = Options()
        options.add_argument('-headless')
        browser = webdriver.Firefox(options=options)
        url = f'https://mobile.twitter.com/{username}'
        browser.get(url)
        time.sleep(5)  # Add a 5-second wait for page load

        # parse html
        soup = BeautifulSoup(browser.page_source, 'html.parser')
        browser.quit()

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
            img_urls = [img['src'] for img in tweet.find_all('img') if 'profile_images' not in img['src']]
            timestamp_element = tweet.find('time')
            timestamp = None
            if timestamp_element:
                timestamp = timestamp_element['datetime']
                
            tweet_id = timestamp

            # append to array tweet information, mostly image url array and timestamp as unique identifier
            tweet_data.append({'id': tweet_id, 'img_urls': img_urls, 'timestamp': timestamp})

            break # only one

        return tweet_data
    except Exception as e:
        print(e)
        return []

def get_steam_uploads(username):

    try:

        # with selenium, read from firefox headless
        options = Options()
        options.add_argument('-headless')
        browser = webdriver.Firefox(options=options)
        url = f'https://steamcommunity.com/id/{username}/screenshots/?appid=0&sort=newestfirst&browsefilter=myfiles&view=grid'
        browser.get(url)
        time.sleep(5)  # Add a 5-second wait for page load

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
            # time.sleep(5)
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

        browser.quit()
        return steam_data
    except Exception as e:
        print(e)
        return []

# post image to discord
async def post_images(username, discord_user_id, channel_id, is_steam = False):
    global bot, first_run_twitter, first_run_steam, processed_posts

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
        if (first_run_twitter and not is_steam) or (first_run_steam and is_steam):
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
                    if (not is_steam and not first_run_twitter) or (is_steam and not first_run_steam):

                        title = post['title']

                        if title is not None:
                            await channel.send(f'From: {mention} playing {title}', file=file)
                        else:
                            await channel.send(f'From: {mention}', file=file)
                    else:
                        if is_steam:
                            print('first run, setting latest of steam..')
                        else:
                            print('first run, setting latest of twitter..')
            except Exception as e:
                # handle the exception gracefully
                print("An exception occurred:", e)         

            print('sent to discord...')

# check twitter on timer loop
@tasks.loop(seconds=60)
async def check_twitter():
    global first_run_twitter

    # for each user in config
    for user in twitter_config["users"]:
        print('~~~~~~~')
        print('checking twitter... ', end='')
        print(user)
        username = user["twitter_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = twitter_config['channel_id']

        await post_images(username, discord_user_id, channel_id, False)
    first_run_twitter = False
    print('done.')

@tasks.loop(seconds=60)
async def check_steam():
    global first_run_steam

    # for each user in config
    for user in steam_config["users"]:
        print('~~~~~~~')
        print('checking steam... ', end='')
        print(user)
        username = user["steam_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = twitter_config['channel_id']

        await post_images(username, discord_user_id, channel_id, True)
    first_run_steam = False
    print('done.')

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online)
    print(f'Logged in as {bot.user.name}')
    try:
        check_twitter.start()
    except RuntimeError as e:
        print('already running twitter task')
    except Exception as e:
        print(e)
    try:
        check_steam.start()
    except RuntimeError as e:
        print('already running steam task')
    except Exception as e:
        print(e)

bot.run(twitter_config['discord_token'])