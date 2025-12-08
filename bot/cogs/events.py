from datetime import datetime

import discord
from discord.ext import tasks
from discord.ext.commands import Bot, Cog, Context, CommandError
from discord.utils import get

from configs import settings
from middleware.loggers import logger
from ..storage import storage, Reminder


class Events(Cog):
    """
    Cog с обработчиками событий и фоновой задачей напоминаний.
    """

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot
        self.check_reminders.start()

    @Cog.listener()
    async def on_ready(self) -> None:
        """
        Событие запуска бота.
        Загружает данные и создаёт необходимые роли.
        """
        logger.info(text=f"Бот запущен как {self.bot.user}", log_type="SYSTEM")
        storage.load_all()
        await self.ensure_roles_exist()

    @Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """
        Событие вступления нового участника на сервер.

        :param member: Новый участник.
        """
        new_member_role: discord.Role | None = get(member.guild.roles, name="New Member")
        if new_member_role:
            try:
                await member.add_roles(new_member_role)
            except discord.Forbidden:
                logger.warning(
                    text=f"Нет прав выдать роль New Member пользователю {member}",
                    log_type="EVENT",
                    user=str(member),
                )

        channel = self.bot.get_channel(settings.WELCOME_CHANNEL_ID)
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(f"Приветствуем {member.mention} на сервере!")
            except discord.HTTPException as e:
                logger.error(
                    text=f"Не удалось отправить приветствие для {member}: {e!r}",
                    log_type="EVENT",
                    user=str(member),
                )

    @Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Событие получения сообщения. Проверяет чёрный список слов
        и передаёт сообщение обработчику команд.
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
                logger.info(
                    text=f"Удалено сообщение с запрещённым словом от {message.author}: {message.content!r}",
                    log_type="BLACKLIST",
                    user=str(message.author),
                )
            except discord.Forbidden:
                logger.warning(
                    text=f"Нет прав удалить сообщение {message.author}: {message.content!r}",
                    log_type="BLACKLIST",
                    user=str(message.author),
                )
            except discord.HTTPException as e:
                logger.error(
                    text=f"Ошибка при удалении сообщения {message.author}: {e!r}",
                    log_type="BLACKLIST",
                    user=str(message.author),
                )
            return

    @Cog.listener()
    async def on_command_error(self, ctx: Context, error: CommandError) -> None:
        """
        Логирование ошибок команд.
        """
        logger.error(
            text=f"Ошибка команды: {ctx.command} | Автор: {ctx.author} | Ошибка: {error!r}",
            log_type="COMMAND",
            user=str(ctx.author),
        )

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
                        try:
                            await channel.set_permissions(
                                muted_role, send_messages=False, speak=False
                            )
                        except discord.Forbidden:
                            logger.warning(
                                text=f"Нет прав настроить права для канала {channel} в {guild}",
                                log_type="ROLES",
                            )
                except discord.Forbidden:
                    logger.warning(
                        text=f"Нет прав создать роль Muted в {guild}",
                        log_type="ROLES",
                    )
                except discord.HTTPException as e:
                    logger.error(
                        text=f"Ошибка при создании роли Muted в {guild}: {e!r}",
                        log_type="ROLES",
                    )

            new_member_role: discord.Role | None = get(guild.roles, name="New Member")
            if new_member_role is None:
                try:
                    await guild.create_role(name="New Member")
                except discord.Forbidden:
                    logger.warning(
                        text=f"Нет прав создать роль New Member в {guild}",
                        log_type="ROLES",
                    )
                except discord.HTTPException as e:
                    logger.error(
                        text=f"Ошибка при создании роли New Member в {guild}: {e!r}",
                        log_type="ROLES",
                    )

    @tasks.loop(seconds=30)
    async def check_reminders(self) -> None:
        """
        Фоновая задача, которая каждые 30 секунд проверяет напоминания
        и отправляет просроченные.
        """
        now: float = datetime.now().timestamp()
        to_remove: list[Reminder] = []

        for rem in list(storage.reminders):
            if rem.time <= now:
                channel = self.bot.get_channel(rem.channel_id)
                if isinstance(channel, discord.TextChannel):
                    try:
                        await channel.send(f"{rem.user_mention} Напоминание: {rem.text}")
                        logger.info(
                            text=f"Отправлено напоминание пользователю {rem.user_mention}: {rem.text!r}",
                            log_type="REMINDER",
                        )
                    except discord.HTTPException as e:
                        logger.error(
                            text=f"Ошибка при отправке напоминания в канал {channel.id}: {e!r}",
                            log_type="REMINDER",
                        )
                to_remove.append(rem)

        if to_remove:
            for rem in to_remove:
                try:
                    storage.reminders.remove(rem)
                except ValueError:
                    pass
            storage.save_reminders()

    @check_reminders.before_loop
    async def before_check_reminders(self) -> None:
        """
        Ожидание готовности бота перед стартом фоновой задачи.
        """
        await self.bot.wait_until_ready()


async def setup(bot: Bot) -> None:
    """
    Функция для загрузки Cog.

    :param bot: Экземпляр бота.
    """
    await bot.add_cog(Events(bot))
