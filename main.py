"""listening.uz Telegram bot.

Ishga tushirish:
    cd bot
    python main.py

Bot ikki ish qiladi:
  1. Foydalanuvchiga 1 daqiqalik kirish kodini beradi (sayt shu kod
     orqali JWT beradi).
  2. Backend `BotMessage` jadvaliga yozgan bildirishnomalarni yuboradi.
"""
import asyncio
import logging
import sys

from settings import BOT_TOKEN, setup_django

# Django ORM handlerlar import qilinishidan OLDIN sozlanishi kerak.
setup_django()

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402

from handlers.common import router  # noqa: E402
from services import mark_message, take_pending_messages  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("listening.bot")


async def notification_worker(bot: Bot) -> None:
    """Navbatdagi bildirishnomalarni yuboradi (har 10 soniyada tekshiradi)."""
    while True:
        try:
            for message in await take_pending_messages():
                try:
                    await bot.send_message(message["telegram_id"], message["text"])
                    await mark_message(message["id"], ok=True)
                except Exception as exc:  # bloklangan foydalanuvchi va h.k.
                    logger.warning("Xabar yuborilmadi (%s): %s", message["telegram_id"], exc)
                    await mark_message(message["id"], ok=False, error=str(exc))
                await asyncio.sleep(0.05)  # Telegram rate limit
        except Exception:
            logger.exception("Bildirishnoma workerida xatolik")
        await asyncio.sleep(10)


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN topilmadi. bot/.env faylini to'ldiring.")
        sys.exit(1)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    me = await bot.get_me()
    logger.info("Bot ishga tushdi: @%s", me.username)

    worker = asyncio.create_task(notification_worker(bot))
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        worker.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")
