import traceback

import discord
from discord.ext import commands
from .help_command import HelpCommand


class Base(commands.Cog):
    """Commands providing core functionality and cog management"""
    def __init__(self, bot):
        self.bot = bot
        self.conf = {}

    async def cog_load(self):
        default_config = {
            "status": "default"
        }
        self.conf = await self.bot.get_config("base", default_config)
        self.bot.help_command = HelpCommand()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.set_status()

    @commands.command()
    async def status(self, ctx, *, status):
        """
        Sets the bot's status.
        Running [p]status default will reset the status.
        Arguments:
            status: The status to give the bot.
        Example usage:
            [p]status Hello, world!
        """
        self.conf["status"] = status
        await self.set_status()
        await self.bot.write_config("base", self.conf)
        await ctx.send("Status changed!")

    @commands.command()
    async def shutdown(self, ctx):
        """
        Shuts the bot down.
        """
        await ctx.send("Shutting down...")
        await self.bot.close()

    @commands.command()
    async def refresh(self, ctx):
        """
        Scans for and loads any new cogs in the bot's cog directory
        """
        extension_count = len(self.bot.extensions)
        self.bot.available_cogs = await self.bot.load_cogs()
        new_extensions = len(self.bot.extensions) - extension_count
        if new_extensions > 0:
            await ctx.send(f"{new_extensions} cogs loaded!")
            return
        await ctx.send("No new cogs found")

    @commands.command()
    async def reload(self, ctx, cog):
        """
        Reloads a loaded cog.
        Arguments:
            cog: The name of the cog to reload
        Example usage:
            [p]reload ping
        """
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(f"{cog} reloaded!")
        except commands.ExtensionError as e:
            self.bot.logger.warn(traceback.format_exc())
            await ctx.send(f"An error occurred: `{e}`\nCheck your logs for more details.")

    async def set_status(self):
        await self.bot.wait_until_ready()
        status = self.conf["status"]
        if status == "default":
            status = f"Running discord.py {discord.__version__}"
        await self.bot.change_presence(activity=discord.CustomActivity(status))


