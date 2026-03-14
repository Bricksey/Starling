import traceback
import discord
import sys
from discord.ext import commands
import argparse
import yaml
import logging
import os
from datetime import datetime


class Bot(commands.Bot):
    def __init__(self, prefix, config_path):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self.available_cogs = {}
        # Allow getting bot uptime
        self.start_time = datetime.now()
        super().__init__(prefix, intents=intents)

    async def setup_hook(self):
        await self.load_cogs()

    async def on_ready(self):
        self.logger.info(f"Logged in as {self.user}")

    async def load_cogs(self):
        valid_cogs = []
        failed_cogs = []
        cog_modules = [f"cogs.{c}" for c in os.listdir("cogs")]

        # Non-bundled cogs mounted from docker host.
        if os.path.isdir("cogs_mounted"):
            cog_modules += [f"cogs_mounted.{c}" for c in os.listdir("cogs_mounted")]

        for cog in cog_modules:
            try:
                await self.load_extension(cog)
                valid_cogs.append(cog)
            except commands.ExtensionAlreadyLoaded:
                # Allow loading new cogs by running this function again from base
                self.logger.debug(f"{cog} already loaded, skipping.")
            except commands.ExtensionError as e:
                # Catch all other errors in cogs.
                self.logger.warning(f"Extension load failed for {cog}: {e}")
                self.logger.debug(traceback.format_exc())
                failed_cogs.append(cog)

        if len(failed_cogs) > 0:
            self.logger.warning(f"Failed to load the following cogs: {failed_cogs}")
        self.logger.info(f"Cogs found: {valid_cogs}")

    async def get_config(self, identifier, default_config=None):
        try:
            with open(f"{self.config_path}/{identifier}.yaml", "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            with open(f"{self.config_path}/{identifier}.yaml", "w") as f:
                yaml.safe_dump(default_config, f)
                return default_config

    async def write_config(self, identifier, data):
        with open(f"{self.config_path}/{identifier}.yaml", "w") as f:
            yaml.safe_dump(data, f)


def main():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="A multipurpose Discord bot.",
        epilog="Token must be set before usage."
    )
    parser.add_argument('-t', '--token')
    parser.add_argument('-p', '--prefix', default="!")
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    config_path = "./config/"
    if not os.path.isdir(config_path):
        try:
            os.mkdir(config_path)
        except Exception as e:
            print(f"Couldn't create config directory:{e}")
            sys.exit(1)
    prefix = os.getenv("PREFIX") or args.prefix
    token = args.token or os.getenv("TOKEN")
    if token is None:
        parser.print_help()
        sys.exit(1)
    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    bot = Bot(prefix, config_path)
    bot.run(
        token,
        log_level=log_level,
        root_logger=True
    )


if __name__ == "__main__":
    main()
