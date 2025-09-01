from discord.ext.commands import Bot
from .ping import Ping

async def setup(bot: Bot) -> None:
    await bot.add_cog(Ping(bot))