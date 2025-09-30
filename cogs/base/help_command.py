import discord
from discord.ext import commands
import textwrap


class HelpCommand(commands.HelpCommand):
    wrapper = textwrap.TextWrapper(drop_whitespace=True)
    async def send_bot_help(self, mapping):
        username = self.context.bot.user.name
        prefix = self.context.bot.command_prefix
        msg = f"""\
        ### About {username}:
        *{username}* is a multipurpose Discord bot running on discord.py {discord.__version__}
        There are currently **{len(mapping) - 1}** cogs loaded.
        ### Cogs:
        ```yaml"""
        msg = textwrap.dedent(msg)
        for cog, cmds in mapping.items():
            if cog is None:
                # This help command will not have a cog, skip.
                continue
            if len(await self.filter_commands(cmds)) == 0:
                # Don't show the user cogs they can't use
                continue
            msg += f"\n{cog.qualified_name}: {cog.description or "No description"}"
        msg += f"```\n* Run `{prefix}help cog_name` to see command usage."
        await self.get_destination().send(msg)

    async def send_cog_help(self, cog):
        prefix = self.context.bot.command_prefix
        msg = f"### Commands for `{cog.qualified_name}`\n```yaml"
        for command in cog.get_commands():
            msg += await self.get_all_group_commands(command)
        msg += f"\n```\n* For detailed info on a command, run `{prefix}help command_name`"
        await self.get_destination().send(msg)

    async def send_command_help(self, cmd: commands.Command):
        prefix = self.context.bot.command_prefix
        msg = f"### Help for `{cmd.qualified_name}`"
        msg += f"\n```yaml\n{cmd.help}\n```".replace("[p]", prefix)
        await self.get_destination().send(msg)


    async def send_group_help(self, group):
        bot = self.context.bot
        cog_name = group.name.capitalize()
        # Get cog help if group is just used for namespacing
        if group.help is None and cog_name in bot.cogs:
            cog = bot.cogs[cog_name]
            await self.send_cog_help(cog)
            return
        prefix = self.context.bot.command_prefix
        msg = f"### Help for `{group.qualified_name}`"
        msg += f"\n```yaml\n{group.help}\n```".replace("[p]", prefix)
        await self.get_destination().send(msg)

    async def command_not_found(self, string):
        cog_name = string.capitalize()
        bot = self.context.bot
        if cog_name in bot.cogs:
            cog = bot.cogs[cog_name]
            await self.send_cog_help(cog)
        else:
            await self.get_destination().send("Command not found")

    async def send_error_message(self, error):
        # Not needed as command_not_found prints the error.
        pass

    async def get_all_group_commands(self, group):
        if group.short_doc is not None:
            msg = f"\n{group.qualified_name}: {group.short_doc}"
        if type(group) is commands.core.Group:
            for command in await self.filter_commands(group.commands):
                msg += await self.get_all_group_commands(command)

        return msg