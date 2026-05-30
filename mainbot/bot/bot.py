from typing import Optional

import discord
from discord import Intents
from discord.ext import commands

from configs import settings
from .help import MyHelpCommand
from middleware.loggers import logger
from .storage import storage

__all__ = ("Bot", "discbot")


class Bot(commands.Bot):
    """
    Основной класс Discord-бота с методами настройки и запуска.
    Поддерживает префиксные и slash-команды.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        prefix: Optional[str] = None,
        intents: Optional[Intents] = None,
        help_command: Optional[commands.HelpCommand] = None,
    ) -> None:
        if intents is None:
            intents = Intents.default()
            intents.guilds = True
            intents.message_content = True
            intents.members = True
            intents.presences = True
            intents.voice_states = True

        command_prefix: str = prefix or getattr(settings, "PREFIX", "!")

        if help_command is None:
            help_command = MyHelpCommand()

        # ВАЖНО: tree создаёт сам commands.Bot, мы его не переопределяем
        super().__init__(
            command_prefix=command_prefix,
            intents=intents,
            help_command=help_command,
        )

        self._token: Optional[str] = token
        self.storage = storage  # type: ignore[assignment]

    @property
    def token(self) -> Optional[str]:
        """
        Токен бота: сначала из конструктора, затем из settings.
        """
        return self._token or settings.BOT_TOKEN

    async def setup(self) -> None:
        """
        Инициализация бота: логгер и загрузка cogs.
        """
        logger.setup(start=True)
        logger.info(text="Настройка бота...", log_type="SYSTEM")

        await self.load_cogs()

    async def load_cogs(self) -> None:
        """
        Загрузить все модули cogs.
        """
        logger.info(text="Начинаю загрузку cogs...", log_type="COGS")

        cogs: list[str] = [
            "bot.cogs.events",
            "bot.cogs.moderation",
            "bot.cogs.blacklist",
            "bot.cogs.reminders",
            "bot.cogs.slash",
            "bot.cogs.musiclava",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(text=f"Загружен cog: {cog}", log_type="COGS")
            except Exception as e:
                logger.error(text=f"Ошибка загрузки {cog}: {e!r}", log_type="COGS")

    async def setup_hook(self) -> None:
        """
        Хук discord.py 2.x: вызывается перед подключением к Gateway.
        Здесь синхронизируем slash-команды.

        """
        await self.tree.sync()
        logger.info(text="Slash-команды синхронизированы", log_type="SYSTEM")

    async def start_bot(self, token: Optional[str] = None) -> None:
        """
        Запуск бота с использованием сохранённого токена или переданного.
        """
        use_token: Optional[str] = token or self.token
        if not use_token:
            error: str = "BOT_TOKEN не задан (ни в конструкторе, ни в settings)"
            logger.error(text=error, log_type="START")
            raise ValueError(error)

        logger.info(text="Запуск бота...", log_type="START")
        await self.start(use_token)

    @staticmethod
    async def on_command(ctx: commands.Context) -> None:
        """
        Глобальное логирование всех вызванных префиксных команд.
        """
        logger.info(
            text=(
                f"Команда: {ctx.command} | Автор: {ctx.author} | "
                f"Гильдия: {ctx.guild} | Сообщение: {ctx.message.content}"
            ),
            log_type="COMMAND",
            user=str(ctx.author),
        )
        


discbot: Bot = Bot(
    token=settings.BOT_TOKEN,
    prefix=settings.PREFIX,
)
