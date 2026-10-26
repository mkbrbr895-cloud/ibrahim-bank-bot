import asyncio
import logging
import math
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("telegram_timer_bot")

router = Router()
active_timer_tasks: set[asyncio.Task[None]] = set()

MAX_TIMER_MINUTES = 7 * 24 * 60
MAX_DESCRIPTION_LENGTH = 3500


def format_remaining(seconds: int) -> str:
    seconds = max(0, seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def timer_text(description: str, seconds: int) -> str:
    return f"⏳ {description}\nالوقت المتبقي: {format_remaining(seconds)}"


async def run_countdown(
    timer_message: Message,
    description: str,
    duration_seconds: int,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration_seconds

    try:
        while True:
            remaining = max(0, math.ceil(deadline - loop.time()))
            if remaining == 0:
                await timer_message.edit_text(f"✅ انتهى الوقت\n{description}")
                return

            await asyncio.sleep(min(10, remaining))
            remaining = max(0, math.ceil(deadline - loop.time()))
            if remaining == 0:
                await timer_message.edit_text(f"✅ انتهى الوقت\n{description}")
                return

            await timer_message.edit_text(timer_text(description, remaining))
    except asyncio.CancelledError:
        raise
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.info("A timer stopped because its message could no longer be updated.")


@router.message(Command("timer"))
async def create_timer(message: Message, command: CommandObject) -> None:
    if message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        await message.answer("استخدم هذا الأمر داخل مجموعة أو مجموعة فائقة.")
        return

    arguments = (command.args or "").strip().split(maxsplit=1)
    if len(arguments) != 2:
        await message.reply(
            "طريقة الاستخدام: /timer <الدقائق> <الوصف>\n"
            "مثال: /timer 5 استراحة"
        )
        return

    try:
        minutes = int(arguments[0])
    except ValueError:
        await message.reply("يجب أن يكون عدد الدقائق رقمًا صحيحًا.")
        return

    description = arguments[1].strip()
    if not 1 <= minutes <= MAX_TIMER_MINUTES:
        await message.reply("اختر مدة بين دقيقة واحدة و7 أيام.")
        return
    if not description:
        await message.reply("أضف وصفًا للعداد.")
        return
    if len(description) > MAX_DESCRIPTION_LENGTH:
        await message.reply("الوصف طويل جدًا؛ الحد الأقصى 3500 حرف.")
        return

    duration_seconds = minutes * 60
    timer_message = await message.answer(timer_text(description, duration_seconds))

    try:
        await timer_message.pin(disable_notification=True)
    except (TelegramBadRequest, TelegramForbiddenError):
        await message.reply(
            "بدأ العداد، لكن تعذر تثبيت الرسالة. امنح البوت صلاحية تثبيت الرسائل."
        )

    task = asyncio.create_task(
        run_countdown(timer_message, description, duration_seconds),
        name=f"timer-{timer_message.chat.id}-{timer_message.message_id}",
    )
    active_timer_tasks.add(task)
    task.add_done_callback(active_timer_tasks.discard)


async def run_bot(token: str) -> None:
    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    try:
        await dispatcher.start_polling(bot, close_bot_session=False)
    finally:
        tasks = tuple(active_timer_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
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
