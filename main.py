import discord
import sys
from discord.ext import commands
import argparse
import yaml
import logging
import os
import importlib
import importlib.util


class Bot(commands.Bot):
    def __init__(self, prefix, config_path):
        intents = discord.Intents.default()
        intents.message_content = True
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self.cog_path = "./cogs"
        self.available_cogs = {}
        super().__init__(prefix, intents=intents)

    async def setup_hook(self):
        self.available_cogs = await self.find_cogs()
        await self.load_cog(self.available_cogs["base"]["spec"])

    async def on_ready(self):
        self.logger.info(f"Logged in as {self.user}")

    async def find_cogs(self):
        importlib.invalidate_caches()
        valid_cogs = []
        failed_cogs = []
        specs = {}
        for cog in os.listdir(self.cog_path):
            cog_path = f"{self.cog_path}/{cog}/"
            if cog[:2] == "__" or not os.path.isdir(cog_path):
                self.logger.warning(f"Invalid entry found in {self.cog_path}: {cog}, skipping")
                continue
            spec = importlib.util.spec_from_file_location(cog, f"{cog_path}/__init__.py")
            if spec is not None:
                if not os.path.isfile(f"{cog_path}/info.yaml"):
                    self.logger.warning(f"{cog} found but no info.yaml provided, skipping.")
                    continue
                with open(f"{cog_path}/info.yaml", "rb") as f:
                    cog_info = yaml.safe_load(f)

                valid_cogs.append(cog)
                specs[cog] = {
                    "name": cog_info["name"],
                    "desc": cog_info["description"],
                    "spec": spec
                }
            else:
                failed_cogs.append(cog)
        if len(failed_cogs) > 0:
            self.logger.warning(f"Failed to load the following cogs: {failed_cogs}")
        self.logger.info(f"Cogs found in {self.cog_path}: {valid_cogs}")
        return specs

    async def load_cog(self, cog_spec):
        self.logger.info(f"Loading {cog_spec.name}")
        cog_module = importlib.util.module_from_spec(cog_spec)
        sys.modules[cog_spec.name] = cog_module
        cog_spec.loader.exec_module(cog_module)
        await cog_module.setup(self)

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

def first_run(path):
    token = input("Bot token: ")
    if token == "":
        print("Token cannot be blank")
        sys.exit(1)
    prefix = input("Command prefix[!]: ")
    if prefix == "":
        prefix = "!"

    initial_config= {
        "token": token,
        "prefix": prefix
    }

    os.mkdir(path)
    with open(path + "bot.yaml", "w") as f:
        yaml.safe_dump(initial_config, f)
    return initial_config


def main():
    config_path = "./config/"
    bot_config_path = config_path + "bot.yaml"
    try:
        with open(bot_config_path, "rb") as f:
            bot_config = yaml.safe_load(f)
    except FileNotFoundError:
        bot_config = first_run(config_path)

    prefix = bot_config["prefix"]
    token = bot_config["token"]

    bot = Bot(prefix, config_path)
    bot.run(
        token,
        log_level=logging.INFO,
        root_logger=True
    )


if __name__ == "__main__":
    main()
