from pathlib import Path
from functools import wraps
from sys import stderr as console
from inspect import iscoroutinefunction
from typing import Any, Callable, Optional, TypeVar, cast, Final

from loguru import logger as logs

from configs.config import settings  # экземпляр настроек

__all__ = ("logger", "log")

F = TypeVar("F", bound=Callable[..., Any])


class _Logger:
    """
    Обёртка над loguru с:
    - единым форматом сообщений;
    - выводом в консоль;
    - файлами в ./logs:
        - logs/bot.log      — все уровни (DEBUG+)
        - logs/debug.log    — только DEBUG
        - logs/info.log     — только INFO
        - logs/warning.log  — только WARNING
        - logs/error.log    — только ERROR
        - logs/critical.log — только CRITICAL
    """

    _log_format: Final[str] = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> <red>|</red> "
        "<blue>{extra[system]}-{extra[log_type]}</blue> <red>|</red> "
        "{extra[user]} <red>|</red> <level>{message}</level>"
    )

    def __init__(self, system_name: str = "DISCORD_BOT") -> None:
        self.system_name: str = system_name
        self._setup_done: bool = False

    def setup(self, start: bool = True) -> None:
        """
        Настроить loguru: консоль + файлы в каталоге logs/.
        Вызывать один раз при старте приложения.
        """
        if self._setup_done:
            return

        logs.remove()

        # Директория для логов
        log_dir: Path = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Консольный вывод
        logs.add(
            sink=console,
            format=self._log_format,
            colorize=True,
            level=settings.LOG_LEVEL.upper(),
        )

        # Общий лог (все уровни)
        logs.add(
            sink=log_dir / "bot.log",
            rotation="100 MB",
            retention="7 days",
            format=self._log_format,
            level="DEBUG",
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

        # Отдельные файлы по уровням
        for level_name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            logs.add(
                sink=log_dir / f"{level_name.lower()}.log",
                rotation="10 MB",
                retention="7 days",
                format=self._log_format,
                level=level_name,
                filter=lambda rec, lvl=level_name: rec["level"].name == lvl,
                enqueue=True,
            )

        self._setup_done = True

        if start:
            self.log_entry(
                level="INFO",
                text="Запуск Discord‑бота...",
                log_type="START",
            )

    @staticmethod
    def format_user(user: Optional[str] = None) -> str:
        """
        Вернуть строку пользователя для логов.
        """
        return user or "@System"

    def log_entry(
        self,
        level: str,
        text: str,
        log_type: str = "BOT",
        user: Optional[str] = None,
    ) -> None:
        """
        Записать строку лога.

        :param level: Уровень (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        :param text: Текст сообщения.
        :param log_type: Категория/подсистема (например, SYSTEM, COGS, DB).
        :param user: Опционально — строка пользователя.
        """
        actual_user: str = self.format_user(user)
        logs.bind(
            system=self.system_name,
            user=actual_user,
            log_type=log_type,
        ).log(level, text)

    def log(
        self,
        level: str = "INFO",
        log_type: str = "",
        text: Optional[str] = None,
    ) -> Callable[[F], F]:
        """
        Декоратор для логирования вызовов функций/корутин.

        :param level: Уровень сообщения.
        :param log_type: Категория (например, HANDLER, TASK).
        :param text: Кастомный текст (по умолчанию 'Вызов <имя функции>').
        """

        def decorator(func: F) -> F:
            is_coroutine: bool = iscoroutinefunction(func)
            action_text: str = text or f"Вызов {func.__name__}"

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                self.log_entry(level=level, text=f"[START] {action_text}", log_type=log_type)
                try:
                    result: Any = func(*args, **kwargs)
                    self.log_entry(level=level, text=f"[SUCCESS] {action_text}", log_type=log_type)
                    return result
                except Exception as e:
                    self.log_entry(
                        level="ERROR",
                        text=f"[ERROR] {action_text} | Exception: {e!r}",
                        log_type=log_type,
                    )
                    raise

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                self.log_entry(level=level, text=f"[START] {action_text}", log_type=log_type)
                try:
                    result: Any = await func(*args, **kwargs)
                    self.log_entry(level=level, text=f"[SUCCESS] {action_text}", log_type=log_type)
                    return result
                except Exception as e:
                    self.log_entry(
                        level="ERROR",
                        text=f"[ERROR] {action_text} | Exception: {e!r}",
                        log_type=log_type,
                    )
                    raise

            return cast(F, async_wrapper if is_coroutine else sync_wrapper)

        return decorator

    def debug(self, text: str, log_type: str = "BOT", user: Optional[str] = None) -> None:
        self.log_entry(level="DEBUG", text=text, log_type=log_type, user=user)

    def info(self, text: str, log_type: str = "BOT", user: Optional[str] = None) -> None:
        self.log_entry(level="INFO", text=text, log_type=log_type, user=user)

    def warning(self, text: str, log_type: str = "BOT", user: Optional[str] = None) -> None:
        self.log_entry(level="WARNING", text=text, log_type=log_type, user=user)

    def error(self, text: str, log_type: str = "BOT", user: Optional[str] = None) -> None:
        self.log_entry(level="ERROR", text=text, log_type=log_type, user=user)

    def critical(self, text: str, log_type: str = "BOT", user: Optional[str] = None) -> None:
        self.log_entry(level="CRITICAL", text=text, log_type=log_type, user=user)


# Глобальный экземпляр
logger: _Logger = _Logger(system_name="DISCORD_BOT")
log = logger.log
