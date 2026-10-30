import io
import re
import unicodedata
from typing import TypedDict

from PIL import Image, ImageDraw, ImageFont


class FlagData(TypedDict):
    url: str
    name: str
    answers: list[str]


FLAGS_DATA: list[FlagData] = [
    {
        "url": "https://flagcdn.com/w640/ca.png",
        "name": "كندا",
        "answers": ["كندا"],
    },
    {
        "url": "https://flagcdn.com/w640/iq.png",
        "name": "العراق",
        "answers": ["العراق", "عراق"],
    },
    {
        "url": "https://flagcdn.com/w640/sa.png",
        "name": "السعودية",
        "answers": ["السعودية", "سعودية", "المملكة العربية السعودية"],
    },
    {
        "url": "https://flagcdn.com/w640/eg.png",
        "name": "مصر",
        "answers": ["مصر", "جمهورية مصر العربية"],
    },
    {
        "url": "https://flagcdn.com/w640/ae.png",
        "name": "الإمارات",
        "answers": ["الامارات", "الإمارات", "امارات"],
    },
    {
        "url": "https://flagcdn.com/w640/ps.png",
        "name": "فلسطين",
        "answers": ["فلسطين"],
    },
    {
        "url": "https://flagcdn.com/w640/sy.png",
        "name": "سوريا",
        "answers": ["سوريا", "سورية"],
    },
    {
        "url": "https://flagcdn.com/w640/jo.png",
        "name": "الأردن",
        "answers": ["الاردن", "الأردن", "اردن"],
    },
    {
        "url": "https://flagcdn.com/w640/kw.png",
        "name": "الكويت",
        "answers": ["الكويت", "كويت"],
    },
    {
        "url": "https://flagcdn.com/w640/qa.png",
        "name": "قطر",
        "answers": ["قطر"],
    },
    {
        "url": "https://flagcdn.com/w640/bh.png",
        "name": "البحرين",
        "answers": ["البحرين", "بحرين"],
    },
    {
        "url": "https://flagcdn.com/w640/om.png",
        "name": "عمان",
        "answers": ["عمان", "سلطنة عمان"],
    },
    {
        "url": "https://flagcdn.com/w640/ye.png",
        "name": "اليمن",
        "answers": ["اليمن", "يمن"],
    },
    {
        "url": "https://flagcdn.com/w640/dz.png",
        "name": "الجزائر",
        "answers": ["الجزائر", "جزائر"],
    },
    {
        "url": "https://flagcdn.com/w640/ma.png",
        "name": "المغرب",
        "answers": ["المغرب", "مغرب"],
    },
    {
        "url": "https://flagcdn.com/w640/tn.png",
        "name": "تونس",
        "answers": ["تونس"],
    },
    {
        "url": "https://flagcdn.com/w640/ly.png",
        "name": "ليبيا",
        "answers": ["ليبيا"],
    },
    {
        "url": "https://flagcdn.com/w640/sd.png",
        "name": "السودان",
        "answers": ["السودان", "سودان"],
    },
    {
        "url": "https://flagcdn.com/w640/us.png",
        "name": "أمريكا",
        "answers": ["امريكا", "أمريكا", "الولايات المتحدة", "الولايات المتحدة الامريكية"],
    },
    {
        "url": "https://flagcdn.com/w640/gb.png",
        "name": "بريطانيا",
        "answers": ["بريطانيا", "المملكة المتحدة", "انجلترا", "إنكلترا"],
    },
    {
        "url": "https://flagcdn.com/w640/fr.png",
        "name": "فرنسا",
        "answers": ["فرنسا"],
    },
    {
        "url": "https://flagcdn.com/w640/de.png",
        "name": "ألمانيا",
        "answers": ["المانيا", "ألمانيا"],
    },
    {
        "url": "https://flagcdn.com/w640/es.png",
        "name": "إسبانيا",
        "answers": ["اسبانيا", "إسبانيا"],
    },
    {
        "url": "https://flagcdn.com/w640/it.png",
        "name": "إيطاليا",
        "answers": ["ايطاليا", "إيطاليا"],
    },
    {
        "url": "https://flagcdn.com/w640/br.png",
        "name": "البرازيل",
        "answers": ["البرازيل", "برازيل"],
    },
    {
        "url": "https://flagcdn.com/w640/ar.png",
        "name": "الأرجنتين",
        "answers": ["الارجنتين", "الأرجنتين", "ارجنتين"],
    },
    {
        "url": "https://flagcdn.com/w640/jp.png",
        "name": "اليابان",
        "answers": ["اليابان", "يابان"],
    },
    {
        "url": "https://flagcdn.com/w640/tr.png",
        "name": "تركيا",
        "answers": ["تركيا"],
    },
]


def normalize_country_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.translate(
        str.maketrans(
            {
                "أ": "ا",
                "إ": "ا",
                "آ": "ا",
                "ٱ": "ا",
                "ى": "ي",
                "ة": "ه",
                "ـ": "",
            }
        )
    )
    return re.sub(r"[^\w]", "", value, flags=re.UNICODE)


def flag_code(flag: FlagData) -> str:
    return flag["url"].rsplit("/", 1)[-1].removesuffix(".png")


FLAG_BY_CODE = {flag_code(flag): flag for flag in FLAGS_DATA}


def accepted_country_answers(flag: FlagData) -> set[str]:
    return {normalize_country_name(answer) for answer in flag["answers"]}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(font_path, size=size)
    except OSError:
        return ImageFont.load_default()


def render_bank_card_png(account: dict[str, object]) -> bytes:
    width, height = 1100, 680
    image = Image.new("RGB", (width, height), "#101a32")
    draw = ImageDraw.Draw(image)

    for y in range(height):
        blend = y / height
        color = (
            int(16 + 12 * blend),
            int(31 + 20 * blend),
            int(58 + 35 * blend),
        )
        draw.line((0, y, width, y), fill=color)

    draw.ellipse((700, -180, 1260, 380), fill="#163b57")
    draw.ellipse((790, -95, 1190, 305), fill="#1b4a63")
    draw.rounded_rectangle(
        (12, 12, width - 13, height - 13),
        radius=40,
        outline="#91d7c5",
        width=4,
    )

    title_font = _font(48)
    label_font = _font(27)
    number_font = _font(48)
    value_font = _font(34)
    small_font = _font(22)

    draw.text((64, 62), "IBRAHIM INTERNATIONAL BANK", font=title_font, fill="white")
    draw.text((66, 132), "MASTERCARD  |  GAME POINTS", font=label_font, fill="#b8d8eb")

    card_number = str(account["card_number"])
    grouped_number = " ".join(
        card_number[index : index + 4] for index in range(0, len(card_number), 4)
    )
    draw.rounded_rectangle((66, 238, 144, 296), radius=12, fill="#d6c681")
    draw.line((84, 238, 84, 296), fill="#8c8050", width=3)
    draw.line((110, 238, 110, 296), fill="#8c8050", width=3)
    draw.line((66, 267, 144, 267), fill="#8c8050", width=3)
    draw.text((66, 346), grouped_number, font=number_font, fill="white")

    display_name = str(account["display_name"]).strip()
    if display_name.isascii() and len(display_name) > 25:
        display_name = display_name[:22] + "..."
    elif not display_name.isascii():
        display_name = "GAME MEMBER"
    draw.text((66, 455), display_name.upper(), font=value_font, fill="white")
    draw.text((66, 506), "CARD HOLDER", font=small_font, fill="#b8d8eb")

    points = int(account["points"])
    draw.text((746, 455), f"{points:,} POINTS", font=value_font, fill="#a9f0d1")
    draw.text((66, 603), "VIRTUAL GAME CARD - NOT FOR PAYMENT", font=small_font, fill="#ffc979")

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
