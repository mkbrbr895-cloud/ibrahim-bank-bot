from dataclasses import dataclass
import io
import math
import re
import unicodedata

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    answers: tuple[str, ...]


COUNTRIES = (
    Country("sa", "السعودية", ("السعودية", "السعوديه", "المملكة العربية السعودية", "saudi arabia")),
    Country("iq", "العراق", ("العراق", "جمهورية العراق", "iraq")),
    Country("eg", "مصر", ("مصر", "جمهورية مصر العربية", "egypt")),
    Country("ma", "المغرب", ("المغرب", "المملكة المغربية", "morocco")),
    Country("ae", "الإمارات", ("الإمارات", "الامارات", "الإمارات العربية المتحدة", "uae", "united arab emirates")),
    Country("fr", "فرنسا", ("فرنسا", "france")),
    Country("jp", "اليابان", ("اليابان", "japan")),
    Country("qa", "قطر", ("قطر", "qatar")),
    Country("kw", "الكويت", ("الكويت", "kuwait")),
    Country("jo", "الأردن", ("الأردن", "الاردن", "jordan")),
    Country("ps", "فلسطين", ("فلسطين", "palestine")),
    Country("tr", "تركيا", ("تركيا", "turkey", "türkiye")),
    Country("de", "ألمانيا", ("ألمانيا", "المانيا", "germany", "deutschland")),
    Country("it", "إيطاليا", ("إيطاليا", "ايطاليا", "italy", "italia")),
    Country("es", "إسبانيا", ("إسبانيا", "اسبانيا", "spain", "españa")),
    Country("br", "البرازيل", ("البرازيل", "brazil", "brasil")),
    Country("ar", "الأرجنتين", ("الأرجنتين", "الارجنتين", "argentina")),
    Country("ca", "كندا", ("كندا", "canada")),
    Country("tn", "تونس", ("تونس", "tunisia")),
    Country("om", "عُمان", ("عمان", "عُمان", "oman")),
    Country("lb", "لبنان", ("لبنان", "lebanon")),
    Country("sy", "سوريا", ("سوريا", "سورية", "syria")),
    Country("ye", "اليمن", ("اليمن", "yemen")),
    Country("in", "الهند", ("الهند", "india")),
    Country("cn", "الصين", ("الصين", "china")),
    Country("id", "إندونيسيا", ("إندونيسيا", "اندونيسيا", "indonesia")),
)

COUNTRY_BY_CODE = {country.code: country for country in COUNTRIES}


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


def accepted_country_answers(country: Country) -> set[str]:
    return {normalize_country_name(answer) for answer in country.answers}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(font_path, size=size)
    except OSError:
        return ImageFont.load_default()


def _star_points(cx: float, cy: float, outer: float, inner: float) -> list[tuple[float, float]]:
    points = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = math.radians(-90 + index * 36)
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return points


def _draw_crescent(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, color: str) -> None:
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    offset = int(radius * 0.38)
    draw.ellipse(
        (x - radius + offset, y - radius, x + radius + offset, y + radius),
        fill="#d91f35",
    )


def render_flag_png(country_code: str) -> bytes:
    width, height = 900, 600
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    def horizontal(colors: tuple[str, ...]) -> None:
        stripe_height = height / len(colors)
        for index, color in enumerate(colors):
            top = round(index * stripe_height)
            bottom = round((index + 1) * stripe_height)
            draw.rectangle((0, top, width, bottom), fill=color)

    def vertical(colors: tuple[str, ...]) -> None:
        stripe_width = width / len(colors)
        for index, color in enumerate(colors):
            left = round(index * stripe_width)
            right = round((index + 1) * stripe_width)
            draw.rectangle((left, 0, right, height), fill=color)

    if country_code == "sa":
        image.paste("#006c35", (0, 0, width, height))
        draw.rounded_rectangle((245, 250, 655, 266), radius=8, fill="white")
        draw.polygon(
            ((628, 258), (682, 246), (693, 252), (642, 268)),
            fill="white",
        )
        draw.line((340, 290, 620, 290), fill="white", width=10)
    elif country_code == "iq":
        horizontal(("#ce1126", "white", "black"))
        for cx in (365, 450, 535):
            draw.polygon(_star_points(cx, 300, 22, 9), fill="#007a3d")
    elif country_code == "eg":
        horizontal(("#ce1126", "white", "black"))
        draw.ellipse((416, 245, 484, 313), fill="#c09300")
        draw.polygon(
            ((450, 255), (432, 286), (450, 301), (468, 286)),
            fill="#f6d04d",
        )
    elif country_code == "ma":
        image.paste("#c1272d", (0, 0, width, height))
        draw.polygon(
            _star_points(450, 300, 92, 36),
            outline="#006233",
            fill="#c1272d",
            width=12,
        )
    elif country_code == "ae":
        horizontal(("#00732f", "white", "black"))
        draw.rectangle((0, 0, 205, height), fill="#ff0000")
    elif country_code == "fr":
        vertical(("#0055a4", "white", "#ef4135"))
    elif country_code == "jp":
        draw.ellipse((330, 180, 570, 420), fill="#bc002d")
    elif country_code == "qa":
        image.paste("#8a1538", (0, 0, width, height))
        draw.polygon(
            (
                (0, 0), (225, 0), (265, 50), (225, 100), (265, 150),
                (225, 200), (265, 250), (225, 300), (265, 350),
                (225, 400), (265, 450), (225, 500), (265, 550), (225, 600), (0, 600),
            ),
            fill="white",
        )
    elif country_code == "kw":
        horizontal(("#007a3d", "white", "#ce1126"))
        draw.polygon(((0, 0), (190, 90), (190, 510), (0, 600)), fill="black")
    elif country_code in {"jo", "ps"}:
        horizontal(("black", "white", "#007a3d"))
        draw.polygon(((0, 0), (300, 300), (0, 600)), fill="#ce1126")
        if country_code == "jo":
            draw.polygon(_star_points(108, 300, 40, 17), fill="white")
    elif country_code == "tr":
        image.paste("#e30a17", (0, 0, width, height))
        draw.ellipse((245, 175, 495, 425), fill="white")
        draw.ellipse((300, 205, 510, 395), fill="#e30a17")
        draw.polygon(_star_points(525, 300, 62, 25), fill="white")
    elif country_code == "de":
        horizontal(("black", "#dd0000", "#ffce00"))
    elif country_code == "it":
        vertical(("#009246", "white", "#ce2b37"))
    elif country_code == "es":
        horizontal(("#aa151b", "#f1bf00", "#aa151b"))
        draw.rectangle((0, 120, width, 480), fill="#f1bf00")
        draw.rectangle((0, 0, width, 120), fill="#aa151b")
        draw.rectangle((0, 480, width, 600), fill="#aa151b")
        draw.ellipse((255, 255, 305, 345), fill="#aa151b")
    elif country_code == "br":
        image.paste("#009b3a", (0, 0, width, height))
        draw.polygon(((450, 80), (795, 300), (450, 520), (105, 300)), fill="#ffdf00")
        draw.ellipse((320, 170, 580, 430), fill="#002776")
    elif country_code == "ar":
        horizontal(("#74acdf", "white", "#74acdf"))
        draw.ellipse((405, 255, 495, 345), fill="#f6b40e")
    elif country_code == "ca":
        vertical(("#d80621", "white", "#d80621"))
        draw.polygon(
            (
                (450, 205), (480, 255), (525, 245), (505, 290),
                (540, 315), (492, 325), (500, 385), (450, 350),
                (400, 385), (408, 325), (360, 315), (395, 290),
                (375, 245), (420, 255),
            ),
            fill="#d80621",
        )
    elif country_code == "tn":
        image.paste("#e70013", (0, 0, width, height))
        draw.ellipse((335, 185, 565, 415), fill="white")
        draw.ellipse((390, 235, 500, 365), fill="#e70013")
        draw.ellipse((420, 235, 530, 365), fill="white")
        draw.polygon(_star_points(477, 300, 43, 18), fill="#e70013")
    elif country_code == "om":
        horizontal(("white", "#d01c1f", "#008000"))
        draw.rectangle((0, 0, 205, height), fill="#d01c1f")
    elif country_code == "lb":
        horizontal(("#ed1c24", "white", "#ed1c24"))
        draw.rectangle((0, 120, width, 480), fill="white")
        draw.polygon(
            ((450, 220), (420, 310), (450, 290), (480, 310)),
            fill="#00a651",
        )
    elif country_code == "sy":
        horizontal(("#ce1126", "white", "black"))
        for cx in (355, 450, 545):
            draw.polygon(_star_points(cx, 300, 24, 10), fill="#007a3d")
    elif country_code == "ye":
        horizontal(("#ce1126", "white", "black"))
    elif country_code == "in":
        horizontal(("#ff9933", "white", "#138808"))
        draw.ellipse((399, 249, 501, 351), outline="#000080", width=8)
        draw.ellipse((440, 290, 460, 310), fill="#000080")
    elif country_code == "cn":
        image.paste("#de2910", (0, 0, width, height))
        draw.polygon(_star_points(180, 165, 70, 28), fill="#ffde00")
        for cx, cy in ((290, 100), (345, 160), (345, 235), (290, 290)):
            draw.polygon(_star_points(cx, cy, 25, 10), fill="#ffde00")
    elif country_code == "id":
        horizontal(("#ce1126", "white"))
    else:
        image.paste("#1d3557", (0, 0, width, height))

    draw.rectangle((2, 2, width - 3, height - 3), outline="#e8edf5", width=4)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


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
