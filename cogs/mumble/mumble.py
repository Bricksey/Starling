import discord
import logging
import asyncio
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse
from discord.ext import commands, tasks
from .mumble_protocol import fetch_user_count
from dataclasses import dataclass, asdict, field


@dataclass()
class MumbleServer:
    address: str
    port: int = 64738
    channels: list[int] = field(default_factory=list)
    users: list[int] = field(default_factory=list)
    user_count: int = 0

    def __post_init__(self):
        # Allow address:port to be passed as one string and parsed
        if p := urlparse(f"//{self.address}").port is not None:
            self.port = p
        # Force an update on first load
        self.user_count = -1

    async def ping(self):
        self.user_count = await fetch_user_count(self.address, self.port)

class Mumble(commands.Cog):
    """Track user counts across Mumble servers"""
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.conf = {}
        self.user_notification_settings = {}
        self._servers_by_user = {}
        self._servers_by_channel = {}
        self._servers_by_address = {}

    async def cog_load(self):
        default_config = {
            "task_interval": 5,
            "servers": [],
            "user_notifications" : {}
        }
        self.conf = await self.bot.get_config("mumble", default_config)
        all_servers = [MumbleServer(**s) for s in self.conf["servers"]]
        self.user_notification_settings = self.conf["user_notifications"]

        self.logger.info(f"Starting Mumble task, tracking {len(all_servers)} servers.")
        self.update_statuses.start()
        self.update_statuses.change_interval(seconds=self.conf["task_interval"])

        for server in all_servers:
            # Build dicts indexed by channel, address and user
            # servers_by_address will always contain all servers
            self._servers_by_address[server.address] = server
            for user in server.users:
                if user not in self._servers_by_user:
                    self._servers_by_user[user] = []
                self._servers_by_user[user].append(server)
            for channel in server.channels:
                self._servers_by_channel[channel] = server

    async def cog_unload(self):
        self.logger.info("Unloading Mumble Status, clearing channel status")
        for channel in self._servers_by_channel:
            await self.bot.get_channel(channel).edit(status=None)


    @commands.group(invoke_without_command=True)
    async def mumble(self, ctx):
        help_cmd = self.bot.help_command
        help_cmd.context = ctx
        await help_cmd.send_cog_help(self)

    @mumble.command()
    async def interval(self, ctx, interval):
        """
        Sets the frequency at which servers are pinged
        Arguments:
            interval: a float value indicating how many seconds between updates
        """
        try:
            interval = float(interval)
            self.update_statuses.change_interval(seconds=interval)
            self.conf["task_interval"] = interval
            await self.update_conf()
            await ctx.send("Updated interval")
        except ValueError:
            await ctx.send("Invalid value for interval")

    @mumble.group(invoke_without_command=True)
    async def status(self, ctx, server_address, channel_id):
        """
        Adds the status of a Mumble server to a channel.
        This status can be removed with `[p]status disable`
        Arguments:
            server_address: The address of the Mumble server
            channel_id: The ID of a Discord voice channel
        Example Usage:
            [p]mumble status example.com 1234567890
        """
        # Ensure channel exists and server is reachable before writing to config
        try:
            if not isinstance(self.bot.get_channel(int(channel_id)), discord.VoiceChannel):
                await ctx.send(f"{channel_id} is not a valid voice channel.")
                return
        except ValueError:
            await ctx.send("Discord channel IDs must be integers.")

        # Ensure that duplicate channels can't be added
        if server := self.get_servers(address=server_address):
            if channel_id in server.channels:
                await ctx.send(f"Channel is already displaying status of {server_address}")
                return
        else:
            connection_test = await self.server_is_reachable(server_address)
            if not connection_test:
                await ctx.send("Server does not appear to be reachable, try again.")
                return
            server = MumbleServer(server_address)
        await self.server_append(server, channel=int(channel_id))

        await ctx.send("Added status to channel")
        self.logger.info(f"Tracking added for {server_address} on channel {channel_id}")



    @status.command()
    async def disable(self, ctx, channel_id):
        """
        Removes Mumble statuses from a channel
        Arguments:
            channel_id: The ID of a Discord voice channel
        Example Usage:
            [p]mumble status disable 1234567890
        """
        try:
            channel_id = int(channel_id)
        except ValueError:
            await ctx.send("Invalid channel ID")
            return
        # Check server exists before modifying
        if not (server := self.get_servers(channel=channel_id)):
            await ctx.send("That channel isn't tracking any servers")
            return

        await self.server_remove(server, channel=channel_id)
        self.logger.info(f"Tracking removed from channel {channel_id}")

    @mumble.group(invoke_without_command=True)
    async def untrack(self, ctx, server_address):
        """
        Stop getting notifications for a Mumble server.
        Arguments:
            server_address: The address of the Mumble server
        Example Usage:
            [p]mumble untrack example.com
        """
        user_id = ctx.message.author.id
        # Check server exists before modifying
        server = self.get_servers(address=server_address)
        if user_id not in server.users:
            await ctx.send("You're not tracking that server.")
            return
        await self.server_remove(server, user=user_id)
        await ctx.send(f"{server.address} is no longer being tracked.")



    @mumble.group(invoke_without_command=True)
    async def track(self, ctx, server_address):
        """
        Get notified via DM when a Mumble server first becomes active.
        Toggle all notifications with [p]mumble track toggle
        Arguments:
            server_address: The address of the Mumble server
        Example Usage:
            [p]mumble track example.com
        """
        user_id = ctx.message.author.id
        # Check server is valid before writing to config
        if server := self.get_servers(address=server_address):
            if user_id in server.users:
                await ctx.send("You're already tracking that server.")
                return
        else:
            connection_test = await self.server_is_reachable(server_address)
            if not connection_test:
                await ctx.send("Server does not appear to be reachable, try again.")
                return
            server = MumbleServer(server_address)
        await self.server_append(server, user=user_id)
        await ctx.send(f"Added tracking for {server_address}")
        # Enable notifications if user has never run toggle
        if user_id not in self.user_notification_settings:
            self.user_notification_settings[user_id] = True

    @track.command()
    async def toggle(self, ctx):
        """
        Toggle notifications from all tracked servers
        """
        user_id = ctx.message.author.id
        # Enable if the user hasn't run toggle before
        if user_id not in self.user_notification_settings:
            self.user_notification_settings[user_id] = True
            setting_string = "on"
        elif self.user_notification_settings[user_id]:
            self.user_notification_settings[user_id] = False
            setting_string = "off"
        else:
            self.user_notification_settings[user_id] = True
            setting_string = "on"

        await self.update_conf()
        await ctx.send(f"Toggled notifications {setting_string}")

    @tasks.loop(seconds=5)
    async def update_statuses(self):
        self.logger.debug("Updating Mumble servers.")

        # If the loop gets behind, it will try to catch up all delayed runs.
        # This just prevents it doing that and spamming the server.
        current_time = datetime.now(timezone.utc)
        next_iteration_time = self.update_statuses.next_iteration
        if next_iteration_time is not None and current_time >= next_iteration_time:
            self.logger.debug("Restarting update_statuses() task")
            self.update_statuses.restart()
            return

        for s in self.get_all_servers():
            # Store previous count before updating
            previous_count = s.user_count
            self.logger.debug(f"Pinging {s.address}")
            try:
                await s.ping()
                self.logger.debug(f"{s.user_count} users in {s.address}")
            except TimeoutError:
                # Timeouts will occur and are normal behaviour
                self.logger.debug(f"Ping timed out: {s.address}")
                continue
            if previous_count == s.user_count:
                # Don't ping Discord if no status update is needed
                continue

            for channel_id in s.channels:
                channel = self.bot.get_channel(channel_id)
                user_plural = "users" if s.user_count != 1 else "user"
                await channel.edit(status=f"{s.user_count} {user_plural} on Mumble")
                guild = channel.guild
                voice_client = guild.voice_client
                if s.user_count > 0 and voice_client is None:
                    self.logger.info(f"Connected to {channel.name} in {guild.name}")
                    await channel.connect()
                elif s.user_count == 0 and voice_client is not None:
                    self.logger.info(f"Disconnected from {channel.name} in {guild.name}")
                    await voice_client.disconnect()

            # Only notify users when someone first joins a server
            if previous_count == 0 and s.user_count > 0:
                self.logger.info(f"pinging users for {s.address}")
                for user_id in s.users:
                    user = self.bot.get_user(user_id)
                    if user is None:
                        # Only ping discord if user isn't cached
                        user = await self.bot.fetch_user(user_id)
                    try:
                        notif = self.user_notification_settings[user_id]
                        if notif:
                            dm = await user.create_dm()
                            msg = f"{s.address} just became active!"
                            await dm.send(msg)
                    except KeyError:
                        continue


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Status gets cleared when a channel is empty :3
        channel = before.channel
        if channel is None:
            return

        server = self.get_servers(channel=channel)
        if server is None:
            return

        if len(before.channel.members) == 0:
            self.logger.info("Discord channel now empty, resetting status")
            server.user_count = -1

    @update_statuses.before_loop
    async def wait_until_ready(self):
        await self.bot.wait_until_ready()

    async def update_conf(self):
        self.conf["servers"] = [asdict(s) for s in self.get_all_servers()]
        await self.bot.write_config("mumble", self.conf)

    def get_servers(self, address=None, user=None, channel=None):
        try:
            # Return server for given key. One user may be tracking multiple servers.
            if address:
                return self._servers_by_address[address]
            elif user:
                return self._servers_by_user[user]
            elif channel:
                return  self._servers_by_channel[channel]
            else:
                raise TypeError("A user, address or channel must be given.")
        except KeyError:
            return None

    def get_all_servers(self):
        return [s for s in self._servers_by_address.values()]

    async def server_append(self, server, user=None, channel=None):
        # Add a value to a server and keep all dicts updated
        if server not in self.get_all_servers():
            self._servers_by_address[server.address] = server
        if user:
            server.users.append(user)
            if user not in self._servers_by_user:
                self._servers_by_user[user] = []
            self._servers_by_user[user].append(server)
        if channel:
            # Force an update if a channel is added
            server.user_count = -1
            server.channels.append(channel)
            self._servers_by_channel[channel] = server

        await self.update_conf()

    async def server_remove(self, server, user=None, channel=None):
        if user:
            server.users.remove(user)
            self._servers_by_user[user].remove(server)
            if len(self._servers_by_user[user]) == 0:
                del self._servers_by_user[user]
        if channel:
            server.channels.remove(channel)
            del self._servers_by_channel[channel]
            # Cleanup status and dc from voice if needed
            channel = self.bot.get_channel(channel)
            await channel.edit(status=None)
            c = channel.guild.voice_client
            if c is not None:
                await c.disconnect()
        if not (server.users or server.channels):
            # Stop tracking the server if nothing needs it
            del self._servers_by_address[server.address]

        await self.update_conf()


    @staticmethod
    async def server_is_reachable(server, port=64738):
        # Check for server:port in string to reduce parsing in other functions
        if len(s := server.split(":")) > 1:
            port = int(s[1])
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