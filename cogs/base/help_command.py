import discord
from discord.ext import commands


class HelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        username = self.context.bot.user.name
        ver = discord.__version__
        prefix = self.context.clean_prefix
        msg = f"### About {username}\n"
        msg += f"*{username}* is a multipurpose bot built on discord.py {ver}\n"
        msg += "### Cogs: \n"
       # Start code block for cog output
        msg += "```yaml\n"
        for cog, cmds in mapping.items():
            if cog is None:
                # This help command will not have a cog, skip.
                continue
            if len(await self.filter_commands(cmds)) == 0:
                # Don't show the user cogs they can't use
                continue
            msg += f"\n{cog.qualified_name}: {cog.description or "No description"}"
        msg += f"```\n* Run `{prefix}help cog_name` to see command usage."
        await self.context.reply(msg)

    async def send_cog_help(self, cog):
        cmds = await self.filter_commands(cog.walk_commands())
        if len(cmds) == 0:
            # Don't print help if the user can't use the cog.
            msg = "You don't have access to any commands in this cog."
            await self.context.reply(msg)
            return
        prefix = self.context.clean_prefix
        msg = f"### Commands for `{cog.qualified_name}`\n```yaml"
        for command in cmds:
            if command.short_doc != "":
                msg += f"\n{command.qualified_name}: {command.short_doc}"
        msg += f"\n```\n* For detailed info on a command, run `{prefix}help command_name`"
        await self.context.reply(msg)

    async def send_command_help(self, cmd: commands.Command):
        prefix = self.context.clean_prefix
        msg = f"### Help for `{cmd.qualified_name}`"
        msg += f"\n```yaml\n{cmd.help}\n```".replace("[p]", prefix)
        await self.context.reply(msg)

    async def send_group_help(self, group):
        bot = self.context.bot
        cog_name = group.name.capitalize()
        # Get cog help if group is just used for namespacing
        if group.help is None and cog_name in bot.cogs:
            cog = bot.cogs[cog_name]
            await self.send_cog_help(cog)
            return
        prefix = self.context.clean_prefix
        msg = f"### Help for `{group.qualified_name}`\n"
        msg += "```yaml\n"
        msg += f"{group.help}```\n".replace("[p]", prefix)
        # Show the group's subcommands if any are available
        cmds = await self.filter_commands(group.walk_commands())
        if len(cmds) != 0:
            msg += f"### Commands in `{group.qualified_name}`\n"
            msg += "```yaml\n"
            for command in cmds:
                msg += f"{command.qualified_name}: {command.short_doc}\n"
            msg += "```"
        await self.context.reply(msg)

    async def command_not_found(self, string):
        cog_name = string.capitalize()
        bot = self.context.bot
        if cog_name in bot.cogs:
            cog = bot.cogs[cog_name]
            await self.send_cog_help(cog)
        else:
            await self.context.reply("Command not found")

    async def subcommand_not_found(self, command, string):
        # If a subcommand is not found, send parent's help
        if isinstance(command, commands.Group) and len(command.all_commands) > 0:
            await self.send_group_help(command)
        else:
            await self.send_command_help(command)

    async def send_error_message(self, error):
        # Not needed as command_not_found prints the error.
        pass