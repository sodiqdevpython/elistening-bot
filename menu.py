"""Botning doimiy menyusi (pastdagi klaviatura) va umumiy tugma yordamchilari.

Menyu har foydalanuvchiga ALOHIDA yasaladi: oxirgi tugmada uning **To'lov
ID** si turadi (`🆔 ID: 931716835`) va kiritish maydonida ham ko'rinadi.
Foydalanuvchi talabi: "profile id doim ko'rinib tursin — Paynet'ga pul
tashlashda shu ID ni kiritadi". ID — Telegram chat id (`User.telegram_id`),
saytdagi hamyon pill'idagi ID ham shu.

Telegram reply-klaviaturasi bir marta yuborilsa, keyingi xabarlarda ham
turaveradi — shu bois uni `/start` da yuborish yetarli.
"""
from aiogram.types import (
    BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
)

from settings import SITE_URL

BTN_CODE = "🔑 Kirish kodi"
BTN_PROFILE = "👤 Profil"
BTN_DEVICES = "📱 Qurilmalar"
BTN_BALANCE = "💰 Balans"
BTN_INVITE = "🎁 Taklif"
#: ID tugmasi matni o'zgaruvchan (`🆔 ID: <raqam>`) — prefiks bo'yicha taniladi.
BTN_ID_PREFIX = "🆔"

#: "/" menyusi — `main.py` ishga tushganda Telegram'ga yozadi.
COMMANDS = [
    BotCommand(command="start", description="Saytga kirish kodi"),
    BotCommand(command="profil", description="Profil, tarif va To'lov ID"),
    BotCommand(command="qurilmalar", description="Ulangan qurilmalar — chiqarib yuborish"),
    BotCommand(command="balans", description="Balans va tariflar"),
    BotCommand(command="tolov", description="To'lov ID (Paynet)"),
    BotCommand(command="taklif", description="Do'stlarni taklif qilish"),
]


def is_public_url(url: str) -> bool:
    """Telegram inline tugmasi faqat public HTTPS qabul qiladi (localhost — yo'q)."""
    return url.startswith("https://") and "localhost" not in url and "127.0.0.1" not in url


def main_menu(telegram_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CODE), KeyboardButton(text=BTN_PROFILE)],
            [KeyboardButton(text=BTN_DEVICES), KeyboardButton(text=BTN_BALANCE)],
            [KeyboardButton(text=BTN_INVITE), KeyboardButton(text=f"{BTN_ID_PREFIX} ID: {telegram_id}")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=f"To'lov ID: {telegram_id}",
    )


def inline(rows: list[list[dict]], site_path: str | None = None) -> InlineKeyboardMarkup | None:
    """Backend bergan `[[{"text", "data"}]]` → aiogram klaviaturasi (+ sayt havolasi)."""
    keyboard = [
        [InlineKeyboardButton(text=b["text"], callback_data=b["data"]) for b in row]
        for row in rows
    ]
    if site_path is not None and is_public_url(SITE_URL):
        keyboard.append([InlineKeyboardButton(text="🌐 Saytda ochish", url=f"{SITE_URL}{site_path}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
