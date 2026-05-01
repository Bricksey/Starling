import discord
import logging
import asyncio
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse
from discord.ext import commands, tasks
from .mumble_protocol import fetch_user_count

class Mumble(commands.Cog):
    """Track user counts across Mumble servers"""
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.conf = {}
        self.user_count = None
        self.mumble_server = None
        self.task_interval = 5
        self.users = []
        self.channels = []
        self.notify_cooldown = False

    async def cog_load(self):
        default_config = {
            "task_interval": 5,
            "channels": [],
            "users": [],
            "mumble_server": None
        }
        self.conf = await self.bot.get_config("mumble", default_config)
        self.task_interval = self.conf["task_interval"]
        self.mumble_server = self.conf["mumble_server"]
        self.logger.info(f"Starting Mumble task")
        self.update_statuses.start()
        self.update_statuses.change_interval(seconds=self.task_interval)

    async def cog_unload(self):
        self.logger.info("Unloading Mumble Status, clearing channel status")
        for channel in self.channels:
            await self.clear_channel(channel)
        self.update_statuses.stop()
        self.notify_cooldown_task.stop()


    @commands.group(invoke_without_command=True)
    async def mumble(self, ctx):
        addr = self.mumble_server[0]
        port = self.mumble_server[1]
        if port != 64738:
            server_string = f"{addr}:{port}"
        else:
            server_string = f"{addr}"
        p = self.bot.command_prefix
        msg = f"""
        This cog is tracking the user count for the Mumble server at `{server_string}`
        Get notified via DM when this server becomes active with `{p}mumble notify`
        
        [Learn more about Mumble](<https://www.mumble.info/>)
        """
        await ctx.reply(msg)

    @mumble.command()
    @commands.is_owner()
    async def server(self, ctx, server_address=None):
        """
        Sets the Mumble server for the cog to track
        Arguments:
            server_address: The address of the Mumble server
        Example usage:
            [p]mumble server example.com
            [p]mumble server example.com:1234
        """
        if server_address is None:
            self.mumble_server = None
            await ctx.reply("Mumble server unset, tracking disabled.")
            await self.update_conf()
            for channel in self.channels:
                await self.clear_channel(channel)
            return

        url = urlparse(f"//{server_address}")
        address = url.hostname
        if port := url.port is None:
            port = 64738
        # Connection test may be slow, give user feedback with typing indicator.
        async with ctx.typing():
            reachable = await self.server_is_reachable(address, port)
        if not reachable:
            await ctx.reply("That server does not appear reachable, try again.")
        else:
            self.mumble_server = [address, port]
            await ctx.message.add_reaction("✅")
        await self.update_conf()

    @mumble.command()
    @commands.is_owner()
    async def interval(self, ctx, interval: float):
        """
        Sets the frequency at which the server is pinged
        Arguments:
            interval: a float value indicating how many seconds between updates
        """
        self.update_statuses.change_interval(seconds=interval)
        self.task_interval = interval
        await self.update_conf()
        await ctx.message.add_reaction("✅")

    @mumble.command()
    @commands.is_owner()
    async def status(self, ctx, channel: discord.VoiceChannel):
        """
        Toggles displaying the Mumble status on the given channel.
        Arguments:
            channel: The ID of a Discord voice channel
        Example Usage:
            [p]mumble status 1234567890
        """
        # Toggle status off if already present.
        if channel in self.channels:
            self.channels.remove(channel)
            await self.clear_channel(channel)
            await ctx.message.add_reaction("✅")
            await self.update_conf()
            return
        self.channels.append(channel)
        # Force update
        self.user_count = None
        await self.update_conf()
        await ctx.message.add_reaction("✅")
        self.logger.info(f"Mumble tracking added for channel: {channel.name}")

    @mumble.command()
    async def notify(self, ctx):
        """
        Toggles DM notifications for activity on the Mumble server
        """
        user = ctx.message.author
        if user in self.users:
            self.users.remove(user)
            setting = "🔕"
        else:
            self.users.append(user)
            setting = "🔔"
        await self.update_conf()
        await ctx.message.add_reaction(setting)

    @tasks.loop(seconds=5)
    async def update_statuses(self):
        if self.mumble_server is None:
            return
        self.logger.debug("Updating Mumble servers.")

        # If the loop gets behind, it will try to catch up all delayed runs.
        # This just prevents it doing that and spamming the server.
        current_time = datetime.now(timezone.utc)
        next_iteration_time = self.update_statuses.next_iteration
        if next_iteration_time is not None and current_time >= next_iteration_time:
            self.logger.debug("Restarting update_statuses() task")
            self.update_statuses.restart()
            return

        # Store previous count before updating
        previous_count = self.user_count
        self.logger.debug(f"Pinging {self.mumble_server}")
        try:
            addr = self.mumble_server[0]
            port = self.mumble_server[1]
            self.user_count = await fetch_user_count(addr, port)
        except TimeoutError:
            # Timeouts will occur and are normal behaviour
            self.logger.debug(f"Mumble ping timed out")
            return
        if previous_count == self.user_count:
            # Don't ping Discord if no status update is needed
            self.logger.debug("Mumble has not changed user count.")
            return

        if self.user_count == 0 and previous_count is not None:
            # Don't ping on brief disconnects
            self.logger.debug("Starting notification cooldown.")
            try:
                self.notify_cooldown_task.start()
            except RuntimeError:
                pass

        for channel in self.channels:
            user_plural = "users" if self.user_count != 1 else "user"
            await channel.edit(status=f"{self.user_count} {user_plural} on Mumble")
            # Show voice indicator if Mumble is active by joining channel
            guild = channel.guild
            voice_client = guild.voice_client
            if self.user_count > 0 and voice_client is None:
                self.logger.info(f"Connected to {channel.name} in {guild.name}")
                await channel.connect(self_mute=True, self_deaf=True, timeout=1)
            elif self.user_count == 0 and voice_client is not None:
                self.logger.info(f"Disconnected from {channel.name} in {guild.name}")
                await voice_client.disconnect()

        # Only notify users when someone first joins a server
        if previous_count == 0 and self.user_count > 0:
            if self.notify_cooldown:
                self.logger.info("Not pinging due to cooldown.")
                return
            self.logger.info(f"Pinging users for Mumble")
            for user in self.users:
                dm = await user.create_dm()
                msg = f"Mumble just became active!"
                await dm.send(msg)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Status gets cleared when a channel is empty
        channel = before.channel
        if channel is None or channel not in self.channels:
            return

        if len(before.channel.members) == 0:
            self.logger.info("Discord channel now empty, resetting status")
            self.user_count = None

    @update_statuses.before_loop
    async def wait_until_ready(self):
        await self.bot.wait_until_ready()
        # Wait until bot is ready before getting users and channels
        user_ids = self.conf["users"]
        self.users = [self.bot.get_user(u) for u in user_ids]
        channel_ids = self.conf["channels"]
        self.channels = [self.bot.get_channel(c) for c in channel_ids]

    @tasks.loop(minutes=2, count=2)
    async def notify_cooldown_task(self):
        # Task runs twice, once to set the cooldown and once to clear it.
        if self.notify_cooldown:
            self.notify_cooldown = False
        else:
            self.notify_cooldown = True

    async def update_conf(self):
        # Can't store channel/user objects, use IDs
        channel_ids = [c.id for c in self.channels]
        user_ids = [u.id for u in self.users]
        self.conf = {
            "task_interval": self.task_interval,
            "channels": channel_ids,
            "users": user_ids,
            "mumble_server": self.mumble_server
        }
        await self.bot.write_config("mumble", self.conf)

    async def clear_channel(self, channel):
        """Remove channel status and disconnect from voice."""
        await channel.edit(status=None)
        voice_client = channel.guild.voice_client
        if voice_client is not None:
            await voice_client.disconnect()


    @staticmethod
    async def server_is_reachable(server, port=64738):
        tries = 0
        while (tries := tries + 1) < 3:
            try:
                await fetch_user_count(server, port)
                return True
            except (ConnectionError, TimeoutError):
                await asyncio.sleep(3)
            except socket.gaierror:
                # Handles unknown services (neither valid domains nor IPs)
                break
        return False