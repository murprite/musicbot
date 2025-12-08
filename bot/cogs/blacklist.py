from discord.ext.commands import Cog, Bot, command, Context

from ..storage import storage
from .moderation import is_admin


class Blacklist(Cog):
    """
    Cog для управления чёрным списком слов.
    """

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot

    @command()
    @is_admin()
    async def blacklist_show(self, ctx: Context) -> None:
        """
        Показать текущий чёрный список слов.

        :param ctx: Контекст команды.
        """
        if not storage.blacklist:
            await ctx.send("Чёрный список пуст.")
        else:
            await ctx.send("Чёрный список:\n" + ", ".join(storage.blacklist))

    @command()
    @is_admin()
    async def blacklist_add(self, ctx: Context, *, word: str) -> None:
        """
        Добавить слово в чёрный список.

        :param ctx: Контекст команды.
        :param word: Слово для добавления.
        """
        word_lower: str = word.lower()
        if word_lower in storage.blacklist:
            await ctx.send(f"Слово `{word_lower}` уже в чёрном списке.")
            return

        storage.blacklist.append(word_lower)
        storage.save_blacklist()
        await ctx.send(f"Слово `{word_lower}` добавлено в чёрный список.")

    @command()
    @is_admin()
    async def blacklist_remove(self, ctx: Context, *, word: str) -> None:
        """
        Удалить слово из чёрного списка.

        :param ctx: Контекст команды.
        :param word: Слово для удаления.
        """
        word_lower: str = word.lower()
        if word_lower not in storage.blacklist:
            await ctx.send(f"Слово `{word_lower}` отсутствует в чёрном списке.")
            return

        storage.blacklist.remove(word_lower)
        storage.save_blacklist()
        await ctx.send(f"Слово `{word_lower}` удалено из чёрного списка.")


async def setup(bot: Bot) -> None:
    await bot.add_cog(Blacklist(bot))
