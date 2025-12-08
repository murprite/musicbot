# config.py
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )

    BOT_TOKEN: Optional[str] = None
    PREFIX: Optional[str] = '!'

    WELCOME_CHANNEL_ID: int = 0
    ADMIN_ROLE_NAME: str = "Администратор"

    WARNINGS_FILE: Path = Path("warnings.json")
    REMINDERS_FILE: Path = Path("reminders.json")
    BLACKLIST_FILE: Path = Path("blacklist.json")

    LOG_FILE_NAME: Path = Path("bot.log")
    LOG_LEVEL: str = "info"

    @field_validator("BOT_TOKEN")
    def validate_bot_token(cls, v: Optional[str]) -> str:
        if not v:
            raise ValueError("Не задан BOT_TOKEN (проверь .env или переменные окружения)")
        return v

    @field_validator("WELCOME_CHANNEL_ID")
    def validate_channel_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("WELCOME_CHANNEL_ID должен быть положительным ID канала")
        return v

    @field_validator("ADMIN_ROLE_NAME")
    def validate_admin_role_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ADMIN_ROLE_NAME не может быть пустым")
        return v

    @field_validator("LOG_LEVEL")
    def validate_log_level(cls, v: str) -> str:
        allowed: set[str] = {"debug", "info", "warning", "error", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"LOG_LEVEL должен быть одним из: {', '.join(allowed)}")
        return v.lower()

    @field_validator("WARNINGS_FILE", "REMINDERS_FILE", "BLACKLIST_FILE", "LOG_FILE_NAME", mode="before")
    def validate_paths(cls, v) -> Optional[Path]:
        return Path(v) if isinstance(v, str) else v


# Создаём экземпляр класса настроек
settings = _Settings()

# Настройка экспорта в модули
__all__ = ("settings",)
