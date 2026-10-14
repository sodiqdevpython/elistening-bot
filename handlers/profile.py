"""👤 Profil va 📱 Qurilmalar — menyu tugmalari, buyruqlar va inline tugmalar.

Matn va qarorlar backendda (`apps/accounts/bot_profile.py`); bu yerda faqat
yuborish va xabarni joyida yangilash.

    👤 Profil / /profil        → profil: To'lov ID, tarif, balans, statistika
    📱 Qurilmalar / /qurilmalar → ro'yxat + har biriga "🚪 Chiqarish" tugmasi
    pf / sl                     → profil / ro'yxatga qaytish (xabar joyida)
    sx:<id> / sx:all            → chiqarish; ro'yxat joyida yangilanadi

Bu router `common` dan OLDIN ulanadi — u yerdagi "har qanday matn → kod"
handleri menyu tugmalarining matnini yutib yuborardi.
"""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from menu import BTN_DEVICES, BTN_PROFILE, inline, main_menu
from services import profile_view, revoke_session, sessions_view

logger = logging.getLogger(__name__)
router = Router()

NOT_REGISTERED = (
    "Avval saytga yoki ilovaga kirib ro'yxatdan o'ting — shundan keyin profilingiz "
    "shu yerda ko'rinadi. Kirish kodi uchun: 🔑 Kirish kodi."
)


async def _edit(callback: CallbackQuery, view: dict, site_path: str | None = None) -> None:
    """Tugma bosilgan xabarni joyida o'zgartiradi (rasmli bo'lsa — yangisini yuboradi)."""
    markup = inline(view["buttons"], site_path)
    message = callback.message
    try:
        if isinstance(message, Message) and not message.photo:
            await message.edit_text(view["text"], reply_markup=markup)
        else:
            await callback.bot.send_message(callback.from_user.id, view["text"], reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


@router.message(Command("profil"))
@router.message(Command("profile"))
@router.message(F.text == BTN_PROFILE)
async def cmd_profile(message: Message) -> None:
    view = await profile_view(message.from_user.id)
    if view is None:
        await message.answer(NOT_REGISTERED, reply_markup=main_menu(message.from_user.id))
        return
    await message.answer(view["text"], reply_markup=inline(view["buttons"], "/profile"))


@router.message(Command("qurilmalar"))
@router.message(Command("devices"))
@router.message(F.text == BTN_DEVICES)
async def cmd_devices(message: Message) -> None:
    view = await sessions_view(message.from_user.id)
    if view is None:
        await message.answer(NOT_REGISTERED, reply_markup=main_menu(message.from_user.id))
        return
    await message.answer(view["text"], reply_markup=inline(view["buttons"]))


@router.callback_query(F.data == "pf")
async def on_profile(callback: CallbackQuery) -> None:
    view = await profile_view(callback.from_user.id)
    if view is None:
        await callback.answer(NOT_REGISTERED, show_alert=True)
        return
    await _edit(callback, view, "/profile")
    await callback.answer()


@router.callback_query(F.data == "sl")
async def on_sessions(callback: CallbackQuery) -> None:
    view = await sessions_view(callback.from_user.id)
    if view is None:
        await callback.answer(NOT_REGISTERED, show_alert=True)
        return
    await _edit(callback, view)
    await callback.answer()


@router.callback_query(F.data.startswith("sx:"))
async def on_revoke(callback: CallbackQuery) -> None:
    result = await revoke_session(callback.from_user.id, callback.data[3:])
    if result is None:
        await callback.answer(NOT_REGISTERED, show_alert=True)
        return
    await _edit(callback, result)
    await callback.answer(result["toast"] or None)
