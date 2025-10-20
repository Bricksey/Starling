import discord.errors
from discord.ext import commands


class Profile(commands.Cog):
    """Make changes to the bot's profile."""
    def __init__(self, bot):
        self.bot = bot

    @commands.is_owner()
    @commands.group(invoke_without_command=True)
    async def profile(self, ctx):
        pass

    @commands.is_owner()
    @profile.command()
    async def avatar(self, ctx):
        """
        Change the bot's avatar
        The new avatar must be attached as an image when the command is run.
        """
        try:
            image = await ctx.message.attachments[0].read()
            await self.bot.user.edit(avatar=image)
            await ctx.message.add_reaction("✅")
        except discord.errors.HTTPException as e:
            await ctx.reply(str(e).split(":")[-1])
        except (ValueError, IndexError):
            msg = "Unsupported attachment\n"
            msg += "Supported types are JPEG, PNG, GIF, and WEBP."
            await ctx.reply(msg)


    @commands.is_owner()
    @profile.command()
    async def bio(self, ctx, *, bio):
        """
        Change the bot's profile bio.
        This changes the Application's description.
        Arguments:
            bio: The new bio to set.
        Example usage:
            [p]profile bio A multipurpose Discord bot.
        """
        await self.bot.application.edit(description=bio)
        await ctx.message.add_reaction("✅")

    @commands.is_owner()
    @profile.command()
    async def username(self, ctx, *, name):
        """
        Change the bot's username.
        Arguments:
            name: The new username to set.
        Example usage:
            [p]profile username John Bot
        """
        try:
            await self.bot.user.edit(username=name)
            await ctx.message.add_reaction("✅")
        except discord.errors.HTTPException as e:
            await ctx.reply(str(e).split(":")[-1])

    @commands.is_owner()
    @commands.guild_only()
    @profile.command()
    async def nickname(self, ctx, *, name=None):
        """
        Change the bot's nickname in this server.
        Arguments:
            name: The new nickname to set.
        Example usage:
            [p]profile nickname Jane Bot
        """
        try:
            await ctx.guild.me.edit(nick=name)
            await ctx.message.add_reaction("✅")
        except discord.errors.HTTPException as e:
            await ctx.reply(str(e).split(":")[-1])