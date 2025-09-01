from discord.ext.commands import Bot
from .base import Base

async def setup(bot: Bot) -> None:
    await bot.add_cog(Base(bot))