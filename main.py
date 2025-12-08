from asyncio import run

from bot import discbot
from middleware.loggers import logger


async def main() -> None:
    """
    Точка входа для асинхронного запуска бота.
    """
    logger.setup()          # настройка логера
    await discbot.setup()   # ЗАГРУЗКА COGS + настройка discord-логов
    await discbot.start_bot()  # запуск бота (внутри возьмёт token из settings)


if __name__ == "__main__":
    run(main())
