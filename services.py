"""Bot va baza o'rtasidagi qatlam.

Barcha ORM chaqiruvlari `sync_to_async` orqali o'raladi — aiogram
asinxron, Django ORM esa sinxron.
"""
import secrets
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.utils import timezone

from settings import OTP_LENGTH, OTP_RATE_LIMIT, OTP_TTL_SECONDS


# Bu kod(lar) hech qachon generatsiya qilinmaydi — doimiy TEST akkaunt uchun
# band (backend `settings.TEST_OTP_CODE`). Aks holda tasodifan tushib qolsa
# oddiy foydalanuvchi test akkauntga kirib qolardi.
RESERVED_CODES = {"789878", "789888", "789898"}


def _generate_code() -> str:
    """Boshida nol bo'lishi mumkin bo'lgan 6 xonali kod (band kodlardan tashqari)."""
    while True:
        code = "".join(str(secrets.randbelow(10)) for _ in range(OTP_LENGTH))
        if code not in RESERVED_CODES:
            return code


@sync_to_async
def issue_code(telegram_id: int, username: str = "", first_name: str = "") -> tuple[str | None, int]:
    """Yangi kirish kodini yaratadi.

    Qaytaradi: (kod, amal qilish soniyasi). Limit oshsa (None, 0).
    """
    from apps.accounts.models import TelegramOTP

    now = timezone.now()
    # Kerak bo'lmay qolgan kodlarni tozalaymiz. Kod atigi 1 daqiqa yashaydi,
    # muddati o'tgani yoki ishlatilgani jadvalda turishining foydasi yo'q
    # (alohida cron kerak emas -- har yangi kod berilganda tozalanadi).
    TelegramOTP.purge_expired()

    recent = TelegramOTP.objects.filter(
        telegram_id=telegram_id, created_at__gte=now - timedelta(minutes=1)
    ).count()
    if recent >= OTP_RATE_LIMIT:
        return None, 0

    # Eski ishlatilmagan kodlarni bekor qilamiz — bir vaqtda bitta kod amal qiladi.
    TelegramOTP.objects.filter(telegram_id=telegram_id, is_used=False).update(is_used=True)

    otp = TelegramOTP.objects.create(
        telegram_id=telegram_id,
        telegram_username=username or "",
        first_name=first_name or "",
        code=_generate_code(),
        expires_at=now + timedelta(seconds=OTP_TTL_SECONDS),
    )
    return otp.code, OTP_TTL_SECONDS


@sync_to_async
def take_pending_messages(limit: int = 30) -> list[dict]:
    """Navbatdagi bildirishnomalarni oladi va 'yuborilmoqda' deb belgilaydi."""
    from apps.telegrambot.models import BotMessage

    messages = list(
        BotMessage.objects.filter(status=BotMessage.Status.PENDING).order_by("created_at")[:limit]
    )
    return [{"id": m.id, "telegram_id": m.telegram_id, "text": m.text} for m in messages]


@sync_to_async
def mark_message(message_id: int, ok: bool, error: str = "") -> None:
    from apps.telegrambot.models import BotMessage

    BotMessage.objects.filter(pk=message_id).update(
        status=BotMessage.Status.SENT if ok else BotMessage.Status.FAILED,
        error=error[:500],
        sent_at=timezone.now() if ok else None,
    )


@sync_to_async
def remember_invite(telegram_id: int, payload: str) -> bool:
    """`/start <kod>` -- taklif havolasini eslab qoladi.

    Bu paytda `User` hali YO'Q (u faqat kod tekshirilgach yaratiladi), shu
    bois bog'lanish `PendingInvite` da telegram_id ustida saqlanadi va
    ro'yxatdan o'tish payti hisobga olinadi
    (`apps/accounts/invites.py`).
    """
    from apps.accounts.invites import remember_pending_invite

    try:
        return remember_pending_invite(telegram_id, payload)
    except Exception:
        return False


@sync_to_async
def invite_summary(telegram_id: int) -> dict | None:
    """Botdagi "Taklif" bo'limi uchun: havola + jami + keyingi sovg'agacha."""
    from django.conf import settings

    from apps.accounts.models import User
    from apps.billing.rewards import reward_progress

    user = User.objects.filter(telegram_id=telegram_id).first()
    if user is None:
        return None
    bot = (getattr(settings, "TELEGRAM_BOT_USERNAME", "") or "").lstrip("@")
    data = reward_progress(user)
    data["link"] = f"https://t.me/{bot}?start={user.invite_code}" if bot else ""
    data["code"] = user.invite_code
    return data
