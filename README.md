# Screenshot Bot

Screenshot Bot is a Discord bot designed to fetch and display Steam screenshots directly within Discord channels. The bot leverages Selenium and BeautifulSoup to scrape Steam profiles and extract screenshot data, making it easier for users to share their gaming moments with their friends.

![](.img/sample1.png)

![](.img/sample2.png)

## Features

- Register and save your Steam ID or custom URL.
- Fetch and display the latest Steam screenshots.
- Support for multiple users.
- Persistent storage of user data using pickle.

## Requirements

- Python 3.7+
- Discord.py
- Selenium
- BeautifulSoup
- aiohttp
- Requests
- Firefox and Geckodriver

## Dependencies

- discord.py
- beautifulsoup4
- selenium
- requests

## Setup

1. **Install Dependencies**

   Use `pip` to install the necessary Python libraries:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Firefox and Geckodriver**

   Ensure you have Firefox installed on your system along with Geckodriver. You can download Geckodriver from [here](https://github.com/mozilla/geckodriver/releases).

3. **Configuration**

   Create a `config-steam.json` file in the root directory of the project with the following structure:
   ```json
   {
       "guild_id": "YOUR_GUILD_ID",
       "discord_token": "YOUR_DISCORD_BOT_TOKEN",
       "users": []
   }
   ```

4. **Run the Bot**

   Execute the bot script:
   ```bash
   python screenshot_bot.py
   ```

## Usage

### Registering Your Steam ID

Use the `/register` command to register your Steam ID or custom URL:
```discord
/register [steamID64 or custom_url]
```
- `steamID64`: You can look up your Steam ID at [steamid.io](https://steamid.io).
- `custom_url`: Set a custom URL in your Steam profile settings.

### Fetching Screenshots

Use the `/screenshot` command to fetch and display your latest Steam screenshots:
```discord
/screenshot
```

### Testing with a Specific Steam ID

Use the `/test` command to fetch screenshots for any Steam ID without registration:
```discord
/test [steamID64 or custom_url]
```

### Getting Help

Use the `/help` command to get a list of available commands and usage instructions:
```discord
/help
```

## Code Overview

### Bot Client

The `bot_client` class is a custom Discord client that initializes with all necessary intents and synchronizes commands with the Discord server.

### Firefox WebDriver Singleton

The `FirefoxWebDriverSingleton` class ensures a single instance of Firefox WebDriver is used across the application. It includes methods to manage the browser lifecycle and clean up temporary files.

### Steam Functions

- `get_steam_url(username)`: Generates the Steam URL for the provided username or Steam ID.
- `get_steam_uploads(username)`: Scrapes the Steam profile page to get the latest screenshots.

### Discord Commands

- `/register`: Registers a user's Steam ID.
- `/screenshot`: Fetches and displays the user's registered Steam screenshots.
- `/test`: Fetches screenshots for a given Steam ID without registration.
- `/help`: Provides help and command usage information.

### Persistent State

The bot uses `pickle` to save and load the state, which includes registered Steam IDs for users.

## Notes

- Ensure the `data` directory exists for storing the state file (`state.pickle`).
- The bot will handle and report exceptions gracefully, providing error messages in Discord where necessary.

## Contributing

Feel free to fork this repository and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License.

---

Happy gaming and sharing your screenshots with Screenshot Bot! 