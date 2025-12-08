from discord.ext.commands import HelpCommand

from configs import settings


class MyHelpCommand(HelpCommand):
    """Кастомная команда help с текстовой справкой."""
    async def send_bot_help(self, mapping, prefix: str = settings.PREFIX) -> None:
        channel = self.get_destination()
        help_text: str = (
            "**Доступные команды:**\n"
            f"`{prefix}help` — показать это сообщение\n"
            f"`{prefix}rules` — показать правила сервера\n"
            f"`{prefix}reminder add <минуты> <текст>` — добавить напоминание\n"
            f"`{prefix}reminder list` — список напоминаний\n"
            f"`{prefix}reminder remove <номер>` — удалить напоминание\n"
            f"`{prefix}kick @пользователь [причина]` — исключить\n"
            f"`{prefix}ban @пользователь [причина]` — забанить\n"
            f"`{prefix}unban имя#дискриминатор` — разбанить\n"
            f"`{prefix}mute @пользователь [причина]` — заглушить\n"
            f"`{prefix}unmute @пользователь` — снять заглушение\n"
            f"`{prefix}warn @пользователь [причина]` — предупреждение\n"
            f"`{prefix}warnings @пользователь` — список предупреждений\n"
            f"`{prefix}clear <кол-во>` — очистить чат\n"
            f"`{prefix}blacklist_show` — показать чёрный список\n"
            f"`{prefix}blacklist_add` — добавить слово чёрный список\n"
            f"`{prefix}blacklist_remove` — удалить слово из чёрного списока\n"
        )
        await channel.send(help_text)
