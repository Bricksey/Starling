from venv import logger

import discord
from discord.ext import commands
import argparse
import yaml
import logging

class Bot(commands.Bot):
    def __init__(self, prefix, config_path):
        intents = discord.Intents.default()
        intents.message_content = True
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        super().__init__(prefix, intents=intents)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}")


def first_run(path):
    token = input("Bot token: ")

    initial_config= {
        "bot": {
            "token": token,
            "prefix": "!"
        }
    }
    with open(path, "w") as f:
        yaml.safe_dump(initial_config, f)

    return initial_config


def main():
    config_location = "./conf.yaml"
    try:
        with open(config_location, "rb") as f:
            config_data = yaml.safe_load(f)
    except FileNotFoundError:
        config_data = first_run(config_location)

    prefix = config_data["bot"]["prefix"]
    token = config_data["bot"]["token"]

    bot = Bot(prefix, config_location)
    bot.run(
        token,
        log_level=logging.INFO,
        root_logger=True
    )


if __name__ == "__main__":
    main()
