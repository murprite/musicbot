from __future__ import annotations
import asyncio
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands
import yt_dlp

YTDL_FORMAT_OPTIONS: Dict[str, Any] = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
}

FFMPEG_OPTIONS: Dict[str, str] = {
    "options": "-vn",
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
}

ytdl: yt_dlp.YoutubeDL = yt_dlp.YoutubeDL(YTDL_FORMAT_OPTIONS)


class Music(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.queue: Dict[int, List[str]] = {}

    async def connect_to_voice(self, ctx: commands.Context) -> Optional[discord.VoiceClient]:
        if ctx.author.voice is None:
            await ctx.send("❌ Вы должны находиться в голосовом канале.")
            return None

        voice_client: Optional[discord.VoiceClient] = ctx.voice_client

        if voice_client is None:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except Exception:
                await ctx.send("❌ Не удалось подключиться к голосовому каналу.")
                return None

        return voice_client

    async def get_audio_data(self, query: str) -> Optional[Dict[str, Any]]:
        """Получает данные аудио по URL или поисковому запросу."""
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

    async def play_next(self, ctx: commands.Context) -> None:
        guild_id = ctx.guild.id
        voice_client = ctx.voice_client

        if guild_id in self.queue and self.queue[guild_id]:
            query = self.queue[guild_id].pop(0)
            await self.play(ctx, query=query)
        else:
            await ctx.send("📭 Очередь пуста.")

    @commands.command(name="play")
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        voice_client = await self.connect_to_voice(ctx)
        if voice_client is None:
            return

        guild_id = ctx.guild.id

        if guild_id not in self.queue:
            self.queue[guild_id] = []

        if voice_client.is_playing():
            self.queue[guild_id].append(query)
            await ctx.send("➕ Трек добавлен в очередь.")
            return

        data = await self.get_audio_data(query)

        if data is None:
            await ctx.send("❌ Не удалось найти трек.")
            return

        stream_url: str = data["url"]
        title: str = data.get("title", "Неизвестный трек")

        try:
            source = await discord.FFmpegOpusAudio.from_probe(
                stream_url,
                executable="ffmpeg",
                **FFMPEG_OPTIONS
            )
        except Exception:
            await ctx.send("❌ Ошибка воспроизведения.")
            return

        def after_playing(error):
            fut = asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)
            try:
                fut.result()
            except Exception:
                pass

        voice_client.play(source, after=after_playing)

        await ctx.send(f"▶️ Сейчас играет: **{title}**")

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context) -> None:
        voice_client: Optional[discord.VoiceClient] = ctx.voice_client

        if voice_client is None or not voice_client.is_playing():
            await ctx.send("❌ Сейчас ничего не играет.")
            return

        voice_client.stop()
        await ctx.send("⏭️ Трек пропущен.")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context) -> None:
        voice_client: Optional[discord.VoiceClient] = ctx.voice_client

        if voice_client is None:
            await ctx.send("❌ Бот не подключён.")
            return

        guild_id = ctx.guild.id
        self.queue[guild_id] = []

        if voice_client.is_playing():
            voice_client.stop()

        await ctx.send("⏹️ Музыка остановлена.")

    @commands.command(name="leave")
    async def leave(self, ctx: commands.Context) -> None:
        voice_client: Optional[discord.VoiceClient] = ctx.voice_client

        if voice_client is None:
            await ctx.send("❌ Бот не в голосовом канале.")
            return

        await voice_client.disconnect()
        await ctx.send("👋 Бот вышел из голосового канала.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))