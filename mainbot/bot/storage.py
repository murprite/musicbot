from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from configs import settings


@dataclass
class Reminder:
    """
    Модель напоминания.

    Attributes:
        time: Unix-время, когда нужно отправить напоминание.
        channel_id: ID текстового канала.
        user_mention: mention пользователя.
        text: Текст напоминания.
    """
    time: float
    channel_id: int
    user_mention: str
    text: str


@dataclass
class Storage:
    """
    Класс для работы с локальными JSON‑хранилищами:
    предупреждения, напоминания, чёрный список.
    """

    warnings_file: Path = settings.WARNINGS_FILE
    reminders_file: Path = settings.REMINDERS_FILE
    blacklist_file: Path = settings.BLACKLIST_FILE

    reminders: List[Reminder] = field(default_factory=list)
    user_warnings: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    blacklist: List[str] = field(default_factory=list)

    def load_all(self) -> None:
        """
        Загрузить все данные из файлов.
        """
        self.load_warnings()
        self.load_reminders()
        self.load_blacklist()

    def load_warnings(self) -> None:
        """
        Загрузить предупреждения пользователей из JSON‑файла.
        """
        if self.warnings_file.is_file():
            try:
                data = json.loads(self.warnings_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.user_warnings = data
                else:
                    self.user_warnings = {}
            except json.JSONDecodeError:
                self.user_warnings = {}

    def save_warnings(self) -> None:
        """
        Сохранить предупреждения пользователей в JSON‑файл.
        """
        self.warnings_file.write_text(
            json.dumps(self.user_warnings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_reminders(self) -> None:
        """
        Загрузить напоминания из JSON‑файла.
        """
        self.reminders.clear()
        if self.reminders_file.is_file():
            try:
                data = json.loads(self.reminders_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        try:
                            self.reminders.append(
                                Reminder(
                                    time=float(item["time"]),
                                    channel_id=int(item["channel_id"]),
                                    user_mention=str(item["user_mention"]),
                                    text=str(item["text"]),
                                )
                            )
                        except (KeyError, ValueError, TypeError):
                            continue
            except json.JSONDecodeError:
                self.reminders = []

    def save_reminders(self) -> None:
        """
        Сохранить напоминания в JSON‑файл.
        """
        data: List[Dict[str, Any]] = [
            {
                "time": r.time,
                "channel_id": r.channel_id,
                "user_mention": r.user_mention,
                "text": r.text,
            }
            for r in self.reminders
        ]
        self.reminders_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_blacklist(self) -> None:
        """
        Загрузить чёрный список слов из JSON‑файла.
        """
        self.blacklist.clear()
        if self.blacklist_file.is_file():
            try:
                data = json.loads(self.blacklist_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.blacklist = [str(w).lower() for w in data]
                else:
                    self.blacklist = []
            except Exception:
                self.blacklist = []

    def save_blacklist(self) -> None:
        """
        Сохранить чёрный список слов в JSON‑файл.
        """
        self.blacklist_file.write_text(
            json.dumps(self.blacklist, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


storage: Storage = Storage()
