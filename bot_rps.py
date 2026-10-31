import asyncio
from dataclasses import dataclass
from html import escape
import logging
import secrets

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_storage import RPS_REWARD, award_points


router = Router(name="rock-paper-scissors")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RpsPlayer:
    user_id: int
    first_name: str
    username: str | None
    display_name: str


@dataclass
class RpsMatch:
    chat_id: int
    p1: RpsPlayer
    p2: RpsPlayer
    p1_choice: str | None = None
    p2_choice: str | None = None
    settling: bool = False


pending_challenges: dict[int, RpsPlayer] = {}
active_pvp_matches: dict[str, RpsMatch] = {}
state_lock = asyncio.Lock()

MOVE_LABELS = {
    "rock": "حجرة 🪨",
    "paper": "ورقة 📄",
    "scissors": "مقص ✂️",
}
P1_WINNING_MOVES = {
    ("rock", "scissors"),
    ("paper", "rock"),
    ("scissors", "paper"),
}


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.text == "تحدي",
)
async def handle_challenge(message: Message) -> None:
    user = message.from_user
    if user is None or user.is_bot:
        return

    player = RpsPlayer(
        user_id=user.id,
        first_name=user.first_name,
        username=user.username,
        display_name=user.full_name,
    )

    action: str
    match_id = ""
    async with state_lock:
        challenge = pending_challenges.get(message.chat.id)
        if challenge is None:
            pending_challenges[message.chat.id] = player
            action = "opened"
        elif challenge.user_id == player.user_id:
            action = "same_user"
        else:
            pending_challenges.pop(message.chat.id, None)
            match_id = secrets.token_hex(12)
            active_pvp_matches[match_id] = RpsMatch(
                chat_id=message.chat.id,
                p1=challenge,
                p2=player,
            )
            action = "joined"

    if action == "opened":
        await message.reply(
            f"📢 <b>{escape(player.first_name)}</b> فتح باب التحدي في حجرة ورقة مقص!\n"
            f"الجائزة: <b>{RPS_REWARD} نقطة من بنك إبراهيم الدولي</b> 🏦💰\n"
            "الشخص الثاني يكتب <b>تحدي</b> للدخول والمنافسة!",
            parse_mode="HTML",
        )
        return

    if action == "same_user":
        await message.reply(
            "⏳ أنت بالفعل فتحت التحدي! بانتظار شخص ثاني يكتب كلمة "
            "<b>تحدي</b>.",
            parse_mode="HTML",
        )
        return

    match = active_pvp_matches[match_id]
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text="🪨 حجرة",
        callback_data=f"rps:{match_id}:rock",
    )
    keyboard.button(
        text="📄 ورقة",
        callback_data=f"rps:{match_id}:paper",
    )
    keyboard.button(
        text="✂️ مقص",
        callback_data=f"rps:{match_id}:scissors",
    )
    keyboard.adjust(3)

    text = (
        "⚔️ <b>بدأ التحدي وانغلقت المشاركة!</b>\n\n"
        f"👤 {escape(match.p1.first_name)} 🆚 👤 {escape(match.p2.first_name)}\n"
        f"💰 الجائزة للفائز: <b>{RPS_REWARD} نقطة</b> تحول إلى بنك إبراهيم الدولي!\n\n"
        "كل لاعب يضغط حركته بالسر من الأزرار 👇"
    )
    await message.reply(
        text,
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML",
    )


async def _publish_result(
    callback: CallbackQuery,
    chat_id: int,
    text: str,
) -> None:
    target_message = callback.message
    if target_message is not None and hasattr(target_message, "edit_text"):
        try:
            await target_message.edit_text(
                text,
                reply_markup=None,
                parse_mode="HTML",
            )
            return
        except TelegramAPIError:
            logger.exception("Could not edit the completed RPS match message.")

    await callback.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
    )


async def _finish_match(
    callback: CallbackQuery,
    match_id: str,
    match: RpsMatch,
) -> None:
    p1_choice = match.p1_choice
    p2_choice = match.p2_choice
    if p1_choice is None or p2_choice is None:
        return

    result_text = (
        "🔔 <b>انتهت المباراة!</b>\n\n"
        f"👤 {escape(match.p1.first_name)}: {MOVE_LABELS[p1_choice]}\n"
        f"👤 {escape(match.p2.first_name)}: {MOVE_LABELS[p2_choice]}\n\n"
    )

    if p1_choice == p2_choice:
        result_text += "🤝 <b>النتيجة: تعادل!</b> لم يحصل أحد على نقاط."
    else:
        winner = (
            match.p1
            if (p1_choice, p2_choice) in P1_WINNING_MOVES
            else match.p2
        )
        try:
            account = await asyncio.to_thread(
                award_points,
                winner.user_id,
                winner.username,
                winner.display_name,
                RPS_REWARD,
            )
        except Exception:
            logger.exception("Could not deposit the RPS prize.")
            async with state_lock:
                current_match = active_pvp_matches.get(match_id)
                if current_match is match:
                    current_match.settling = False
            await callback.bot.send_message(
                chat_id=match.chat_id,
                text=(
                    "تعذر إيداع الجائزة الآن. اختياراتكما محفوظة؛ "
                    "اضغط أحد الأزرار مجدداً لإعادة المحاولة."
                ),
            )
            return

        result_text += (
            f"🏆 الفائز بالتحدي: <b>{escape(winner.first_name)}</b>! "
            "عاش البطل 🎉\n"
            f"🏦 تم إيداع <b>{RPS_REWARD} نقطة</b> في حسابك في بنك إبراهيم الدولي!\n"
            f"💳 رصيدك الجديد: <b>{int(account['points']):,} نقطة</b>."
        )

    async with state_lock:
        active_pvp_matches.pop(match_id, None)
    await _publish_result(callback, match.chat_id, result_text)


@router.callback_query(F.data.startswith("rps:"))
async def handle_rps_moves(callback: CallbackQuery) -> None:
    data_parts = (callback.data or "").split(":")
    if len(data_parts) != 3 or data_parts[0] != "rps":
        await callback.answer("⚠️ حركة غير صالحة!", show_alert=True)
        return

    _, match_id, move = data_parts
    if move not in MOVE_LABELS:
        await callback.answer("⚠️ حركة غير صالحة!", show_alert=True)
        return

    player_id = callback.from_user.id
    completed_match: RpsMatch | None = None
    error_message: str | None = None
    acknowledgement = ""

    async with state_lock:
        match = active_pvp_matches.get(match_id)
        if match is None:
            error_message = "⚠️ هذه اللعبة انتهت أو أُلغيت!"
        elif player_id not in {match.p1.user_id, match.p2.user_id}:
            error_message = "🚫 التحدي خاص باللاعبين فقط!"
        elif match.settling:
            error_message = "⏳ جارٍ إنهاء المباراة، انتظر قليلاً."
        elif match.p1_choice is not None and match.p2_choice is not None:
            match.settling = True
            completed_match = match
            acknowledgement = "اختياراتكما مسجلة، جارٍ إنهاء المباراة."
        else:
            is_player_one = player_id == match.p1.user_id
            current_choice = match.p1_choice if is_player_one else match.p2_choice
            if current_choice is not None:
                error_message = "أنت اخترت بالفعل!"
            else:
                if is_player_one:
                    match.p1_choice = move
                    opponent_name = match.p2.first_name
                else:
                    match.p2_choice = move
                    opponent_name = match.p1.first_name

                if match.p1_choice is not None and match.p2_choice is not None:
                    match.settling = True
                    completed_match = match
                    acknowledgement = (
                        f"اخترت {MOVE_LABELS[move]}! تم تسجيل اختيارك."
                    )
                else:
                    acknowledgement = (
                        f"اخترت {MOVE_LABELS[move]}! بانتظار "
                        f"{escape(opponent_name)}..."
                    )

    try:
        await callback.answer(
            error_message or acknowledgement,
            show_alert=True,
        )
    except TelegramAPIError:
        logger.debug("Could not acknowledge an RPS callback query.")

    if error_message is not None or completed_match is None:
        return

    await _finish_match(callback, match_id, completed_match)
