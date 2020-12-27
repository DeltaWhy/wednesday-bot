from dotenv import load_dotenv
import os


load_dotenv()


import wednesday_bot.database
from wednesday_bot.bot import bot


bot.run(os.environ['DISCORD_TOKEN'])
