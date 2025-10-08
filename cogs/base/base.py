import traceback

import discord
from discord.ext import commands
from .help_command import HelpCommand


class Base(commands.Cog):
    """Commands providing core functionality"""
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
    @commands.is_owner()
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
        await ctx.message.add_reaction("✅")

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx):
        """
        Shuts the bot down.
        """
        await ctx.message.add_reaction("✅")
        await self.bot.close()

    @commands.command()
    @commands.is_owner()
    async def refresh(self, ctx):
        """
        Scans for and loads any new cogs in the bot's cog directory
        """
        extension_count = len(self.bot.extensions)
        self.bot.available_cogs = await self.bot.load_cogs()
        new_extensions = len(self.bot.extensions) - extension_count
        if new_extensions > 0:
            await ctx.reply(f"{new_extensions} cogs loaded!")
            return
        await ctx.reply("No new cogs found")

    @commands.command()
    @commands.is_owner()
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
            await ctx.message.add_reaction("✅")
        except commands.ExtensionError as e:
            self.bot.logger.warn(traceback.format_exc())
            await ctx.reply(f"An error occurred: `{e}`\nCheck your logs for more details.")

    async def set_status(self):
        await self.bot.wait_until_ready()
        status = self.conf["status"]
        if status == "default":
            p = self.bot.text_prefix
            users = len(list(self.bot.get_all_members()))
            guilds = len(self.bot.guilds)
            status = f"{p}help | {users} users | {guilds} servers"
        await self.bot.change_presence(activity=discord.CustomActivity(status))

    @commands.command()
    @commands.cooldown(1, 120)
    async def contact(self, ctx, *, message):
        """
        Sends a DM to the bot's owner
        This command has a cooldown of 120 seconds.
        Arguments:
            message: The message to send
        Example usage:
            [p]contact Lorem ipsum dolor sit amet
        """
        #Ensure newlines are preserved within the quote block
        message = message.replace("\n", "\n> ")
        owner_id = self.bot.owner_id
        owner = self.bot.get_user(owner_id)
        author = ctx.message.author
        if owner is None:
            #Fetch owner if not already cached
            owner = await self.bot.fetch_user(owner_id)
        dm = owner.dm_channel or await owner.create_dm()
        msg = "### New message from `contact`\n"
        msg += f"> {message}\n"
        msg += f"-*{author.name}*"
        await dm.send(msg)
        await ctx.message.add_reaction("📨")


