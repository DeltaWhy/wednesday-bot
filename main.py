from dotenv import load_dotenv
import os
import logging


load_dotenv()
logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'),
        format='%(asctime)s - %(levelname)s - %(name)s: %(message)s')


import wednesday_bot.database
from wednesday_bot.bot import bot


bot.run(os.environ['DISCORD_TOKEN'])
