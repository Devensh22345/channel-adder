import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials (get from https://my.telegram.org)
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')

# Bot token from @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN', '8429065169:AAHJiXwDUl4t_cdPgcVdJDIzFX19sh3gv7g')

# Session string for the admin account
SESSION_STRING = os.getenv('SESSION_STRING')

# Target group where request links will be sent
LINK_GROUP_ID = int(os.getenv('LINK_GROUP_ID'))  # Can be chat_id or username

# List of bots to add to channels (as usernames)
BOTS_TO_ADD = os.getenv('BOTS_TO_ADD', '').split(',')

# MongoDB URI
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
DATABASE_NAME = 'channel_bot_db'
