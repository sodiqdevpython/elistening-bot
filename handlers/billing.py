"""Hisob va tariflar: "pul tushdi" xabaridagi tugmalar + `/balans`.

Oqim (hamma qaror backendda — `apps/billing/offer.py`):

    pul tushdi → rasm + balans + [O‘rta · 23 000 so‘m] [Yuqori · 32 000 so‘m]
    tugma (pl:<kod>)   → shu xabarning o'zi tasdiqlash ekraniga aylanadi
    ✅ (pk:<kod>:<b>)  → wallet.choose_plan: pul yetsa yoqiladi, yetmasa niyat
    ↩️ (pb)            → yana tariflar ro'yxati

Pul faqat "Tasdiqlash"da yechiladi. Tugma ikki marta bosilsa ikkinchisi
`StaleBalance` ga uchraydi (callback'dagi balans endi mos emas) — tarif ikki
marta sotib olinmaydi.
"""
import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

from plan_image import render
from services import apply_choice, offer_view, plan_prompt
from settings import SITE_URL

logger = logging.getLogger(__name__)
router = Router()

NOT_REGISTERED = (
    "Avval saytga yoki ilovaga kirib ro'yxatdan o'ting — "
    "shundan keyin hisobingiz shu yerda ko'rinadi."
)


def _is_public_url(url: str) -> bool:
    # `handlers/common.py` dagi bilan bir xil: Telegram faqat public HTTPS qabul qiladi.
    return url.startswith("https://") and "localhost" not in url and "127.0.0.1" not in url


def markup(rows: list[list[dict]], site: bool = False) -> InlineKeyboardMarkup | None:
    """Backend bergan `[[{"text", "data"}]]` → aiogram klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton(text=b["text"], callback_data=b["data"]) for b in row]
        for row in rows
    ]
    if site and _is_public_url(SITE_URL):
        keyboard.append([InlineKeyboardButton(text="🌐 Saytda ochish", url=f"{SITE_URL}/profile/billing")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None


async def send_offer(bot, chat_id: int, caption: str, rows: list[list[dict]], offer: dict | None) -> None:
    """Tariflar rasmi + matn + tugmalar. Rasm chizilmasa — faqat matn."""
    keyboard = markup(rows, site=True)
    png = None
    if offer is not None:
        try:
            png = await asyncio.to_thread(render, offer)
        except Exception:  # shrift/Pillow muammosi xabarni to'xtatmasin
            logger.exception("Tariflar rasmini chizib bo'lmadi")
    if png:
        await bot.send_photo(chat_id, BufferedInputFile(png, "tariflar.png"),
                             caption=caption, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, caption, reply_markup=keyboard)


async def _edit(callback: CallbackQuery, text: str, rows: list[list[dict]], site: bool = False) -> None:
    """Tugma bosilgan xabarni joyida o'zgartiradi (rasmli bo'lsa — izohini)."""
    keyboard = markup(rows, site=site)
    message = callback.message
    try:
        if isinstance(message, Message) and message.photo:
            await message.edit_caption(caption=text, reply_markup=keyboard)
        elif isinstance(message, Message):
            await message.edit_text(text, reply_markup=keyboard)
        else:  # juda eski xabar — tahrirlab bo'lmaydi, yangisini yuboramiz
            await callback.bot.send_message(callback.from_user.id, text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


@router.message(Command("balans"))
@router.message(Command("tarif"))
async def cmd_balance(message: Message) -> None:
    """Hisob va tariflar — istalgan paytda (pul tushmasa ham)."""
    view = await offer_view(message.from_user.id)
    if view is None:
        await message.answer(NOT_REGISTERED)
        return
    await send_offer(message.bot, message.chat.id, view["text"], view["buttons"], view["offer"])


@router.callback_query(F.data.startswith("pl:"))
async def on_plan(callback: CallbackQuery) -> None:
    result = await plan_prompt(callback.from_user.id, callback.data[3:])
    if result is None:
        await callback.answer(NOT_REGISTERED, show_alert=True)
        return
    if "alert" in result:
        await callback.answer(result["alert"], show_alert=True)
        return
    await _edit(callback, result["text"], result["buttons"])
    await callback.answer()


@router.callback_query(F.data.startswith("pk:"))
async def on_confirm(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].lstrip("-").isdigit():
        await callback.answer()
        return
    result = await apply_choice(callback.from_user.id, parts[1], int(parts[2]))
    if result is None:
        await callback.answer(NOT_REGISTERED, show_alert=True)
        return
    if "text" in result:
        # Eskirgan tugma bo'lsa backend tariflar ro'yxatini qaytaradi (sayt tugmasi bilan).
        await _edit(callback, result["text"], result["buttons"], site="offer" in result)
    alert = result.get("alert")
    await callback.answer(alert or result.get("toast"), show_alert=bool(alert))


@router.callback_query(F.data == "pb")
async def on_back(callback: CallbackQuery) -> None:
    view = await offer_view(callback.from_user.id)
    if view is None:
        await callback.answer(NOT_REGISTERED, show_alert=True)
        return
    await _edit(callback, view["text"], view["buttons"], site=True)
    await callback.answer()
