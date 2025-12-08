from discord.ext import commands

from ..storage import storage
from .moderation import is_admin


class Blacklist(commands.Cog):
    """
    Cog для управления чёрным списком слов.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    @commands.command()
    @is_admin()
    async def blacklist_show(self, ctx: commands.Context) -> None:
        """
        Показать текущий чёрный список слов.

        :param ctx: Контекст команды.
        """
        if not storage.blacklist:
            await ctx.send("Чёрный список пуст.")
        else:
            await ctx.send("Чёрный список:\n" + ", ".join(storage.blacklist))

    @commands.command()
    @is_admin()
    async def blacklist_add(self, ctx: commands.Context, *, word: str) -> None:
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

    @commands.command()
    @is_admin()
    async def blacklist_remove(self, ctx: commands.Context, *, word: str) -> None:
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Blacklist(bot))
