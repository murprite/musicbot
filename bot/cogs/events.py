import datetime

import discord
from discord.ext import commands, tasks
from discord.utils import get

from configs import settings
from middleware import logger
from ..storage import storage, Reminder


class Events(commands.Cog):
    """
    Cog с обработчиками событий и фоновой задачей напоминаний.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.check_reminders.start()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Событие запуска бота.
        Загружает данные и создаёт необходимые роли.
        """
        logger.info(text=f"Бот запущен как {self.bot.user}")
        storage.load_all()
        await self.ensure_roles_exist()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """
        Событие вступления нового участника на сервер.

        :param member: Новый участник.
        """
        new_member_role: discord.Role | None = get(member.guild.roles, name="New Member")
        if new_member_role:
            await member.add_roles(new_member_role)

        channel: discord.abc.MessageableChannel | None = self.bot.get_channel(
            settings.WELCOME_CHANNEL_ID
        )
        if isinstance(channel, discord.TextChannel):
            await channel.send(f"Приветствуем {member.mention} на сервере!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Событие получения сообщения. Проверяет чёрный список слов.

        :param message: Полученное сообщение.
        """
        if message.author.bot or not message.content:
            return

        msg_lower: str = message.content.lower()
        if any(word in msg_lower for word in storage.blacklist):
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, ваше сообщение содержит запрещённые слова."
                )
            except Exception:
                pass
            return

        await self.bot.process_commands(message)

    async def ensure_roles_exist(self) -> None:
        """
        Проверяет наличие ролей Muted и New Member и создаёт их при необходимости.
        """
        for guild in self.bot.guilds:
            muted_role: discord.Role | None = get(guild.roles, name="Muted")
            if muted_role is None:
                try:
                    muted_role = await guild.create_role(name="Muted")
                    for channel in guild.channels:
                        await channel.set_permissions(
                            muted_role, send_messages=False, speak=False
                        )
                except Exception:
                    pass

            new_member_role: discord.Role | None = get(guild.roles, name="New Member")
            if new_member_role is None:
                try:
                    await guild.create_role(name="New Member")
                except Exception:
                    pass

    @tasks.loop(seconds=30)
    async def check_reminders(self) -> None:
        """
        Фоновая задача, которая каждые 30 секунд проверяет напоминания
        и отправляет просроченные.
        """
        now: float = datetime.datetime.now().timestamp()
        to_remove: list[Reminder] = []

        for rem in storage.reminders:
            if rem.time <= now:
                channel = self.bot.get_channel(rem.channel_id)
                if isinstance(channel, discord.TextChannel):
                    await channel.send(f"{rem.user_mention} Напоминание: {rem.text}")
                to_remove.append(rem)

        if to_remove:
            for rem in to_remove:
                storage.reminders.remove(rem)
            storage.save_reminders()

    @check_reminders.before_loop
    async def before_check_reminders(self) -> None:
        """
        Ожидание готовности бота перед стартом фоновой задачи.
        """
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    """
    Функция для загрузки Cog.

    :param bot: Экземпляр бота.
    """
    await bot.add_cog(Events(bot))
