from __future__ import annotations
import asyncio
from typing import Dict, List, Any, Optional

from vkpymusic.vk_api import VkApiException

from middleware import logger
import discord
from discord.ext import commands
import yt_dlp

from vkpymusic import TokenReceiver, Service

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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: Dict[int, List[Dict[str, str]]] = {}
        self.vk_token = None
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

    async def __get_token(self):
        logger.warning(
            text=f"Achtung, ввод логина/пароля от VK для получения токена",
            log_type="cog"
        )

        login = input("Логин:")
        password = input("Пароль:")

        tokenReciever = TokenReceiver(login, password)
        try:
            if tokenReciever.auth():
                logger.info(
                    text=f"Получен токен!",
                    log_type="cog"
                )
                self.vk_token = tokenReciever.get_token()
                print(self.vk_token)
        except VkApiException:
            logger.info(
                text=f"Ошибка при получении токена",
                log_type="cog"
            )
        return self.vk_token

    @discord.app_commands.command(name="vkplaylist", description="Играть плейлист на основе этой песни")
    async def vk_playlist_l(self, interaction: discord.Interaction):
        await interaction.response.defer()
        TIME = "bebra"
        self.vk_token = TIME
        if self.vk_token is None:
            await self.__get_token()

        service = Service(USER_AGENT, self.vk_token)
        playlist = await service.get_recommendations_async(song_id=2001897990_146897990)
        voice_client = await self.connect_voice(interaction)
        guild_id = interaction.guild.id
        title = playlist[0].title
        author = playlist[0].artist

        data = await self.get_audio(author + " - " + title, interaction)

        if not data:
            await interaction.followup.send("❌ Не удалось найти трек.")
            return

        def after_playing(error):
            logger.info(text=f"Включаем следующий трек...", log_type="cog")
            fut = asyncio.run_coroutine_threadsafe(self.play_next(guild_id, interaction.channel), self.bot.loop)
            try:
                fut.result()
            except Exception:
                pass

        stream_url = data["url"]

        source = discord.FFmpegOpusAudio(
            stream_url,
            executable="ffmpeg",
            **FFMPEG_OPTIONS
        )

        self.queue[guild_id].append({"title" : playlist[0].title, "stream_url" : stream_url})

        await interaction.response.send_message(f"{playlist[0].title} - {playlist[0].artist}", ephemeral=True)

        voice_client.play(source, after=after_playing)

    @discord.app_commands.command(name="vkplaylist_l", description="Использовать плейлист VK по алгоритмам")
    async def vk_playlist(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if self.vk_token is None:
            await self.__get_token()

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

    #---------------------------

    @discord.app_commands.command(name="test", description="Плейлист")
    async def test(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.vk_token = "vk1.a.RG196vmO0JXFjKT3-VT31g9L9yvJX5Uq2GHMQol580VObfE-FIchFXFwgvIyy-GcgghlPXpGXamD2yg1z6FHx3oMeIQhe-bHhStyqgcjy8y-_eKwlsEfu6GK8SOyI8v17tmQJBxe8bj3f3Q-vWYBOx5_1MwY6-eKySztj0ggWo74epiCD8U5uc5uLovKjDelQYGZDQdxYtaCqQnXa9ROUg"

        if self.vk_token is None:
            await self.__get_token()

        service = Service(USER_AGENT, self.vk_token)
        playlist = service.get_songs_by_userid(267041638, 10)
        print(playlist)


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