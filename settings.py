"""Bot sozlamalari.

Bot backend bilan bitta bazani baham ko'radi: kodni bazaga yozadi,
sayt esa uni tekshiradi. Shu sababli Django ORM to'g'ridan-to'g'ri
ishlatiladi (alohida HTTP API kerak emas).
"""
import os
import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent / "backend"

env = environ.Env(
    TELEGRAM_BOT_TOKEN=(str, ""),
    TELEGRAM_BOT_USERNAME=(str, "elistening_bot"),
    SITE_URL=(str, "http://192.168.1.178:5173"),
    DJANGO_SETTINGS_MODULE=(str, "config.settings.bot"),
)
environ.Env.read_env(BASE_DIR / ".env")

BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = env("TELEGRAM_BOT_USERNAME")
SITE_URL = env("SITE_URL").rstrip("/")

OTP_TTL_SECONDS = 60
OTP_LENGTH = 6
# Bir foydalanuvchi daqiqasiga nechta kod so'ray oladi.
OTP_RATE_LIMIT = 3


def setup_django():
    """Django ORM ni bot jarayonida ishga tushiradi."""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", env("DJANGO_SETTINGS_MODULE"))
    import django

    django.setup()
