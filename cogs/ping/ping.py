from discord.ext import commands


class Ping(commands.Cog):
    """Respond to the ping command"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Respond with 'pong!'"""
        await ctx.send("Pong!")