from discord.ext.commands import Bot
from .mumble import Mumble

async def setup(bot: Bot) -> None:
    await bot.add_cog(Mumble(bot))