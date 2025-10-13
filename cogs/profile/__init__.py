from discord.ext.commands import Bot
from .profile import Profile

async def setup(bot: Bot) -> None:
    await bot.add_cog(Profile(bot))