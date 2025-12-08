from datetime import datetime, timedelta

from discord.ext.commands import Cog, Bot, Context, group

from ..storage import storage, Reminder
from .moderation import is_admin


class Reminders(Cog):
    """
    Cog для управления напоминаниями: add, list, remove.
    """
    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    @group()
    @is_admin()
    async def reminder(self, ctx: Context) -> None:
        """
        Группа команд напоминаний.

        :param ctx: Контекст команды.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "Используйте `!reminder add <минуты> <текст>`, "
                "`!reminder list` или `!reminder remove <номер>`"
            )

    @reminder.command(name="add")
    async def reminder_add(
        self, ctx: Context, minutes: int, *, text: str
    ) -> None:
        """
        Добавить новое напоминание.

        :param ctx: Контекст команды.
        :param minutes: Через сколько минут сработает напоминание.
        :param text: Текст напоминания.
        """
        if minutes <= 0:
            await ctx.send("Время должно быть положительным числом минут.")
            return

        remind_time: datetime = datetime.now() + timedelta(minutes=minutes)
        storage.reminders.append(
            Reminder(
                time=remind_time.timestamp(),
                channel_id=ctx.channel.id,  # type: ignore[assignment]
                user_mention=ctx.author.mention,  # type: ignore[union-attr]
                text=text,
            )
        )
        storage.save_reminders()
        await ctx.send(f"Напоминание добавлено через {minutes} минут: {text}")

    @reminder.command(name="list")
    async def reminder_list(self, ctx: Context) -> None:
        """
        Показать список активных напоминаний.

        :param ctx: Контекст команды.
        """
        if not storage.reminders:
            await ctx.send("Активных напоминаний нет.")
            return

        msg: str = "Активные напоминания:\n"
        for i, rem in enumerate(storage.reminders, 1):
            t_str: str = datetime.fromtimestamp(rem.time).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            msg += f"{i}. До {t_str} — {rem.text} (от {rem.user_mention})\n"
        await ctx.send(msg)

    @reminder.command(name="remove")
    async def reminder_remove(self, ctx: Context, number: int) -> None:
        """
        Удалить напоминание по номеру.

        :param ctx: Контекст команды.
        :param number: Порядковый номер напоминания.
        """
        if number <= 0 or number > len(storage.reminders):
            await ctx.send("Неверный номер напоминания.")
            return

        removed: Reminder = storage.reminders.pop(number - 1)
        storage.save_reminders()
        await ctx.send(f"Удалено напоминание: {removed.text}")


async def setup(bot: Bot) -> None:
    await bot.add_cog(Reminders(bot))
