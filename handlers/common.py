"""Kirish kodi, taklif va To'lov ID. Profil/qurilmalar — `handlers/profile.py`.

`/start` bosilishi bilan doimiy menyu (`menu.py`) va kod yuboriladi.

**Taklif havolasi:** `t.me/<bot>?start=<INVITE_CODE>`. Telegram payload'ni
`/start` argumenti sifatida beradi; biz uni `PendingInvite` ga yozamiz va
o'sha odam saytga/ilovaga kirib ro'yxatdan o'tgach taklif hisobga olinadi
(`backend/apps/accounts/invites.py`). Shu bois taklif havolasi SAYTGA emas,
aynan BOTGA olib boradi — aks holda kim taklif qilgani yo'qolardi.

`/taklif` (yoki `/invite`) buyrug'i o'z havolangiz va hisobingizni ko'rsatadi.
`/tolov` (yoki `/payment`) — Paynet'da kiritiladigan **To'lov ID** (chat id).
Click orqali to'lash uchun ID kerak emas — saytdagi tugma yetarli.
"""
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from menu import BTN_CODE, BTN_ID_PREFIX, BTN_INVITE, main_menu
from settings import SITE_URL
from services import invite_summary, issue_code, remember_invite

logger = logging.getLogger(__name__)
router = Router()

#: Ikki qator tashlash. Escape ishlatmaymiz — shunda matn ko‘chirilganda buzilmaydi.
BLANK_LINE = chr(10) * 2

NEW_CODE = "new_code"
INVITE = "invite"


def _is_public_url(url: str) -> bool:
    """Telegram inline tugmasi faqat public HTTPS (yoki tg://) qabul qiladi.

    `http://localhost` yoki bo'sh URL bo'lsa Telegram xato beradi, shuning
    uchun bunday hollarda "Saytga o'tish" tugmasi tushirib qoldiriladi.
    """
    return url.startswith("https://") and "localhost" not in url and "127.0.0.1" not in url


def keyboard() -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton(text="🔄 Yangi kod", callback_data=NEW_CODE),
        InlineKeyboardButton(text="🎁 Taklif qilish", callback_data=INVITE),
    ]]
    if _is_public_url(SITE_URL):
        buttons.append([InlineKeyboardButton(text="🌐 Saytga o'tish", url=SITE_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def invite_keyboard(link: str) -> InlineKeyboardMarkup:
    """Havolani do'stga yuborish uchun tugma.

    `t.me/share/url?...` — Telegram'ning o'z ulashish oynasini ochadi:
    foydalanuvchi chat tanlaydi va tayyor xabar ketadi. Bot uchun "inline
    mode" yoqilishi shart emas (u alohida sozlama talab qiladi va yoqilmagan
    bo'lsa tugma umuman ishlamasdi).
    """
    from urllib.parse import quote

    share = (
        "https://t.me/share/url?url=" + quote(link, safe="")
        + "&text=" + quote(SHARE_TEXT, safe="")
    )
    buttons = [[InlineKeyboardButton(text="📤 Do'stga yuborish", url=share)]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def code_text(code: str, ttl: int) -> str:
    # Lokal ishlashda saytga o'tish tugmasi bo'lmagani uchun URL'ni matnda beramiz.
    site_line = "" if _is_public_url(SITE_URL) else f"\n\n🌐 {SITE_URL}"
    return (
        f"🔑 Saytga kirish kodingiz:\n\n"
        f"<code>{code}</code>\n\n"
        f"Kod <b>{ttl} soniya</b> amal qiladi.\n"
        f"Uni saytdagi kirish oynasiga kiriting."
        f"{site_line}\n\n"
        f"⚠️ Kodni hech kimga bermang."
    )


INVITED_NOTE = (
    "🎁 Siz do'stingizning taklif havolasi orqali keldingiz — "
    "ro'yxatdan o'tsangiz u sovg'aga bir qadam yaqinlashadi."
)

SHARE_TEXT = (
    "Ingliz tilida listening yaxshilash uchun"
    "Shu havola orqali qo'shiling"
)

TOO_FAST = "⏳ Juda tez-tez so'ralmoqda. Bir daqiqadan keyin urinib ko'ring."


def menu_intro(telegram_id: int) -> str:
    return (
        "👋 Xush kelibsiz! Pastdagi menyudan foydalaning." + BLANK_LINE +
        f"🆔 To'lov ID: <code>{telegram_id}</code>" + chr(10) +
        "Paynet orqali to'lashda aynan shu raqamni kiriting."
    )


async def send_menu(message: Message) -> None:
    """Doimiy menyu (pastdagi klaviatura) — `/start` da bir marta yetarli,
    Telegram uni keyingi xabarlarda ham saqlaydi. Ilgari bot faqat kod va
    taklif berardi; profil, tarif, qurilmalar va ID uchun joy yo'q edi."""
    await message.answer(menu_intro(message.from_user.id), reply_markup=main_menu(message.from_user.id))


async def give_code(message: Message) -> None:
    user = message.from_user
    code, ttl = await issue_code(user.id, user.username or "", user.first_name or "")

    if code is None:
        await message.answer(TOO_FAST)
        return

    await message.answer(code_text(code, ttl), reply_markup=keyboard())


INVITE_CODE_RE = re.compile(r"^[A-Za-z0-9]{4,12}$")


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject) -> None:
    """`t.me/<bot>?start=<KOD>` — taklif havolasi orqali kirish.

    Payload taklif kodiga o'xshasa eslab qolamiz. Kod baribir beriladi:
    odam bu yerga kirishga kelgan, taklif esa fon ishi.
    """
    payload = (command.args or "").strip()
    if payload and INVITE_CODE_RE.match(payload):
        try:
            if await remember_invite(message.from_user.id, payload):
                await message.answer(INVITED_NOTE)
        except Exception:
            logger.exception("Taklif havolasini saqlab bo'lmadi")
    await send_menu(message)
    await give_code(message)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """/start — menyu va darrov kod."""
    await send_menu(message)
    await give_code(message)


@router.message(Command("kod"))
@router.message(F.text == BTN_CODE)
async def cmd_code(message: Message) -> None:
    await give_code(message)


NOT_REGISTERED = (
    "Avval saytga yoki ilovaga kirib ro'yxatdan o'ting — "
    "shundan keyin taklif havolangiz paydo bo'ladi."
)


def invite_text(data: dict) -> str:
    """Taklif xabari — `/taklif` buyrug'i va 🎁 tugmasi uchun umumiy."""
    link = data["link"] or data["code"]
    lines = [
        "🎁 <b>Do'stlaringizni taklif qiling</b>",
        "",
        "Havolangiz:",
        f"<code>{link}</code>",
        "",
        f"Jami taklif qilganingiz: <b>{data['invited_total']}</b>",
    ]
    if data["next_reward_left"]:
        plan = (data["next_reward_plan"] or "").upper()
        lines.append(f"Yana <b>{data['next_reward_left']}</b> ta — 1 oylik {plan} sovg'a.")
    lines += [
        "",
        "Sovg'alar: har 20 ta yangi foydalanuvchi — 1 oy PLUS, "
        "har 40 tasi — 1 oy PRO.",
        "",
        "Do'stingiz havolani bosib botga kiradi, keyin saytda ism va "
        "darajasini belgilaydi — taklif ANA SHUNDAN KEYIN hisobga olinadi.",
    ]
    return "\n".join(lines)


@router.message(Command("taklif"))
@router.message(Command("invite"))
@router.message(F.text == BTN_INVITE)
async def cmd_invite(message: Message) -> None:
    """O'z taklif havolangiz + nechta odam olib kelganingiz."""
    data = await invite_summary(message.from_user.id)
    if data is None:
        await message.answer(NOT_REGISTERED)
        return
    await message.answer(
        invite_text(data),
        reply_markup=invite_keyboard(data["link"] or data["code"]),
    )


@router.message(Command("tolov"))
@router.message(Command("payment"))
@router.message(F.text.startswith(BTN_ID_PREFIX))
async def cmd_payment(message: Message) -> None:
    """To'lov ID — Paynet kassasida kiritiladigan raqam.

    Paynet redirect'li checkout emas: foydalanuvchi Paynet ilovasida yoki
    kassada o'zi to'laydi va bizni FAQAT shu raqam orqali taniydi (u
    `User.telegram_id`). Raqam uzun va yodda qolmaydi, shu bois bot uni
    istalgan paytda qaytarib bera olishi kerak.

    Ataylab ALOHIDA xabar bilan yuboriladi (bitta qatorda, formatlanmagan) —
    Telegram'da bosib nusxa olish oson bo'lsin.
    """
    await message.answer(
        "<b>To'lov ID</b> — Paynet'da aynan shu raqamni kiriting:"
    )
    # Faqat raqam: Telegram'da ustiga bosib nusxa olinadi.
    await message.answer(f"<code>{message.from_user.id}</code>")
    await message.answer(
        "Paynet ilovasi yoki kassasida <b>listening.uz</b> xizmatini tanlang, "
        "shu ID ni kiriting va summani to'lang. Pul tushishi bilan shu yerga "
        "xabar keladi — tarifni tugma bilan tanlaysiz (/balans)." + BLANK_LINE +
        # Click butunlay boshqa oqim: u yerda ID kerak emas, saytdagi tugma
        # foydalanuvchini to'g'ridan-to'g'ri my.click.uz ga olib boradi.
        "Karta bilan tezroq to'lamoqchi bo'lsangiz — saytdagi "
        "<b>Click</b> tugmasi (bu ID kerak emas):" + BLANK_LINE +
        f"{SITE_URL}/profile/billing"
    )


@router.callback_query(F.data == INVITE)
async def on_invite(callback: CallbackQuery) -> None:
    """🎁 tugmasi — saytga kirmasdan ham taklif qilish mumkin bo'lsin.

    Foydalanuvchi talabi: "botga ham taklif qilish uchun tugma kerak, faqat
    saytga kirib olish shart emas". Xabar ALOHIDA yuboriladi (kod xabarini
    tahrirlamaydi) — kod hali amal qilayotgan bo'lishi mumkin.
    """
    data = await invite_summary(callback.from_user.id)
    if data is None:
        await callback.answer(NOT_REGISTERED, show_alert=True)
        return
    await callback.message.answer(
        invite_text(data),
        reply_markup=invite_keyboard(data["link"] or data["code"]),
    )
    await callback.answer()


@router.callback_query(F.data == NEW_CODE)
async def on_new_code(callback: CallbackQuery) -> None:
    """Eski kod muddati o'tsa — yangisini shu yerda olish."""
    user = callback.from_user
    code, ttl = await issue_code(user.id, user.username or "", user.first_name or "")

    if code is None:
        await callback.answer(TOO_FAST, show_alert=True)
        return

    await callback.message.edit_text(code_text(code, ttl), reply_markup=keyboard())
    await callback.answer("Yangi kod tayyor")


@router.message(F.text)
async def any_message(message: Message) -> None:
    """Har qanday xabarga ham kod beriladi — bot boshqa ish qilmaydi."""
    await give_code(message)
