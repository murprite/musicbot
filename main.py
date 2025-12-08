from asyncio import run

from bot import discbot
from configs import settings
from middleware import logger


async def main() -> None:
    """
    Точка входа для асинхронного запуска бота.
    """
    logger.setup()
    await discbot.start(settings.BOT_TOKEN)
    await discbot.start_bot()


if __name__ == "__main__":
    run(main())
