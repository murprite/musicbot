from __future__ import annotations
import asyncio
from typing import Dict, List, Any, Optional

from middleware import logger
import discord
from discord.ext import commands
import yt_dlp

COG_TYPE="Music"

# yt-dlp конфиг с поддержкой поиска и node
YTDL_OPTIONS: Dict[str, Any] = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "remote_components": {
        "ejs:github": "github"
    },
    # "js_runtimes": {
    #     "deno": {'path': "/usr/local/bin/deno"}
    # }

}

FFMPEG_OPTIONS: Dict[str, str] = {
    "options": "-vn",
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: Dict[int, List[Dict[str, str]]] = {}
        logger.info(text="Инициализация Music", log_type="cog")

    @discord.app_commands.command(name="queue", description="Посмотреть очередь")
    async def getQueue(self, interaction: discord.Interaction):
        safeQueue = "\n".join(
            track["title"]
            for guild_queue in self.queue.values()
            for track in guild_queue
        ) or "❌ Пустая очередь"

        logger.info(text=f"Текущая очередь:\n{safeQueue}", log_type="cog")

        await interaction.response.send_message(f"Текущая очередь:\n{safeQueue}")


    async def connect_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if not interaction.user.voice or not interaction.user.voice.channel:
            logger.warning(
                text=f"Юзер не в голосовом канале.\nЮзер: {interaction.user.voice}. Канал: {interaction.user.voice.channel}",
                log_type="cog"
            )
            await interaction.response.send_message("❌ Вы должны быть в голосовом канале.", ephemeral=True)
            return None

        voice_client = interaction.guild.voice_client
        if voice_client is None:
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except Exception as e:
                logger.error(text=f"Не удалось подключиться\nОшибка: {e}", log_type="cog")
                await interaction.response.send_message(f"❌ Не удалось подключиться: {e}", ephemeral=True)
                return None
        return voice_client

    async def get_audio(self, query: str, interaction: discord.Interaction) -> Optional[Dict[str, Any]]:
        try:
            logger.info(
                text=f"Поиск по ключевому слову {query}...",
                log_type="cog"
            )
            if query.startswith("http"):
                data = ytdl.extract_info(query, download=False);
                logger.info(
                    text=f"Предоставлена ссылка {query}",
                    log_type="cog"
                )
            else:
                data = ytdl.extract_info(f"ytsearch:{query}", download=False)

                if "entries" in data:
                    title = data["entries"][0]['title']
                    data = data["entries"][0]

                    logger.info(
                        text=f"Найдено {title}",
                        log_type="cog"
                    )
                else:
                    logger.warning(
                        text=f"Ничего не найдено",
                        log_type="cog"
                    )
            return data
        except Exception as e:
            logger.error(
                text=f"Ошибка при получении аудио {e}",
                log_type="cog"
            )
            await interaction.followup.send(f":x: Ошибка при получении аудио")
            return None

    async def play_next(self, guild_id: int, channel: discord.TextChannel):

        if guild_id not in self.queue or not self.queue[guild_id]:
            await channel.send("📭 Очередь пуста.")
            return

        track = self.queue[guild_id].pop(0)

        voice_client = channel.guild.voice_client
        if not voice_client:
            return

        await self.start_track(voice_client, guild_id, channel, track)

    @discord.app_commands.command(name="play", description="Воспроизвести трек или добавить в очередь")
    async def play(self, interaction: discord.Interaction, query: str):
        voice_client = await self.connect_voice(interaction)

        if voice_client is None:
            return

        guild_id = interaction.guild.id
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        await interaction.response.defer()
        data = await self.get_audio(query, interaction)

        if not data:
            await interaction.followup.send("❌ Не удалось найти трек.")
            return

        stream_url = data["url"]
        title = data.get("title", "Неизвестный трек")

        if voice_client.is_playing():
            self.queue[guild_id].append({"title" : title, "stream_url" : stream_url})
            await interaction.followup.send(f"➕ Трек {title} добавлен в очередь.")
            return

        try:
            source = discord.FFmpegOpusAudio(
                stream_url,
                executable="ffmpeg",
                **FFMPEG_OPTIONS
            )
        except Exception:
            await interaction.followup.send("❌ Ошибка воспроизведения.")
            return

        await interaction.followup.send(f"▶️ Сейчас играет: **{title}**")
        def after_playing(error):
            logger.info(text=f"Включаем следующий трек...", log_type="cog")
            fut = asyncio.run_coroutine_threadsafe(self.play_next(guild_id, interaction.channel), self.bot.loop)
            try:
                fut.result()
            except Exception:
                pass

        voice_client.play(source, after=after_playing)

    @discord.app_commands.command(name="skip", description="Пропустить текущий трек")
    async def skip(self, interaction: discord.Interaction):
        logger.info(
            text=f"Скип...",
            log_type="cog"
        )
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

    async def start_track(self, voice_client, guild_id, channel, track):
        source = discord.FFmpegOpusAudio(
            track["stream_url"],
            executable="ffmpeg",
            **FFMPEG_OPTIONS
        )

        await channel.send(f"▶️ Сейчас играет: **{track['title']}**")

        def after_playing(error):
            asyncio.run_coroutine_threadsafe(
                self.play_next(guild_id, channel),
                self.bot.loop
            )

        voice_client.play(source, after=after_playing)

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))