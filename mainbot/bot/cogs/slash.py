import discord
from discord.ext import commands

from middleware.loggers import logger


class Slash(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.app_commands.command(
        name="rules",
        description="Показать правила сервера",
    )
    async def rules_slash(self, interaction: discord.Interaction) -> None:
        rules_text: str = (
            "**Правила сервера:**\n"
            "1. Уважайте других участников.\n"
            "2. Запрещена реклама и спам.\n"
            "3. Не используйте запрещённые слова.\n"
            "4. Соблюдайте тематику каналов.\n"
            "5. Выполняйте указания модераторов.\n"
        )
        await interaction.response.send_message(rules_text, ephemeral=False)
        logger.info(
            text=f"Slash /rules вызван пользователем {interaction.user}",
            log_type="COMMAND",
            user=str(interaction.user),
        )

    @discord.app_commands.command(
        name="ping",
        description="Проверить отклик бота",
    )
    async def ping_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!", ephemeral=True)
        logger.info(
            text=f"Slash /ping вызван пользователем {interaction.user}",
            log_type="COMMAND",
            user=str(interaction.user),
        )




async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Slash(bot))
