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
            "cogs": [],
            "status": "default"
        }
        self.conf = await self.bot.get_config("base", default_config)
        for cog in self.conf["cogs"]:
            spec = self.bot.available_cogs[cog]["spec"]
            await self.bot.load_cog(spec)
        self.bot.help_command = HelpCommand()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.set_status()

    @commands.command()
    async def status(self, ctx, *, status):
        """
        Sets the bot's status.
        Running `[p]status default` will reset the status.
        Arguments:
            `status`: The status to give the bot.
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
    async def load(self, ctx, cog_name):
        """
        Loads a cog
        Arguments:
            `cog`: The cog to load
        Example usage:
            [p]load ping
        """
        if cog_name in self.bot.available_cogs:
            spec = self.bot.available_cogs[cog_name]["spec"]
            await self.bot.load_cog(spec)
            await ctx.send(f"{cog_name} loaded!")
            self.conf["cogs"].append(cog_name)
            await self.bot.write_config("base", self.conf)
        else:
            await ctx.send(f"{cog_name} not found.")

    @commands.command()
    async def cogs(self, ctx):
        """
        Lists all cogs available to load.
        Cogs can be loaded using the `package names`
        """
        msg = "## Available cogs:"
        for cog_name in self.bot.available_cogs.keys():
            full_name = self.bot.available_cogs[cog_name]["name"]
            desc = self.bot.available_cogs[cog_name]["desc"]
            msg += f"\n\t* {full_name} (`{cog_name}`) - {desc}"
            if self.bot.get_cog(cog_name.capitalize()) is not None:
                msg += " **[Loaded]**"
        await ctx.send(msg)

    @commands.command()
    async def unload(self, ctx, cog_name):
        """
        Unloads a cog
        Arguments:
            `cog`: The cog to unload
        Example usage:
            [p]unload ping
        """
        if cog_name == "base":
            await ctx.send("Cannot unload `base`, doing so would break core bot functionality.")
            return
        if self.bot.get_cog(cog_name.capitalize()) is not None:
            await self.bot.remove_cog(cog_name.capitalize())
            await ctx.send(f"{cog_name} unloaded")
            self.conf["cogs"].remove(cog_name)
            await self.bot.write_config("base", self.conf)
        else:
            await ctx.send(f"{cog_name} not found")

    @commands.command()
    async def refresh(self, ctx):
        """
        Refreshes all available cogs in the bot's cog directory
        """
        self.bot.available_cogs = await self.bot.find_cogs()
        await ctx.send(f"{len(self.bot.available_cogs)} cogs found.")

    async def set_status(self):
        await self.bot.wait_until_ready()
        status = self.conf["status"]
        if status == "default":
            status = f"Running discord.py {discord.__version__}"
        await self.bot.change_presence(activity=discord.CustomActivity(status))


