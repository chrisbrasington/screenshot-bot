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

# processed tweets
processed_tweets = set()
processed_steam = set()

# first run
first_run = True

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

def get_steam_uploads(username):

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

    for item in profile_media_items:

        # print(item)
        href = item.get('href')
        # print(href)

        # # Load the page from the href attribute
        # detail_page_response = browser.get(href)
        # time.sleep(5)
        # print(detail_page_response)
        # detail_page_soup = BeautifulSoup(detail_page_response.page_source, "html.parser")

        # # Find the element with the class 'actualmediactn' and get the href attribute of the child 'a' tag
        # actual_media_ctn = detail_page_soup.find(attrs={'class': 'actualmediactn'})
        # image_link = actual_media_ctn.find('a').get('href')

        # print(detail_page_soup)
        # print(actual_media_ctn)
        # print(image_link)


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


        steam_data.append({'id': id_value[0], 'img_urls': [image_link], 'timestamp': time.time()})
            




        
        ###################
        # get IMAGE URL
        # img_wall_item = item.find(attrs={'class': 'imgWallItem'})

        # # Get the style attribute
        # style = img_wall_item.get('style')

        # # Extract the URL from the style attribute using a regular expression
        # url_match = re.search(r"url\('(.+?)'\)", style)

        # if url_match:
        #     background_image_url = url_match.group(1)
        #     background_image_url += '?imw=5000&imh=5000&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false'

        #     print(background_image_url)

        ###################
        # get PUBLLISHED FILE ID FROM STEAM API
        # published_file_id = item.get('data-publishedfileid')
        # print(published_file_id)

        # url = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/'

        # params = {
        #     'key': '783041FE166A0240714001AEBEBEDF7C',
        #     'itemcount': 1,
        #     'publishedfileids[0]': published_file_id
        # }

        # response = requests.post(url, data=params)
        # response_data = response.json()

        # print(response_data)



        # break
        i += 1
        # print(i)
        if i>= 2:
            break



    browser.quit()
    return steam_data

    # return profile_media_items

# post image to discord
async def post_images(username, discord_user_id, channel_id, is_steam = False):
    global bot, first_run, processed_tweets

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

    first_run = False

    print('~~~~~~~')

    # for each tweet
    for tweet in posts:

        # if first run, mark latest, do not re-upload to discord
        if first_run:
            print(f"first run, adding to processed: {tweet['id']}")
            processed_tweets.add(tweet['id'])        
            continue

        # already processed
        if tweet['id'] in processed_tweets:
            print(f"already processed: {tweet['id']}")
            continue

        # not already processed, add
        print(f'new: {tweet}')
        processed_tweets.add(tweet['id'])

        # mention
        mention = f'<@{discord_user_id}>'

        # for each image
        for img_url in tweet['img_urls']:

            print(img_url)

            # upload channel
            channel = bot.get_channel(channel_id)

            print('downloading...')

            # download image            
            try:
                response = requests.get(img_url)
                print(response)
                if response.status_code == 200:
                    
                    # send to discord channel
                    file = discord.File(io.BytesIO(response.content), filename="image.jpg")
                    if not first_run:
                        await channel.send(f'From: {mention}', file=file)
                    else:
                        print('first run, setting latest..')
            except Exception as e:
                # handle the exception gracefully
                print("An exception occurred:", e)         

            print('done downloading...')

# check twitter on timer loop
@tasks.loop(seconds=60)
async def check_twitter():
    print('checking twitter... ', end='')

    # for each user in config
    for user in twitter_config["users"]:
        print(user)
        username = user["twitter_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = twitter_config['channel_id']

        await post_images(username, discord_user_id, channel_id, False)
    print('done.')

@tasks.loop(seconds=60)
async def check_steam():
    print('checking steam... ', end='')

    # for each user in config
    for user in steam_config["users"]:
        print(user)
        username = user["steam_username"]
        discord_user_id = user["discord_user_id"]
        channel_id = twitter_config['channel_id']

        await post_images(username, discord_user_id, channel_id, True)
    print('done.')

@bot.event
async def on_ready():
    global first_run 
    print(f'Logged in as {bot.user.name}')
    # check_twitter.start()
    check_steam.start()

bot.run(twitter_config['discord_token'])