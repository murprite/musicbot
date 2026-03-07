from __future__ import annotations
import asyncio
from typing import Dict, List, Any, Optional

import discord
from discord.ext import commands
import yt_dlp

# yt-dlp конфиг с поддержкой поиска и node
YTDL_OPTIONS: Dict[str, Any] = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",
    "js_runtimes": {
        "node": {"path": "/usr/bin/node"}
    },
    "remote_components": {
        "ejs:github": "github"
    },
    "extractor_args": {
        "youtube": {
            "player_client": ["web_music"]
        }
    }
}

FFMPEG_OPTIONS: Dict[str, str] = {
    "options": "-vn",
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: Dict[int, List[str]] = {}  # guild_id -> список запросов

    async def connect_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы должны быть в голосовом канале.", ephemeral=True)
            return None

        voice_client = interaction.guild.voice_client
        if voice_client is None:
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.response.send_message(f"❌ Не удалось подключиться: {e}", ephemeral=True)
                return None

        return voice_client

    async def get_audio(self, query: str) -> Optional[Dict[str, Any]]:
        try:
            if query.startswith("http"):
                data = ytdl.extract_info(query, download=False)
            else:
                data = ytdl.extract_info(f"ytsearch:{query}", download=False)
                if "entries" in data:
                    data = data["entries"][0]
            return data
        except Exception:
            return None

    async def play_next(self, guild_id: int, channel: discord.TextChannel) -> None:
        if guild_id not in self.queue or not self.queue[guild_id]:
            await channel.send("📭 Очередь пуста.")
            return

        next_query = self.queue[guild_id].pop(0)
        # создаем фиктивный interaction для play
        class DummyInteraction:
            guild = channel.guild
            user = channel.guild.me
            response = type('Resp', (), {"send_message": lambda self, msg, ephemeral=False: asyncio.create_task(channel.send(msg))})()

        await self.play(DummyInteraction(), next_query)

    @discord.app_commands.command(name="play", description="Воспроизвести трек или добавить в очередь")
    async def play(self, interaction: discord.Interaction, query: str):
        voice_client = await self.connect_voice(interaction)
        if voice_client is None:
            return

        guild_id = interaction.guild.id
        if guild_id not in self.queue:
            self.queue[guild_id] = []

        if voice_client.is_playing():
            self.queue[guild_id].append(query)
            await interaction.response.send_message("➕ Трек добавлен в очередь.")
            return

        data = await self.get_audio(query)
        if not data:
            await interaction.response.send_message("❌ Не удалось найти трек.")
            return

        stream_url = data["url"]
        title = data.get("title", "Неизвестный трек")

        try:
            source = discord.FFmpegOpusAudio(
                stream_url,
                executable="ffmpeg",
                **FFMPEG_OPTIONS
            )
        except Exception:
            await interaction.response.send_message("❌ Ошибка воспроизведения.")
            return

        def after_playing(error):
            fut = asyncio.run_coroutine_threadsafe(self.play_next(guild_id, interaction.channel), self.bot.loop)
            try:
                fut.result()
            except Exception:
                pass

        voice_client.play(source, after=after_playing)
        await interaction.response.send_message(f"▶️ Сейчас играет: **{title}**")

    @discord.app_commands.command(name="skip", description="Пропустить текущий трек")
    async def skip(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message("❌ Сейчас ничего не играет.", ephemeral=True)
            return
        voice_client.stop()
        await interaction.response.send_message("⏭️ Трек пропущен.")

    @discord.app_commands.command(name="stop", description="Остановить музыку и очистить очередь")
    async def stop(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client:
            guild_id = interaction.guild.id
            self.queue[guild_id] = []
            if voice_client.is_playing():
                voice_client.stop()
        await interaction.response.send_message("⏹️ Музыка остановлена.")

    @discord.app_commands.command(name="leave", description="Отключить бота от голосового канала")
    async def leave(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
        await interaction.response.send_message("👋 Бот вышел из голосового канала.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))