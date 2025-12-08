from __future__ import annotations

from typing import Callable, Awaitable, Optional

import datetime

import discord
from discord.ext import commands
from discord.utils import get

from configs import settings
from ..storage import storage


# Тип предиката для check (для читаемости, но не обязателен)
CheckPredicate = Callable[[commands.Context], Awaitable[bool]]


def is_admin():
    """
    Создаёт декоратор проверки прав администратора:
    либо есть роль с именем settings.ADMIN_ROLE_NAME,
    либо у пользователя есть флаг администратора сервера.
    """

    async def predicate(ctx: commands.Context) -> bool:
        author = ctx.author
        if not isinstance(author, discord.Member):
            return False

        admin_role = get(author.roles, name=settings.ADMIN_ROLE_NAME)
        return bool(admin_role) or author.guild_permissions.administrator

    return commands.check(predicate)


def require_guild(ctx: commands.Context) -> Optional[discord.Guild]:
    """
    Безопасно получить guild из контекста.

    Если команда вызвана не на сервере (в ЛС), возвращает None.
    """
    return ctx.guild


class Moderation(commands.Cog):
    """
    Cog с модерационными командами:
    rules, kick, ban, unban, mute, unmute, warn, warnings, clear.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        :param bot: Экземпляр бота, к которому привязан cog.
        """
        self.bot: commands.Bot = bot

    @commands.command()
    @is_admin()
    async def rules(self, ctx: commands.Context) -> None:
        """
        Показать правила сервера.

        :param ctx: Контекст команды.
        """
        rules_text: str = (
            "**Правила сервера:**\n"
            "1. Уважайте других участников.\n"
            "2. Запрещена реклама и спам.\n"
            "3. Не используйте запрещённые слова.\n"
            "4. Соблюдайте тематику каналов.\n"
            "5. Выполняйте указания модераторов.\n"
        )
        await ctx.send(rules_text)

    @commands.command()
    @is_admin()
    async def kick(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """
        Исключить участника с сервера.

        :param ctx: Контекст команды.
        :param member: Участник для исключения.
        :param reason: Причина исключения.
        """
        try:
            await member.kick(reason=reason)
            await ctx.send(f"{member} был исключён. Причина: {reason}")
        except discord.Forbidden:
            await ctx.send("Недостаточно прав для исключения этого участника.")
        except discord.HTTPException:
            await ctx.send(f"Не удалось исключить {member} из-за ошибки Discord.")

    @commands.command()
    @is_admin()
    async def ban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """
        Забанить участника на сервере.

        :param ctx: Контекст команды.
        :param member: Участник для бана.
        :param reason: Причина бана.
        """
        try:
            await member.ban(reason=reason)
            await ctx.send(f"{member} был забанен. Причина: {reason}")
        except discord.Forbidden:
            await ctx.send("Недостаточно прав для бана этого участника.")
        except discord.HTTPException:
            await ctx.send(f"Не удалось забанить {member} из-за ошибки Discord.")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, *, member_name: str) -> None:
        """
        Разбанить пользователя по имени или тегу.

        :param ctx: Контекст команды.
        :param member_name: Имя или имя#дискриминатор.
        """
        guild = require_guild(ctx)
        if guild is None:
            await ctx.send("Команду можно использовать только на сервере.")
            return

        banned_users: list[discord.guild.BanEntry] = [
            ban_entry async for ban_entry in guild.bans()
        ]

        # Вариант с полным тегом
        if "#" in member_name:
            try:
                name, discriminator = member_name.split("#", maxsplit=1)
            except ValueError:
                await ctx.send("Неверный формат пользователя. Используйте Имя#Тег.")
                return

            for ban_entry in banned_users:
                user = ban_entry.user
                if (user.name, user.discriminator) == (name, discriminator):
                    try:
                        await guild.unban(user)
                        await ctx.send(f"Пользователь {user} разбанен.")
                    except discord.HTTPException:
                        await ctx.send("Ошибка при разбане пользователя.")
                    return

            await ctx.send(f"Пользователь {member_name} не найден в бан-листе.")
            return

        # Вариант только с именем
        matching = [
            ban_entry.user
            for ban_entry in banned_users
            if ban_entry.user.name.lower() == member_name.lower()
        ]

        if not matching:
            await ctx.send(
                f"Пользователь с именем `{member_name}` не найден в бан-листе."
            )
            return

        if len(matching) == 1:
            user = matching[0]
            try:
                await guild.unban(user)
                await ctx.send(f"Пользователь {user} разбанен.")
            except discord.HTTPException:
                await ctx.send("Ошибка при разбане пользователя.")
            return

        msg_lines: list[str] = [
            "Найдено несколько пользователей с таким именем. "
            "Укажите полный тег для разбанивания:",
        ]
        for user in matching:
            msg_lines.append(f"- {user.name}#{user.discriminator}")
        await ctx.send("\n".join(msg_lines))

    @commands.command()
    @is_admin()
    async def mute(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """
        Выдать участнику мут (роль Muted).

        :param ctx: Контекст команды.
        :param member: Участник, которому выдаётся мут.
        :param reason: Причина мута.
        """
        guild = require_guild(ctx)
        if guild is None:
            await ctx.send("Команду можно использовать только на сервере.")
            return

        muted_role: Optional[discord.Role] = get(guild.roles, name="Muted")
        if muted_role is None:
            await ctx.send("Роль Muted не найдена.")
            return

        try:
            await member.add_roles(muted_role, reason=reason)
            await ctx.send(f"{member} заглушен. Причина: {reason}")
        except discord.Forbidden:
            await ctx.send("Недостаточно прав для выдачи мута.")
        except discord.HTTPException:
            await ctx.send("Не удалось выдать мут из-за ошибки Discord.")

    @commands.command()
    @is_admin()
    async def unmute(self, ctx: commands.Context, member: discord.Member) -> None:
        """
        Снять мут с участника.

        :param ctx: Контекст команды.
        :param member: Участник, с которого снимается мут.
        """
        guild = require_guild(ctx)
        if guild is None:
            await ctx.send("Команду можно использовать только на сервере.")
            return

        muted_role: Optional[discord.Role] = get(guild.roles, name="Muted")
        if muted_role is None:
            await ctx.send("Роль Muted не найдена.")
            return

        try:
            await member.remove_roles(muted_role)
            await ctx.send(f"Мут снят с {member}.")
        except discord.Forbidden:
            await ctx.send("Недостаточно прав для снятия мута.")
        except discord.HTTPException:
            await ctx.send("Не удалось снять мут из-за ошибки Discord.")

    @commands.command()
    @is_admin()
    async def warn(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """
        Выдать предупреждение участнику.

        :param ctx: Контекст команды.
        :param member: Участник.
        :param reason: Причина предупреждения.
        """
        user_id: str = str(member.id)
        storage.user_warnings.setdefault(user_id, []).append(
            {
                "reason": reason or "Без причины",
                "date": datetime.datetime.now().isoformat(
                    sep=" ", timespec="seconds"
                ),
            }
        )
        storage.save_warnings()
        await ctx.send(
            f"{member} получил предупреждение. Причина: {reason or 'Без причины'}"
        )

    @commands.command()
    async def warnings(self, ctx: commands.Context, member: discord.Member) -> None:
        """
        Показать предупреждения участника.

        :param ctx: Контекст команды.
        :param member: Участник.
        """
        user_id: str = str(member.id)
        warns = storage.user_warnings.get(user_id, [])
        if not warns:
            await ctx.send(f"У пользователя {member} нет предупреждений.")
            return

        lines: list[str] = [f"Предупреждения пользователя {member}:"]
        for i, w in enumerate(warns, 1):
            lines.append(f"{i}. {w['reason']} ({w['date']})")
        await ctx.send("\n".join(lines))

    @commands.command()
    @is_admin()
    async def clear(self, ctx: commands.Context, amount: int) -> None:
        """
        Очистить указанное количество сообщений в канале.

        :param ctx: Контекст команды.
        :param amount: Количество сообщений для удаления.
        """
        if amount <= 0:
            await ctx.send("Количество должно быть положительным числом.")
            return

        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(
            f"Удалено сообщений: {len(deleted) - 1}",
            delete_after=5,
        )


async def setup(bot: commands.Bot) -> None:
    """
    Зарегистрировать cog в боте.

    :param bot: Экземпляр бота.
    """
    await bot.add_cog(Moderation(bot))
