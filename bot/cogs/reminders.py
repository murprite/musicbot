from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from ..storage import storage, Reminder
from .moderation import is_admin


class Reminders(commands.Cog):
    """Cog для управления напоминаниями: add, list, remove через slash-команды."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    reminder_group = app_commands.Group(name="reminder", description="Управление напоминаниями")

    @reminder_group.command(name="add", description="Добавить новое напоминание")
    @is_admin()
    @app_commands.describe(minutes="Через сколько минут сработает напоминание", text="Текст напоминания")
    async def reminder_add(
        self, interaction: discord.Interaction, minutes: int, text: str
    ) -> None:
        if minutes <= 0:
            await interaction.response.send_message(
                "Время должно быть положительным числом минут.", ephemeral=True
            )
            return

        remind_time = datetime.now() + timedelta(minutes=minutes)
        storage.reminders.append(
            Reminder(
                time=remind_time.timestamp(),
                channel_id=interaction.channel.id,  # type: ignore
                user_mention=interaction.user.mention,  # type: ignore
                text=text,
            )
        )
        storage.save_reminders()
        await interaction.response.send_message(
            f"✅ Напоминание добавлено через {minutes} минут: {text}"
        )

    @reminder_group.command(name="list", description="Показать список активных напоминаний")
    @is_admin()
    async def reminder_list(self, interaction: discord.Interaction) -> None:
        if not storage.reminders:
            await interaction.response.send_message("Активных напоминаний нет.", ephemeral=True)
            return

        msg = "📋 Активные напоминания:\n"
        for i, rem in enumerate(storage.reminders, 1):
            t_str = datetime.fromtimestamp(rem.time).strftime("%Y-%m-%d %H:%M:%S")
            msg += f"{i}. До {t_str} — {rem.text} (от {rem.user_mention})\n"

        await interaction.response.send_message(msg)

    @reminder_group.command(name="remove", description="Удалить напоминание по номеру")
    @is_admin()
    @app_commands.describe(number="Номер напоминания из списка")
    async def reminder_remove(self, interaction: discord.Interaction, number: int) -> None:
        if number <= 0 or number > len(storage.reminders):
            await interaction.response.send_message("❌ Неверный номер напоминания.", ephemeral=True)
            return

        removed = storage.reminders.pop(number - 1)
        storage.save_reminders()
        await interaction.response.send_message(f"✅ Удалено напоминание: {removed.text}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reminders(bot))