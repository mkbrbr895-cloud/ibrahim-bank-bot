import asyncio
import logging
import math
import os
import re
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import ChatPermissions, Message

from bot_games_bank import router as games_bank_router
from bot_storage import get_creator_identity, initialize_storage


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("telegram_timer_bot")

router = Router()
active_timer_tasks: set[asyncio.Task[None]] = set()

MAX_TIMER_MINUTES = 7 * 24 * 60
MAX_DESCRIPTION_LENGTH = 3500
MUTE_DURATION = timedelta(seconds=60)
MUTE_COMMAND_PATTERN = re.compile(r"/mute(?:@[A-Za-z0-9_]+)?", re.IGNORECASE)
MUTE_TEXT_PATTERN = re.compile(r"^\s*كتم\s*$")

WELCOME_MESSAGE = (
    "مرحباً بك {name} نورت القروب! 🤍\n"
    "نتمنى لك وقتاً ممتعاً، ويرجى الالتزام بالقوانين التالية:\n"
    "ممنوع الشقة الزايد أو الاستفزاز.\n"
    "يمنع السب، الشتم، أو الألفاظ غير اللائقة نهائياً.\n"
    "يمنع التكلم في أي مواضيع أو سوالف غير مناسبة.\n"
    "⚠️ ملاحظة: أي مخالفة للقوانين ستعرضك لكتم صوت (Mute) لمدة دقيقة واحدة تمنعك من إرسال الرسائل."
)


def format_remaining(seconds: int) -> str:
    seconds = max(0, seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def timer_text(description: str, seconds: int) -> str:
    return f"⏳ {description}\nالوقت المتبقي: {format_remaining(seconds)}"


def is_mute_trigger(text: str) -> bool:
    text = text.strip()
    return text == "كتم" or MUTE_COMMAND_PATTERN.fullmatch(text) is not None


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


@router.message(F.new_chat_members)
async def welcome_new_members(message: Message) -> None:
    for member in message.new_chat_members:
        if member.is_bot:
            continue
        await message.answer(WELCOME_MESSAGE.format(name=member.full_name))


@router.message(F.reply_to_message, F.text.regexp(MUTE_TEXT_PATTERN))
@router.message(F.reply_to_message, Command("mute"))
async def mute_replied_member(message: Message) -> None:
    if not message.text or not is_mute_trigger(message.text):
        return

    if message.chat.type != ChatType.SUPERGROUP:
        await message.reply("يعمل أمر الكتم في المجموعات الفائقة فقط.")
        return

    moderator = message.from_user
    target = message.reply_to_message.from_user
    if moderator is None or target is None:
        await message.reply("تعذر تحديد المشرف أو العضو من الرسالة.")
        return
    if target.is_bot:
        await message.reply("لا يمكن كتم حساب بوت بهذا الأمر.")
        return

    try:
        moderator_status = await message.bot.get_chat_member(
            chat_id=message.chat.id,
            user_id=moderator.id,
        )
    except TelegramAPIError:
        await message.reply("تعذر التحقق من صلاحياتك كمشرف.")
        return

    if moderator_status.status not in {
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    }:
        await message.reply("هذا الأمر متاح للمشرفين فقط.")
        return

    is_creator = await asyncio.to_thread(
        get_creator_identity,
        target.id,
        target.username,
    )
    if is_creator:
        await message.reply("⚠️ لا يمكنك كتم مطور وصانع البوت!")
        return

    try:
        target_status = await message.bot.get_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
        )
    except TelegramAPIError:
        await message.reply("تعذر العثور على العضو في هذه المجموعة.")
        return

    if target_status.status in {
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    }:
        await message.reply("لا يمكن كتم مشرف أو مالك المجموعة.")
        return

    try:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            ),
            until_date=datetime.now(timezone.utc) + MUTE_DURATION,
            use_independent_chat_permissions=True,
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        await message.reply(
            "تعذر كتم العضو. تأكد أن البوت مشرف ولديه صلاحية تقييد الأعضاء."
        )
        return
    except TelegramAPIError:
        await message.reply("حدث خطأ أثناء تنفيذ الكتم؛ حاول مرة أخرى.")
        return

    await message.reply(f"تم كتم {target.full_name} لمدة دقيقة واحدة.")


async def run_bot(token: str) -> None:
    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    dispatcher.include_router(games_bank_router)

    try:
        await asyncio.to_thread(initialize_storage)
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
