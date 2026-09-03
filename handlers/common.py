"""Bot ikki ish qiladi: saytga kirish kodi beradi va TAKLIFni hisobga oladi.

`/start` bosilishi bilan kod yuboriladi.

**Taklif havolasi:** `t.me/<bot>?start=<INVITE_CODE>`. Telegram payload'ni
`/start` argumenti sifatida beradi; biz uni `PendingInvite` ga yozamiz va
o'sha odam saytga/ilovaga kirib ro'yxatdan o'tgach taklif hisobga olinadi
(`backend/apps/accounts/invites.py`). Shu bois taklif havolasi SAYTGA emas,
aynan BOTGA olib boradi — aks holda kim taklif qilgani yo'qolardi.

`/taklif` (yoki `/invite`) buyrug'i o'z havolangiz va hisobingizni ko'rsatadi.
"""
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from settings import SITE_URL
from services import invite_summary, issue_code, remember_invite

logger = logging.getLogger(__name__)
router = Router()

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
    await give_code(message)


@router.message(CommandStart())
@router.message(Command("kod"))
async def cmd_start(message: Message) -> None:
    """/start bosilishi bilanoq kod beriladi."""
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
