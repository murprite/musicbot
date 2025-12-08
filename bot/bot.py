from typing import Optional
import logging

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

    Поддерживает передачу token, prefix, intents и help_command в конструктор.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        prefix: Optional[str] = None,
        intents: Optional[Intents] = None,
        help_command: Optional[commands.HelpCommand] = None,
    ) -> None:
        """
        :param token: Токен бота (если None — берётся из settings.BOT_TOKEN).
        :param prefix: Префикс команд (если None — берётся из settings.PREFIX или '!').
        :param intents: Intents (если None — создаются стандартные + privileged).
        :param help_command: Кастомная команда помощи.
        """
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

        # Сохраняем токен и хранилище
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
        Инициализация бота: логгер, cogs, логирование discord.py.
        """
        logger.setup(start=True)
        logger.info(text="Настройка бота...", log_type="SYSTEM")

        await self.load_cogs()

        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
        )
        logging.getLogger("discord").setLevel(logging.INFO)

    async def load_cogs(self) -> None:
        """
        Загрузить все модули cogs.
        """
        cogs: list[str] = [
            "cogs.events",
            "cogs.moderation",
            "cogs.blacklist",
            "cogs.reminders",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Загружен cog: {cog}", log_type="COGS")
            except Exception as e:
                logger.error(f"Ошибка загрузки {cog}: {e}", log_type="COGS")

    async def start_bot(self, token: Optional[str] = None) -> None:
        """
        Запуск бота с использованием сохранённого токена или переданного.

        :param token: Токен бота (если None — используется self.token).
        """
        use_token: Optional[str] = token or self.token
        if not use_token:
            error: str = "BOT_TOKEN не задан (ни в конструкторе, ни в settings)"
            logger.error(error)
            raise ValueError(error)

        logger.info(text="Запуск бота...", log_type="START")
        await self.start(use_token)


# Глобальный экземпляр — МОЖНО ПЕРЕДАВАТЬ token/prefix ПРЯМО ЗДЕСЬ
discbot: Bot = Bot(
    token=settings.BOT_TOKEN,   # кастомный токен
    prefix=settings.PREFIX,   # кастомный префикс
)
