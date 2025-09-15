import discord
from discord.ext import commands


class Base(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conf = {}

    async def cog_load(self):
        default_config = {
            "cogs": []
        }
        self.conf = await self.bot.get_config("base", default_config)
        for cog in self.conf["cogs"]:
            spec = self.bot.available_cogs[cog]["spec"]
            await self.bot.load_cog(spec)

    @commands.command()
    async def shutdown(self, ctx):
        await ctx.send("Shutting down...")
        await self.bot.close()

    @commands.command()
    async def load(self, ctx, cog_name):
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
        self.bot.available_cogs = await self.bot.find_cogs()
        await ctx.send(f"{len(self.bot.available_cogs)} cogs found.")

