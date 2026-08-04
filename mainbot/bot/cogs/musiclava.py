from middleware import logger
import discord
from discord.ext import commands
from typing import Dict, List, Any, Optional
import re
import time
import os

# Lavalink
import lavalink
from lavalink.events import TrackStartEvent, QueueEndEvent, TrackEndEvent
from lavalink.errors import ClientError
from lavalink.filters import LowPass
from lavalink.server import LoadType

SERVER_PASS = os.getenv("SERVER_PASS", "abobas")
SERVER_HOST = os.getenv("SERVER_HOST", "lavalink")
SERVER_PORT = os.getenv("SERVER_PORT", "5000")

class LavalinkVoiceClient(discord.VoiceProtocol):
    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.guild_id = channel.guild.id
        self._destroyed = False

        if not hasattr(self.client, 'lavalink'):
            # Instantiate a client if one doesn't exist.
            # We store it in `self.client` so that it may persist across cog reloads,
            # however this is not mandatory.
            self.client.lavalink = lavalink.Client(client.user.id)
            self.client.lavalink.add_node(host=SERVER_HOST, port=SERVER_PORT, password=SERVER_PASS,
                                          region='us', name='default-node')

        # Create a shortcut to the Lavalink client here.
        self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {
            't': 'VOICE_SERVER_UPDATE',
            'd': data
        }
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        channel_id = data['channel_id']

        if not channel_id:
            await self._destroy()
            return

        self.channel = self.client.get_channel(int(channel_id))

        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {
            't': 'VOICE_STATE_UPDATE',
            'd': data
        }

        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = False,
                      self_mute: bool = False) -> None:
        """
        Connect the bot to the voice channel and create a player_manager
        if it doesn't exist yet.
        """
        # ensure there is a player_manager when creating a new voice_client
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)

    async def disconnect(self, *, force: bool = False) -> None:
        """
        Handles the disconnect.
        Cleans up running player and leaves the voice client.
        """
        player = self.lavalink.player_manager.get(self.channel.guild.id)

        # no need to disconnect if we are not connected
        if not force and not player.is_connected:
            return

        # None means disconnect
        await self.channel.guild.change_voice_state(channel=None)

        # update the channel_id of the player to None
        # this must be done because the on_voice_state_update that would set channel_id
        # to None doesn't get dispatched after the disconnect
        player.channel_id = None
        await self._destroy()

    async def _destroy(self):
        self.cleanup()

        if self._destroyed:
            # Idempotency handling, if `disconnect()` is called, the changed voice state
            # could cause this to run a second time.
            return

        self._destroyed = True

        try:
            await self.lavalink.player_manager.destroy(self.guild_id)
        except ClientError:
            pass


class Musiclava(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        if not hasattr(bot, 'lavalink'):
            bot.lavalink = lavalink.Client(1479444976701149425)
            bot.lavalink.add_node(host=SERVER_HOST, port=SERVER_PORT, password=SERVER_PASS,
                                  region='us', name='default-node')

        self.lavalink = bot.lavalink
        self.lavalink.add_event_hooks(self)

    async def create_player(ctx: commands.Context):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        player = ctx.bot.lavalink.player_manager.create(ctx.guild.id)

        should_connect = ctx.command.name in ('play',)

        voice_client = ctx.voice_client

        if not ctx.author.voice or not ctx.author.voice.channel:
            if voice_client is not None:
                raise commands.CommandInvokeError('Зайдите в голосовой чат')

            raise commands.CommandInvokeError('Зайдите в голосовой чат')

        voice_channel = ctx.author.voice.channel

        if not should_connect:
            raise commands.CommandInvokeError("Музыка не играет")

        permissions = voice_channel.permissions_for(ctx.me)

        if not permissions.connect or not permissions.speak:
            raise commands.CommandInvokeError('Нет права присоединятся и/или говорить')

        if voice_channel.user_limit > 0:
            if len(voice_channel.members) >= voice_channel.user_limit and not ctx.me.guild_permissions.move_members:
                raise commands.CommandInvokeError('Канал заполнен')

        player.store('channel', ctx.channel.id)
        vc = await voice_channel.connect(cls=LavalinkVoiceClient)

        return True

    @lavalink.listener(lavalink.TrackEndEvent)
    async def on_track_end(self, event: lavalink.TrackEndEvent):
        logger.info(f"Трек {event.track} закончился... ")
        event.player.store("last_track", event.track)

    @lavalink.listener(lavalink.QueueEndEvent)
    async def on_queue_end(self, event: lavalink.QueueEndEvent):
        player = event.player
        logger.info(f"Очередь пуста...")
        if not player.fetch("is_jam"):
            return
        logger.info(f"Режим джема включён")

        last_track = player.fetch("last_track")
        if last_track is None:
            return

        regexp = re.compile(r"[?&]v=([A-Za-z0-9_-]{11})")

        match = regexp.search(last_track.uri)
        if not match:
            return

        video_id = match.group(1)

        results = await player.node.get_tracks(
            f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
        )

        if not results or not results.tracks:
            return

        for track in results.tracks[1:]: # workaround because of yt
            track.extra["requester"] = last_track.extra["requester"]
            player.add(track)

        await player.play()

    # For syncing
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if (
            self.bot.user.mentioned_in(message)
            and message.content.strip() == f"<@{self.bot.user.id}> sync"
        ):
            await self.process_message(message)

    async def process_message(self, message):
        synced = await self.bot.tree.sync()
        print(synced)
        await message.channel.send(f"Successfully synced {len(synced)} command(s).")

    @discord.app_commands.command(name="queue", description="Получить очередь")
    async def queue(self, interaction: discord.Interaction):
        await interaction.response.defer()

        player = self.bot.lavalink.player_manager.create(guild_id=interaction.guild_id)

        embed = discord.Embed(color=discord.Color.blurple())
        embed.title = 'Текущая очередь:'
        embed_lines = []

        if player.is_playing:
            embed_lines.append("Сейчас играет: **{}**\n".format(player.current.title))

        for i, track in enumerate(player.queue, start=1):
            embed_lines.append("{}. {}".format(i, track.title))

        embed.description = "\n".join(embed_lines) or "Пустая очередь"

        return await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="play", description="Включить музыку")
    async def play(self, interaction: discord.Interaction, query: str, is_jam: bool):
        await interaction.response.defer()

        if not interaction.user.voice:
            return await interaction.followup.send("Зайди в голосовой канал")

        voice_channel = interaction.user.voice.channel

        # Подключаемся если бот ещё не в войсе
        if not interaction.guild.voice_client:
            await voice_channel.connect(cls=LavalinkVoiceClient)

        # Создаём/получаем player
        player = self.bot.lavalink.player_manager.create(interaction.guild.id)

        # Сохраняем текстовый канал
        player.store("channel", interaction.channel.id)
        player.store("is_jam", is_jam)

        url_rx = re.compile(r'https?://(?:www\.)?.+')

        query = query.strip('<>')

        # Если не ссылка — ищем через YouTube
        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        # Получаем треки
        results = await player.node.get_tracks(query)

        embed = discord.Embed(color=discord.Color.blurple())

        if results.load_type == LoadType.EMPTY:
            return await interaction.followup.send("Треки не найдены")

        elif results.load_type == LoadType.PLAYLIST:

            tracks = results.tracks

            for track in tracks:
                track.extra["requester"] = interaction.user.id
                player.add(track=track)

            embed.title = 'Добавлен плейлист'
            embed.description = (
                f'{results.playlist_info.name} - {len(tracks)} треков'
            )

        else:
            track = results.tracks[0]

            track.extra["requester"] = interaction.user.id

            player.add(track=track)

            embed.title = 'Добавлен трек'
            embed.description = f'[{track.title}]({track.uri})'

        await interaction.followup.send(embed=embed)

        # Запускаем только если ничего не играет
        if not player.is_playing:
            await player.play()

    @discord.app_commands.command(name="skip", description="Пропустить трек")
    async def skip(self, interaction: discord.Interaction):

        player = self.bot.lavalink.player_manager.get(interaction.guild.id)

        if not player or not player.is_playing:
            return await interaction.response.send_message(
                "Сейчас ничего не играет",
                ephemeral=True
            )

        await interaction.response.send_message("Трек пропущен")

        await player.skip()

    @discord.app_commands.command(name="stop", description="Остановить музыку")
    async def stop(self, interaction: discord.Interaction):

        player = self.bot.lavalink.player_manager.get(interaction.guild.id)

        if not player:
            return await interaction.response.send_message(
                "Плеер не найден",
                ephemeral=True
            )

        player.queue.clear()

        await player.stop()

        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect(force=True)

        await interaction.response.send_message("Музыка остановлена")

    @commands.command(aliases=['lp'])
    @commands.check(create_player)
    async def lowpass(self, ctx, strength: float):
        """ Sets the strength of the low pass filter. """
        # Get the player for this guild from cache.
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        # This enforces that strength should be a minimum of 0.
        # There's no upper limit on this filter.
        strength = max(0.0, strength)

        # Even though there's no upper limit, we will enforce one anyway to prevent
        # extreme values from being entered. This will enforce a maximum of 100.
        strength = min(100, strength)

        embed = discord.Embed(color=discord.Color.blurple(), title='Low Pass Filter')

        # A strength of 0 effectively means this filter won't function, so we can disable it.
        if strength == 0.0:
            await player.remove_filter('lowpass')
            embed.description = 'Disabled **Low Pass Filter**'
            return await ctx.send(embed=embed)

        # Lets create our filter.
        low_pass = LowPass()
        low_pass.update(smoothing=strength)  # Set the filter strength to the user's desired level.

        # This applies our filter. If the filter is already enabled on the player, then this will
        # just overwrite the filter with the new values.
        await player.set_filter(low_pass)

        embed.description = f'Set **Low Pass Filter** strength to {strength}.'
        await ctx.send(embed=embed)

    @commands.command(aliases=['dc'])
    @commands.check(create_player)
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        # The necessary voice channel checks are handled in "create_player."
        # We don't need to duplicate code checking them again.

        # Clear the queue to ensure old tracks don't start playing
        # when someone else queues something.
        player.queue.clear()
        # Stop the current track so Lavalink consumes less resources.
        await player.stop()
        # Disconnect from the voice channel.
        await ctx.voice_client.disconnect(force=True)
        await ctx.send('Отключён')


async def setup(bot):
    await bot.add_cog(Musiclava(bot))

