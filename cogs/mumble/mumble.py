import discord
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

        #Force an update on first load
        self.user_count = -1

    async def ping(self):
        self.user_count = await fetch_user_count(self.address, self.port)

class Mumble(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.logger
        self.conf = {}
        self.user_notification_settings = {}
        self.servers_by_user = {}
        self.servers_by_channel = {}
        self.servers_by_address = {}

    async def cog_load(self):
        default_config = {
            "task_interval": 5,
            "servers": [],
            "user_notifications" : {}
        }
        self.conf = await self.bot.get_config("mumble", default_config)
        all_servers = [MumbleServer(**s) for s in self.conf["servers"]]
        self.user_notification_settings = self.conf["user_notifications"]


        self.update_statuses.start()
        self.update_statuses.change_interval(seconds=self.conf["task_interval"])

        for server in all_servers:
            # Build dicts indexed by channel, address and user
            # servers_by_address will always contain all servers
            self.servers_by_address[server.address] = server
            for user in server.users:
                if user not in self.servers_by_user:
                    self.servers_by_user[user] = []
                self.servers_by_user[user].append(server)
            for channel in server.channels:
                self.servers_by_channel[channel] = server

    async def cog_unload(self):
        self.logger.info("Unloading Mumble Status, clearing channel status")
        for channel in self.servers_by_channel:
            await self.bot.get_channel(channel).edit(status=None)


    @commands.group(invoke_without_command=True)
    async def mumble(self, ctx):
        await ctx.send("No subcommand (WRITE USAGE)")

    @mumble.command()
    async def interval(self, ctx, interval):
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
        #Ensure channel exists and server is reachable before writing to config
        try:
            if not isinstance(self.bot.get_channel(int(channel_id)), discord.VoiceChannel):
                await ctx.send(f"{channel_id} is not a valid voice channel.")
                return
        except ValueError:
            await ctx.send("Discord channel IDs must be integers.")

        # Ensure that duplicate channels can't be added
        if server_address in self.servers_by_address:
            server = self.servers_by_address[server_address]
            if channel_id in server.channels:
                await ctx.send(f"Channel is already displaying status of {server_address}")
                return
        else:
            connection_test = await self.server_is_reachable(server_address)
            if not connection_test:
                await ctx.send("Server does not appear to be reachable, try again.")
                return
            server = MumbleServer(server_address)
            self.servers_by_address[server_address] = server

        server.channels.append(int(channel_id))
        self.servers_by_channel[channel_id] = server
        # Force an update
        server.user_count = -1
        await self.update_conf()
        await ctx.send("Added status to channel")
        self.logger.info(f"Tracking added for {server_address} on channel {channel_id}")



    @status.command()
    async def disable(self, ctx, channel_id):
        try:
            channel_id = int(channel_id)
        except ValueError:
            await ctx.send("Invalid channel ID")
            return
        if channel_id not in self.servers_by_channel:
            await ctx.send("That channel isn't tracking any servers")
            return
        server = self.servers_by_channel[channel_id]
        server.channels.remove(channel_id)
        del self.servers_by_channel[channel_id]
        self.logger.info(f"Tracking removed from channel {channel_id}")
        # Remove the server if it is no longer needed
        if not (server.channels or server.users):
            del self.servers_by_address[server.address]
        await self.update_conf()

        # Cleanup status and dc from voice if needed
        channel = self.bot.get_channel(channel_id)
        await channel.edit(status=None)
        c = channel.guild.voice_client
        if c is not None:
            await c.disconnect()

    @mumble.group(invoke_without_command=True)
    async def untrack(self, ctx, server_address):
        user_id = ctx.message.author.id
        try:
            server = self.servers_by_address[server_address]
            self.servers_by_user[user_id].remove(server)
            server.users.remove(user_id)
            if len(self.servers_by_user[user_id]) == 0:
                del self.servers_by_user[user_id]
            # Remove the server if it is no longer needed
            if not (server.channels or server.users):
                del self.servers_by_address[server.address]
            await self.update_conf()
            await ctx.send(f"{server.address} is no longer being tracked.")
        except (ValueError, KeyError):
            await ctx.send("You weren't tracking that server")



    @mumble.group(invoke_without_command=True)
    async def track(self, ctx, server_address):
        user_id = ctx.message.author.id
        # Check server is valid before writing to config
        if server_address in self.servers_by_address:
            server = self.servers_by_address[server_address]
            if user_id in server.users:
                await ctx.send("You're already tracking that server.")
                return
        else:
            connection_test = await self.server_is_reachable(server_address)
            if not connection_test:
                await ctx.send("Server does not appear to be reachable, try again.")
                return
            server = MumbleServer(server_address)
        self.servers_by_address[server_address] = server
        if user_id not in self.servers_by_user:
            self.servers_by_user[user_id] = []
        self.servers_by_user[user_id].append(server)
        server.users.append(user_id)
        await self.update_conf()
        msg = f"Added tracking for {server_address}"
        # Warn user if their notifications are off when adding a server.
        if user_id not in self.user_notification_settings:
            msg += ", but you haven't configured notifications."
            msg += "\nConsider running `!track on`"
            await ctx.send(msg)
            return
        notif = self.user_notification_settings[user_id]
        if notif == "off":
            msg += ", but your notifications are currently off."
            await ctx.send(msg)
            return
        await ctx.send(msg)

    @track.command()
    async def on(self, ctx):
        user_id = ctx.message.author.id
        self.user_notification_settings[user_id] = "on"
        await self.update_conf()
        await ctx.send("Opted in to Mumble notifications")

    @track.command()
    async def off(self, ctx):
        user_id = ctx.message.author.id
        self.user_notification_settings[user_id] = "off"
        await self.update_conf()
        await ctx.send("Opted out of Mumble notifications")

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

        for _, s in self.servers_by_address.items():
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
                        if notif == "on":
                            dm = await user.create_dm()
                            msg = f"{s.address} just became active!"
                            await dm.send(msg)
                    except KeyError:
                        continue


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Status gets cleared when a channel is empty
        channel = before.channel
        if channel is None:
            return

        if channel.id in self.servers_by_channel and len(before.channel.members) == 0:
            self.logger.info("Discord channel now empty, resetting status")
            self.servers_by_channel[channel.id].user_count = -1

    @update_statuses.before_loop
    async def wait_until_ready(self):
        await self.bot.wait_until_ready()

    async def update_conf(self):
        self.conf["servers"] = [asdict(s) for _, s in self.servers_by_address.items()]
        await self.bot.write_config("mumble", self.conf)

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