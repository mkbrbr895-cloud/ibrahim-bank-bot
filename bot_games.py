import asyncio
from dataclasses import dataclass, field
import random
import re
from html import escape

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.types import Message


router = Router(name="text-games")
GROUP_TYPES = {"group", "supergroup"}

GAMES_MENU_PATTERN = re.compile(r"^\s*(?:العاب|الألعاب)\s*$")
NUMBER_START_PATTERN = re.compile(r"^\s*(?:بدء التخمين|خمن)\s*$")
NUMBER_GUESS_PATTERN = re.compile(r"^\s*(?:تخمين\s+)?(?P<guess>\d{1,3})\s*$")
DICE_PATTERN = re.compile(r"^\s*(?:نرد|النرد)\s*$")
RAFFLE_START_PATTERN = re.compile(r"^\s*قرعة\s*$")
RAFFLE_JOIN_PATTERN = re.compile(r"^\s*مشاركة\s*$")
RAFFLE_DRAW_PATTERN = re.compile(r"^\s*سحب القرعة\s*$")

GAMES_MENU_MESSAGE = (
    "══════════════════\n"
    "🎮 الألعاب المتوفرة وطريقة تشغيلها\n"
    "▫️ اعلام أو أعلام ↢ ابدأ لعبة تخمين أعلام الدول؛ أول إجابة صحيحة تفوز بـ50 نقطة.\n"
    "▫️ تحدي ↢ ابدأ تحدي حجرة ورقة مقص مع عضو آخر؛ الفائز يحصل على 250 نقطة.\n"
    "▫️ بدء التخمين أو خمن ↢ ابدأ تخمين رقم من 1 إلى 50؛ أرسل الرقم مباشرة مثل 30 أو اكتب «تخمين 30».\n"
    "▫️ نرد أو النرد ↢ ارمِ نرداً من 1 إلى 6، بلا نقاط.\n"
    "▫️ قرعة ↢ ابدأ القرعة، ثم اكتب مشاركة للانضمام، واكتب سحب القرعة لاختيار فائز عشوائي؛ بلا نقاط.\n"
    "══════════════════"
)

active_number_games: dict[int, int] = {}
number_game_lock = asyncio.Lock()


@dataclass(frozen=True)
class RaffleParticipant:
    user_id: int
    full_name: str


@dataclass
class RaffleState:
    participants: dict[int, RaffleParticipant] = field(default_factory=dict)


active_raffles: dict[int, RaffleState] = {}
raffle_lock = asyncio.Lock()


class ActiveNumberGuessFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return (
            message.chat.type in GROUP_TYPES
            and message.chat.id in active_number_games
            and message.text is not None
            and NUMBER_GUESS_PATTERN.fullmatch(message.text) is not None
        )


class ActiveRaffleFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return (
            message.chat.type in GROUP_TYPES
            and message.chat.id in active_raffles
            and message.text is not None
            and RAFFLE_JOIN_PATTERN.fullmatch(message.text) is not None
        )


def _raffle_participant(message: Message) -> RaffleParticipant | None:
    user = message.from_user
    if user is None or user.is_bot:
        return None
    return RaffleParticipant(user_id=user.id, full_name=user.full_name)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.regexp(GAMES_MENU_PATTERN),
)
async def show_games_menu(message: Message) -> None:
    await message.answer(GAMES_MENU_MESSAGE)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.regexp(NUMBER_START_PATTERN),
)
async def start_number_guessing(message: Message) -> None:
    user = message.from_user
    if user is None or user.is_bot:
        return

    async with number_game_lock:
        if message.chat.id in active_number_games:
            already_active = True
        else:
            active_number_games[message.chat.id] = random.randint(1, 50)
            already_active = False

    if already_active:
        await message.reply(
            "⏳ توجد جولة تخمين نشطة بالفعل في هذه المجموعة. "
            "خمن الرقم من 1 إلى 50."
        )
        return

    await message.reply(
        f"🎯 بدأت لعبة تخمين الرقم من 1 إلى 50!\n"
        f"اكتب الرقم مباشرة أو اكتب «تخمين 30». بالتوفيق يا {escape(user.first_name)}!"
    )


@router.message(ActiveNumberGuessFilter())
async def handle_number_guess(message: Message) -> None:
    user = message.from_user
    text = message.text
    if user is None or user.is_bot or text is None:
        return

    matched = NUMBER_GUESS_PATTERN.fullmatch(text)
    if matched is None:
        return

    guess = int(matched.group("guess"))
    if not 1 <= guess <= 50:
        await message.reply("اكتب رقماً من 1 إلى 50.")
        return

    async with number_game_lock:
        secret = active_number_games.get(message.chat.id)
        if secret is None:
            return
        if guess < secret:
            result = "higher"
        elif guess > secret:
            result = "lower"
        else:
            active_number_games.pop(message.chat.id, None)
            result = "correct"

    if result == "higher":
        await message.reply("⬆️ فوق! (الرقم المطلوب أكبر).")
    elif result == "lower":
        await message.reply("⬇️ أقل! (الرقم المطلوب أصغر).")
    else:
        await message.reply(
            f"🎉 مبروك <b>{escape(user.full_name)}</b>! "
            f"عرفت الرقم الصحيح وهو <b>{secret}</b>، وانتهت الجولة.",
            parse_mode="HTML",
        )


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.regexp(DICE_PATTERN),
)
async def roll_dice(message: Message) -> None:
    user = message.from_user
    if user is None or user.is_bot:
        return

    result = random.randint(1, 6)
    await message.reply(
        f"🎲 {escape(user.first_name)} رمى النرد وظهرت له {result} من 6."
    )


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.regexp(RAFFLE_START_PATTERN),
)
async def start_raffle(message: Message) -> None:
    participant = _raffle_participant(message)
    if participant is None:
        return

    async with raffle_lock:
        raffle = active_raffles.get(message.chat.id)
        if raffle is None:
            raffle = RaffleState()
            raffle.participants[participant.user_id] = participant
            active_raffles[message.chat.id] = raffle
            created = True
        else:
            created = False

    if created:
        await message.reply(
            "🎟️ بدأت القرعة وأنت مسجل فيها!\n"
            "للانضمام اكتب «مشاركة»، ولإجراء السحب اكتب «سحب القرعة»."
        )
    else:
        await message.reply(
            "⏳ توجد قرعة مفتوحة بالفعل. اكتب «مشاركة» للانضمام، "
            "أو «سحب القرعة» لاختيار الفائز."
        )


@router.message(ActiveRaffleFilter())
async def join_raffle(message: Message) -> None:
    participant = _raffle_participant(message)
    if participant is None:
        return

    async with raffle_lock:
        raffle = active_raffles.get(message.chat.id)
        if raffle is None:
            return
        if participant.user_id in raffle.participants:
            already_joined = True
        else:
            raffle.participants[participant.user_id] = participant
            already_joined = False
        participant_count = len(raffle.participants)

    if already_joined:
        await message.reply("أنت مسجل في القرعة بالفعل.")
    else:
        await message.reply(
            f"✅ تم تسجيلك في القرعة. عدد المشاركين الآن: {participant_count}."
        )


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.regexp(RAFFLE_DRAW_PATTERN),
)
async def draw_raffle(message: Message) -> None:
    async with raffle_lock:
        raffle = active_raffles.get(message.chat.id)
        if raffle is None:
            result = "missing"
            winner = None
            participant_count = 0
        elif len(raffle.participants) < 2:
            result = "not_enough"
            winner = None
            participant_count = len(raffle.participants)
        else:
            winner = random.choice(tuple(raffle.participants.values()))
            participant_count = len(raffle.participants)
            active_raffles.pop(message.chat.id, None)
            result = "drawn"

    if result == "missing":
        await message.reply("لا توجد قرعة مفتوحة. اكتب «قرعة» لبدء واحدة.")
    elif result == "not_enough":
        await message.reply(
            f"تحتاج القرعة إلى مشاركين على الأقل؛ المسجلون حالياً: {participant_count}."
        )
    elif winner is not None:
        await message.reply(
            f"🎉 الفائز بالقرعة هو <b>{escape(winner.full_name)}</b> "
            f"من بين {participant_count} مشاركين!",
            parse_mode="HTML",
        )
