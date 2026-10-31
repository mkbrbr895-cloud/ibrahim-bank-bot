import asyncio
import random
import re

from aiogram import F, Router
from aiogram.types import BufferedInputFile, Message

from bot_storage import (
    FLAG_REWARD,
    TRANSFER_FEE,
    active_flag_country,
    claim_flag_answer,
    create_or_get_account,
    deposit_salary,
    start_flag_game,
    transfer_points,
)
from bot_visuals import (
    FLAG_BY_CODE,
    FLAGS_DATA,
    accepted_country_answers,
    flag_code,
    normalize_country_name,
    render_bank_card_png,
)


router = Router(name="games-and-bank")

HELP_COMMAND_PATTERN = re.compile(
    r"^\s*/?(?:اوامر|الأوامر|مساعدة|help)(?:@[A-Za-z0-9_]+)?\s*$",
    re.IGNORECASE,
)
FLAG_START_PATTERN = re.compile(r"^\s*(?:اعلام|أعلام)\s*$")
BANK_COMMAND_PATTERN = re.compile(r"^\s*/?(?:حسابي|بنك)(?:@[A-Za-z0-9_]+)?\s*$")
SALARY_COMMAND_PATTERN = re.compile(r"^\s*/?راتب(?:@[A-Za-z0-9_]+)?\s*$")
TRANSFER_COMMAND_PATTERN = re.compile(
    r"^\s*/?تحويل(?:@[A-Za-z0-9_]+)?(?:\s+.*)?$"
)
MAX_TRANSFER_AMOUNT = 1_000_000_000_000
SALARY_JOBS = (
    ("عامل نظافة 🧑🏼‍🔧", 300, 80),
    ("صباغ 💅🏼", 500, 50),
    ("دكتور 🧑🏼‍🔬", 1000, 40),
    ("واحد ماكل مندي 🍗", 10_000, 10),
)

HELP_MESSAGE = (
    "══════════════════\n"
    "🏛️ دليل أوامر بنك إبراهيم الدولي 🏛️\n"
    "══════════════════\n"
    "💳 الخدمات البنكية:\n"
    "▫️ حسابي أو بنك ↢ لعرض بطاقتك البنكية ورصيدك الحالي.\n"
    "▫️ راتب ↢ لاستلام وظيفتك العشوائية وراتبك مع البخشيش (متاح كل ساعة).\n"
    "▫️ تحويل [المبلغ] ↢ بالرد على رسالة العضو لتحويل النقاط له (عمولة 10 نقاط).\n"
    "🎮 الألعاب والتسلية:\n"
    "▫️ اعلام ↢ لبدء لعبة تخمين أعلام الدول والحصول على 50 نقطة.\n"
    "▫️ تحدي ↢ للعب حجرة ورقة مقص والفوز بـ250 نقطة.\n"
    "══════════════════\n"
    "👑 المطور: @Ibrahimroblox14GRM\n"
    "══════════════════"
)


def _display_card_number(card_number: str) -> str:
    return " ".join(card_number[index : index + 4] for index in range(0, 16, 4))


@router.message(F.text.regexp(HELP_COMMAND_PATTERN))
async def show_help(message: Message) -> None:
    await message.answer(HELP_MESSAGE)


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.text,
    F.text.regexp(FLAG_START_PATTERN),
)
async def start_flag_game_handler(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("لعبة الأعلام متاحة داخل المجموعات فقط.")
        return

    current_code = await asyncio.to_thread(active_flag_country, message.chat.id)
    choices = [flag for flag in FLAGS_DATA if flag_code(flag) != current_code]
    flag = random.choice(choices or FLAGS_DATA)
    country_code = flag_code(flag)

    await asyncio.to_thread(
        start_flag_game,
        message.chat.id,
        country_code,
        message.from_user.id if message.from_user else 0,
    )
    await message.bot.send_photo(
        chat_id=message.chat.id,
        photo=flag["url"],
        caption="خمن علم أي دولة هذا؟ 🤔",
    )


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.text,
    F.text.regexp(BANK_COMMAND_PATTERN),
)
async def show_bank_account(message: Message) -> None:
    user = message.from_user
    if user is None:
        return

    account = await asyncio.to_thread(
        create_or_get_account,
        user.id,
        user.username,
        user.full_name,
    )
    card_number = str(account["card_number"])
    image_data = await asyncio.to_thread(render_bank_card_png, account)
    photo = BufferedInputFile(image_data, filename="ibrahim-game-points-card.png")
    caption = (
        "💳 ماستر كارد - بنك إبراهيم الدولي\n"
        "بطاقة نقاط افتراضية للعبة فقط، وليست بطاقة دفع حقيقية.\n"
        f"صاحب الحساب: {user.full_name}\n"
        f"رقم البطاقة: {_display_card_number(card_number)}\n"
        f"رصيدك: {int(account['points']):,} نقطة"
    )
    await message.answer_photo(photo=photo, caption=caption)


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.text,
    F.text.regexp(SALARY_COMMAND_PATTERN),
)
async def claim_salary_handler(message: Message) -> None:
    user = message.from_user
    if user is None:
        return

    job_name, base_salary, _weight = random.choices(
        SALARY_JOBS,
        weights=[job[2] for job in SALARY_JOBS],
        k=1,
    )[0]
    tip = random.randint(1, 100)
    result = await asyncio.to_thread(
        deposit_salary,
        user.id,
        user.username,
        user.full_name,
        base_salary,
        tip,
    )

    if result["status"] == "cooldown":
        await message.reply(
            "⏳ لقد استلمت راتبك مؤخراً! يرجى الانتظار "
            f"{int(result['remaining_minutes'])} دقيقة لاستلام راتبك القادم."
        )
        return

    account = result["account"]
    await message.reply(
        f"💼 وظيفتك: {job_name}\n"
        f"الراتب الأساسي: {base_salary:,} نقطة\n"
        f"دلعتك واعطيتك بخشيش {tip} نقطة 😉\n"
        f"إجمالي الإيداع: {base_salary + tip:,} نقطة\n"
        "رصيدك الجديد في بنك إبراهيم الدولي: "
        f"{int(account['points']):,} نقطة"
    )


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.text,
    F.text.regexp(TRANSFER_COMMAND_PATTERN),
)
async def transfer_points_handler(message: Message) -> None:
    sender = message.from_user
    if sender is None or message.text is None:
        return

    parts = message.text.strip().split()
    arguments = parts[1:]
    if not arguments:
        await message.reply(
            "طريقة الاستخدام:\n"
            "• ردّ على رسالة العضو واكتب تحويل <المبلغ> أو /تحويل <المبلغ>\n"
            "• أو اكتب /تحويل <المبلغ> <رقم البطاقة>"
        )
        return

    try:
        amount = int(arguments[0])
    except ValueError:
        await message.reply("المبلغ يجب أن يكون عددًا صحيحًا من النقاط.")
        return

    if not 1 <= amount <= MAX_TRANSFER_AMOUNT:
        await message.reply("اختر مبلغًا موجبًا صالحًا.")
        return

    recipient_user = None
    recipient_card_number = None
    if message.reply_to_message and len(arguments) == 1:
        recipient_user = message.reply_to_message.from_user
        if recipient_user is None:
            await message.reply("لم أتمكن من تحديد صاحب الرسالة التي رددت عليها.")
            return
        if recipient_user.is_bot:
            await message.reply("لا يمكن تحويل النقاط إلى حساب بوت.")
            return
    elif not message.reply_to_message and len(arguments) == 2:
        recipient_card_number = arguments[1]
        if not re.fullmatch(r"[0-9]{16}", recipient_card_number):
            await message.reply("رقم البطاقة يجب أن يتكون من 16 رقمًا.")
            return
    else:
        await message.reply(
            "ردّ على رسالة المستلم واكتب تحويل <المبلغ> أو /تحويل <المبلغ>، "
            "أو استخدم /تحويل <المبلغ> <رقم البطاقة>."
        )
        return

    result = await asyncio.to_thread(
        transfer_points,
        sender.id,
        sender.username,
        sender.full_name,
        amount,
        recipient_user.id if recipient_user else None,
        recipient_user.username if recipient_user else None,
        recipient_user.full_name if recipient_user else None,
        recipient_card_number,
    )
    status = result["status"]

    if status == "no_account":
        await message.reply("أنشئ حسابك أولًا باستخدام /حسابي أو /بنك.")
    elif status == "unknown_card":
        await message.reply("لم أجد حسابًا بهذا الرقم.")
    elif status == "missing_recipient":
        await message.reply("حدد المستلم بالرد على رسالته أو برقم بطاقته.")
    elif status == "self_transfer":
        await message.reply("لا يمكنك تحويل النقاط إلى حسابك.")
    elif status == "insufficient_balance":
        await message.reply(
            f"رصيدك غير كافٍ. تحتاج إلى {int(result['required']):,} نقطة "
            f"شاملة العمولة، ورصيدك {int(result['balance']):,} نقطة."
        )
    elif status == "ok":
        recipient = result["recipient"]
        sender_account = result["sender"]
        await message.reply(
            f"تم تحويل {amount:,} نقطة إلى {recipient['display_name']}.\n"
            f"العمولة: {TRANSFER_FEE} نقاط أُضيفت إلى حساب المطور.\n"
            f"رصيدك الجديد: {int(sender_account['points']):,} نقطة."
        )


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.text,
)
async def guess_flag_handler(message: Message) -> None:
    user = message.from_user
    text = message.text
    if user is None or text is None or text.strip().startswith("/"):
        return
    if message.chat.type not in {"group", "supergroup"}:
        return
    country_code = await asyncio.to_thread(active_flag_country, message.chat.id)
    flag = FLAG_BY_CODE.get(country_code or "")
    if flag is None:
        return

    winner = await asyncio.to_thread(
        claim_flag_answer,
        message.chat.id,
        country_code,
        normalize_country_name(text),
        accepted_country_answers(flag),
        user.id,
        user.username,
        user.full_name,
    )
    if winner is None:
        return

    await message.answer(
        f"🎉 مبروك {user.full_name}! الدولة هي {flag['name']}.\n"
        f"حصلت على {FLAG_REWARD} نقطة، ورصيدك الآن "
        f"{int(winner['points']):,} نقطة."
    )
