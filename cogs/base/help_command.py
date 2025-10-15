import discord
from discord import ui
from discord.ext import commands

class CogDropdown(ui.Select):
    def __init__(self, view):
        self.__view = view
        super().__init__(placeholder="Select a cog", min_values=1, max_values=1)

    async def callback(self, interaction):
        cog_name = self.values[0]
        await self.__view.select_cog(cog_name)
        await interaction.response.edit_message(view=self.__view)


class CommandDropdown(ui.Select):
    def __init__(self, view):
        self.__view = view
        super().__init__(placeholder="Select a command", min_values=1, max_values=1)

    async def callback(self, interaction):
        cog_name = self.values[0]
        await self.__view.select_command(cog_name)
        await interaction.response.edit_message(view=self.__view)


class HelpLayout(ui.LayoutView):
    def __init__(self, help_command):
        super().__init__(timeout=60)
        self.filter_commands = help_command.filter_commands
        self.ctx = help_command.context
        self.bot = self.ctx.bot
        # Generate titlebar and info section
        name = self.bot.user.name
        ver = discord.__version__
        text = "# Help\n"
        text += f"*{name}* is a multipurpose Discord bot running on discord.py {ver}\n"
        text += "The following cogs are currently available, "
        text += "select a cog to see its commands."
        self.title_text = ui.TextDisplay(text)
        self.thumb = ui.Thumbnail(self.bot.user.display_avatar.url)
        self.title_bar = ui.Section(self.title_text, accessory=self.thumb)
        self.help_text = ui.TextDisplay("")
        self.action_row = ui.ActionRow()
        container = ui.Container(self.title_bar, self.help_text, self.action_row)
        self.add_item(container)

    async def show_bot_help(self):
        self.action_row.clear_items()
        cog_dropdown = CogDropdown(self)
        options = []
        text = "### Cogs\n```yaml\n"
        # Can't serialize cog object, use index as option value
        for cog in self.bot.cogs.values():
            # The help command doesn't have a cog associated, skip it
            if cog is None:
                continue
            # Don't show users cogs they can't use.
            if len(await self.filter_commands(cog.walk_commands())) == 0:
                continue
            cog_dropdown.add_option(label=cog.qualified_name)
            text += f"{cog.qualified_name}: {cog.description or "No description"}\n"
        self.help_text.content = text + "```"
        self.action_row.add_item(cog_dropdown)

    async def select_cog(self, cog_name):
        self.action_row.clear_items()
        cmd_dropdown = CommandDropdown(self)
        cmd_dropdown.add_option(label="Back to cogs...", value="all")
        cog = self.bot.cogs[cog_name]
        cmds = await self.filter_commands(cog.walk_commands())

        if len(cmds) == 0:
            # Don't print help if the user can't use the cog.
            msg = "You don't have access to any commands in this cog."
            self.help_text.content=msg
            return
        msg = f"### Commands for `{cog.qualified_name}`\n```yaml"
        for command in cmds:
            if command.short_doc != "":
                name = command.qualified_name
                msg += f"\n{name}: {command.short_doc}"
                cmd_dropdown.add_option(label=name)
        self.help_text.content= msg + "```"
        self.action_row.add_item(cmd_dropdown)


    async def select_command(self, cmd_name):
        if cmd_name == "all":
            await self.show_bot_help()
            return
        prefix = self.ctx.clean_prefix
        cmd = self.ctx.bot.get_command(cmd_name)
        msg = f"### Help for `{cmd.qualified_name}`"
        msg += f"\n```yaml\n{cmd.help}\n```".replace("[p]", prefix)
        self.help_text.content = msg

    async def on_timeout(self):
        await self.ctx.message.add_reaction("⏱️")
        await self.ctx.rsp.delete()


class HelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
       view = HelpLayout(self)
       await view.show_bot_help()
       #Save response to context to delete on timeout
       self.context.rsp = await self.context.reply(view=view)

    async def send_cog_help(self, cog):
        view = HelpLayout(self)
        await view.select_cog(cog.qualified_name)
        self.context.rsp = await self.context.reply(view=view)

    async def send_command_help(self, cmd: commands.Command):
        view = HelpLayout(self)
        await view.select_command(cmd.qualified_name)
        self.context.rsp = await self.context.reply(view=view)

    async def send_group_help(self, group):
        bot = self.context.bot
        cog_name = group.name.capitalize()
        # Get cog help if group is just used for namespacing
        if group.help is None and cog_name in bot.cogs:
            cog = bot.cogs[cog_name]
            await self.send_cog_help(cog)
            return
        view = HelpLayout(self)
        await view.select_command(group.qualified_name)
        self.context.rsp = await self.context.reply(view=view)

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