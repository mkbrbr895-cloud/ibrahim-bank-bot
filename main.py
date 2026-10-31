import asyncio
import logging
import os

from aiogram import Bot, Dispatcher

from bot_rps import router as rps_router
from bot_games import router as text_games_router
from bot_games_bank import router as games_bank_router
from bot_storage import initialize_storage


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
async def run_bot(token: str) -> None:
    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher.include_router(rps_router)
    dispatcher.include_router(text_games_router)
    dispatcher.include_router(games_bank_router)

    try:
        await asyncio.to_thread(initialize_storage)
        await dispatcher.start_polling(bot, close_bot_session=False)
    finally:
        await bot.session.close()


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "أضف TELEGRAM_BOT_TOKEN إلى أسرار Replit لتشغيل البوت."
        )

    asyncio.run(run_bot(token))


if __name__ == "__main__":
    main()
