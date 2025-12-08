from typing import Optional

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
    """

    def __init__(
        self,
        token: Optional[str] = None,
        prefix: Optional[str] = None,
        intents: Optional[Intents] = None,
        help_command: Optional[commands.HelpCommand] = None,
    ) -> None:
        # Intents по умолчанию
        if intents is None:
            intents = Intents.default()
            intents.guilds = True
            intents.message_content = True  # Требует включения в Developer Portal
            intents.members = True

        # Префикс по умолчанию
        command_prefix: str = prefix or getattr(settings, "PREFIX", "!")

        # Help-команда по умолчанию
        if help_command is None:
            help_command = MyHelpCommand()

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
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(text=f"Загружен cog: {cog}", log_type="COGS")
            except Exception as e:
                logger.error(text=f"Ошибка загрузки {cog}: {e!r}", log_type="COGS")

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


discbot: Bot = Bot(
    token=settings.BOT_TOKEN,
    prefix=settings.PREFIX,
)
