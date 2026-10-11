"""Tariflar RASMI — "pul tushdi" xabarining surati.

Saytdagi "Tarifni tanlang" kartochkalarini (`frontend/src/features/billing/
PlanCards.tsx`) takrorlaydi, lekin SHU foydalanuvchining holati bilan:
joriy tarif "JORIY", pastroq tarif xira, ko'tarilishda farq narxi, tepada
balans. Ma'lumot `apps/billing/offer.py::build_offer` dan keladi — rasm,
xabar matni va tugmalar bir xil raqamlarni ko'rsatadi.

Sof funksiya: `render(offer) -> PNG bayt`. Tarmoq ham, baza ham yo'q.
Pillow sinxron — bot uni `asyncio.to_thread` da chaqiradi.

**Shrift.** Saytdagi Inter bo'lsa o'sha, bo'lmasa DejaVu (Docker'da
`fonts-dejavu-core`), lokal Windows'da Segoe UI. Hech biri topilmasa
Pillow'ning ichki shrifti — rasm baribir chiqadi.
"""
from __future__ import annotations

import glob
import io
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

#: Telegram suratni uzun tomoni 1280 px gacha siqadi — aynan shu o'lcham.
WIDTH = 1280
#: Ikki baravar katta chizib kichraytiramiz — yumaloq burchaklar silliq chiqadi.
SS = 2

INK = (15, 23, 42)
MUTED = (100, 116, 139)
BORDER = (226, 232, 240)
GREEN = (16, 185, 129)
GREEN_DARK = (5, 150, 105)
BLUE = (37, 99, 235)
PURPLE = (124, 58, 237)
PANEL = (248, 250, 252)
OUTER = (238, 242, 247)

TEXT = {
    "uz": {
        "title": "Tarifni tanlang",
        "desc": "Ehtiyojingizga mos rejani tanlang, istalgan vaqtda o‘zgartirishingiz mumkin.",
        "current": "JORIY", "popular": "OMMABOP", "current_btn": "Joriy reja",
        "select": "Tanlash", "picked": "Tanlangan", "lower": "Sizda yuqoriroq tarif faol",
        "free": "Bepul", "per": "/ oy", "upgrade": "Ko‘tarilish: {amount}",
        "balance": "Balans: {amount}",
        "footer": "Tarifni xabar ostidagi tugmalar bilan tanlang",
    },
    "en": {
        "title": "Choose your plan",
        "desc": "Pick the plan that fits your needs, change anytime.",
        "current": "CURRENT", "popular": "POPULAR", "current_btn": "Current plan",
        "select": "Select", "picked": "Selected", "lower": "You have a higher plan active",
        "free": "Free", "per": "/ mo", "upgrade": "Upgrade: {amount}",
        "balance": "Balance: {amount}",
        "footer": "Choose a plan with the buttons under this message",
    },
}


def money(uzs: int, lang: str) -> str:
    value = f"{int(uzs):,}"
    return f"{value} UZS" if lang == "en" else value.replace(",", " ") + " so‘m"


# ── Shriftlar ─────────────────────────────────────────────────────────────
_WEIGHTS = {
    # vazn: (Inter fayl nomi bo'laklari, DejaVu, Windows)
    "regular": (("Regular",), "DejaVuSans.ttf", ("segoeui.ttf", "arial.ttf")),
    "semibold": (("SemiBold", "Semibold"), "DejaVuSans-Bold.ttf", ("seguisb.ttf", "arialbd.ttf")),
    "bold": (("Bold",), "DejaVuSans-Bold.ttf", ("segoeuib.ttf", "arialbd.ttf")),
    "black": (("ExtraBold", "Black"), "DejaVuSans-Bold.ttf", ("seguibl.ttf", "segoeuib.ttf", "arialbd.ttf")),
}


@lru_cache(maxsize=None)
def _font_path(weight: str) -> str | None:
    inter_parts, dejavu, windows = _WEIGHTS[weight]
    roots = [os.environ.get("PLAN_IMAGE_FONT_DIR", ""), "/usr/share/fonts", "/usr/local/share/fonts"]
    for root in filter(None, roots):
        for part in inter_parts:
            for pattern in (f"Inter-{part}.ttf", f"Inter-{part}.otf", f"Inter{part}.ttf"):
                hits = glob.glob(os.path.join(root, "**", pattern), recursive=True)
                if hits:
                    return hits[0]
    for root in filter(None, roots):
        hits = glob.glob(os.path.join(root, "**", dejavu), recursive=True)
        if hits:
            return hits[0]
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in windows:
        path = os.path.join(win, name)
        if os.path.exists(path):
            return path
    return None


@lru_cache(maxsize=None)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    path = _font_path(weight)
    px = int(size * SS)
    if path:
        return ImageFont.truetype(path, px)
    return ImageFont.load_default(size=px)


# ── Chizish yordamchilari (koordinatalar 1280 px dizayn birligida) ────────
class Canvas:
    def __init__(self, height: int):
        self.image = Image.new("RGB", (WIDTH * SS, height * SS), OUTER)
        self.draw = ImageDraw.Draw(self.image)

    @staticmethod
    def s(v: float) -> int:
        return int(round(v * SS))

    def box(self, x, y, w, h, radius, fill=None, outline=None, width=1):
        self.draw.rounded_rectangle(
            (self.s(x), self.s(y), self.s(x + w), self.s(y + h)), radius=self.s(radius),
            fill=fill, outline=outline, width=self.s(width) if outline else 0,
        )

    def text(self, x, y, value, weight, size, fill=INK, anchor="la"):
        self.draw.text((self.s(x), self.s(y)), value, font=font(weight, size), fill=fill, anchor=anchor)

    def width_of(self, value, weight, size) -> float:
        return self.draw.textlength(value, font=font(weight, size)) / SS

    def gradient_box(self, x, y, w, h, radius, left, right):
        """Chapdan o'ngga gradient to'ldirilgan yumaloq to'rtburchak."""
        W, H = self.s(w), self.s(h)
        grad = _gradient(W, H, left, right)
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=self.s(radius), fill=255)
        self.image.paste(grad, (self.s(x), self.s(y)), mask)

    def gradient_text(self, x, y, value, weight, size, left, right):
        """Saytdagi tarif nomi kabi — ko'kdan binafshaga o'tuvchi matn."""
        f = font(weight, size)
        x0, y0, x1, y1 = self.draw.textbbox((0, 0), value, font=f)
        W, H = max(1, x1), max(1, y1)
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).text((0, 0), value, font=f, fill=255)
        self.image.paste(_gradient(W, H, left, right), (self.s(x), self.s(y)), mask)

    def check(self, x, y, size, color=GREEN):
        """✓ belgisi chiziq bilan — shriftda glif bo'lmasa ham chiqadi."""
        pts = [(x, y + size * 0.55), (x + size * 0.38, y + size * 0.9), (x + size, y + size * 0.15)]
        self.draw.line([(self.s(a), self.s(b)) for a, b in pts], fill=color, width=self.s(2.6), joint="curve")

    def dashed_box(self, x, y, w, h, color, dash=8, gap=6):
        for x0, y0, x1, y1 in ((x, y, x + w, y), (x, y + h, x + w, y + h)):
            pos = x0
            while pos < x1:
                self.draw.line((self.s(pos), self.s(y0), self.s(min(pos + dash, x1)), self.s(y1)),
                               fill=color, width=self.s(1.5))
                pos += dash + gap
        for x0 in (x, x + w):
            pos = y
            while pos < y + h:
                self.draw.line((self.s(x0), self.s(pos), self.s(x0), self.s(min(pos + dash, y + h))),
                               fill=color, width=self.s(1.5))
                pos += dash + gap

    def fade(self, x, y, w, h, alpha=0.45):
        """Pastroq (tanlab bo'lmaydigan) tarif — saytdagi `opacity: .55`."""
        region = (self.s(x), self.s(y), self.s(x + w), self.s(y + h))
        crop = self.image.crop(region)
        white = Image.new("RGB", crop.size, PANEL)
        self.image.paste(Image.blend(crop, white, alpha), region[:2])

    def png(self) -> bytes:
        out = self.image.resize((self.image.width // SS, self.image.height // SS), Image.LANCZOS)
        buf = io.BytesIO()
        out.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def _gradient(w: int, h: int, left, right) -> Image.Image:
    row = Image.new("RGB", (w, 1))
    px = row.load()
    for i in range(w):
        t = i / max(1, w - 1)
        px[i, 0] = tuple(int(a + (b - a) * t) for a, b in zip(left, right))
    return row.resize((w, h))


# ── Kartochka ─────────────────────────────────────────────────────────────
M, P, GAP, PAD = 28, 34, 22, 26
CARD_W = (WIDTH - 2 * M - 2 * P - 2 * GAP) / 3
FEATURE_STEP = 34
BUTTON_H = 54


def _card_body_height(card: dict) -> float:
    upgrade = 26 if card["upgrade"] else 0
    return PAD + 30 + 28 + 48 + upgrade + 18 + FEATURE_STEP * len(card["features"]) + 22 + BUTTON_H + PAD


def _draw_card(c: Canvas, card: dict, x: float, y: float, h: float, lang: str) -> None:
    T = TEXT[lang]
    if card["current"]:
        outline, width = GREEN, 3
    elif card["pending"]:
        outline, width = GREEN_DARK, 3
    elif card["highlight"]:
        outline, width = BLUE, 2
    else:
        outline, width = BORDER, 2
    c.box(x, y, CARD_W, h, 18, fill=(255, 255, 255), outline=outline, width=width)

    cx, cy = x + PAD, y + PAD
    c.gradient_text(cx, cy, card["name"], "black", 22, BLUE, PURPLE)
    if card["current"]:
        label = T["current"]
        bw = c.width_of(label, "bold", 13) + 22
        c.gradient_box(x + CARD_W - PAD - bw, cy + 2, bw, 26, 8, GREEN, GREEN_DARK)
        c.text(x + CARD_W - PAD - bw / 2, cy + 15, label, "bold", 13, (255, 255, 255), anchor="mm")
    cy += 32
    c.text(cx, cy, card["tagline"], "semibold", 16, MUTED)
    cy += 30

    if card["price_uzs"]:
        price = money(card["price_uzs"], lang)
        c.text(cx, cy + 34, price, "black", 32, INK, anchor="ls")
        c.text(cx + c.width_of(price, "black", 32) + 8, cy + 34, T["per"], "semibold", 17, MUTED, anchor="ls")
    else:
        c.text(cx, cy + 34, T["free"], "black", 32, INK, anchor="ls")
    cy += 48
    if card["upgrade"]:
        c.text(cx, cy, T["upgrade"].format(amount=money(card["pay_uzs"], lang)), "bold", 16, GREEN_DARK)
        cy += 26
    cy += 18

    for feature in card["features"]:
        c.check(cx, cy + 2, 16)
        c.text(cx + 28, cy, feature, "regular", 18, (30, 41, 59))
        cy += FEATURE_STEP

    bx, bw, by = x + PAD, CARD_W - 2 * PAD, y + h - PAD - BUTTON_H
    if card["current"]:
        c.box(bx, by, bw, BUTTON_H, 14, fill=(248, 250, 252), outline=BORDER, width=1.5)
        c.text(bx + bw / 2, by + BUTTON_H / 2, T["current_btn"], "bold", 17, (148, 163, 184), anchor="mm")
    elif card["lower"]:
        c.box(bx, by, bw, BUTTON_H, 14, fill=(241, 245, 249))
        c.dashed_box(bx, by, bw, BUTTON_H, (203, 213, 225))
        c.text(bx + bw / 2, by + BUTTON_H / 2, T["lower"], "bold", 15, MUTED, anchor="mm")
    elif card["buyable"]:
        c.gradient_box(bx, by, bw, BUTTON_H, 14, GREEN, GREEN_DARK)
        label = T["picked"] if card["pending"] else T["select"]
        c.text(bx + bw / 2, by + BUTTON_H / 2, label, "bold", 18, (255, 255, 255), anchor="mm")

    if card["lower"]:
        c.fade(x, y, CARD_W, h)

    # "OMMABOP" — kartochka chegarasi ustida (saytdagidek), xiralashtirishdan keyin.
    if card["highlight"] and not card["current"] and not card["lower"]:
        label = TEXT[lang]["popular"]
        bw = c.width_of(label, "bold", 13) + 24
        c.box(x + 20, y - 13, bw, 26, 13, fill=BLUE)
        c.text(x + 20 + bw / 2, y, label, "bold", 13, (255, 255, 255), anchor="mm")


def render(offer: dict) -> bytes:
    """`build_offer` natijasidan PNG yasaydi."""
    lang = offer.get("lang") if offer.get("lang") in TEXT else "uz"
    T = TEXT[lang]
    cards = offer["plans"]
    card_h = max((_card_body_height(card) for card in cards), default=200)

    header = 100
    footer = 54
    panel_h = P + header + card_h + footer
    height = int(2 * M + panel_h)
    c = Canvas(height)

    c.box(M, M, WIDTH - 2 * M, panel_h, 22, fill=PANEL, outline=BORDER, width=1.5)
    left = M + P
    c.text(left, M + P, T["title"], "black", 30, INK)
    c.text(left, M + P + 46, T["desc"], "regular", 18, MUTED)

    pill = T["balance"].format(amount=money(offer.get("balance_uzs", 0), lang))
    pw = c.width_of(pill, "bold", 18) + 36
    px = WIDTH - M - P - pw
    c.box(px, M + P, pw, 42, 21, fill=(236, 253, 245), outline=(167, 243, 208), width=1.5)
    c.text(px + pw / 2, M + P + 21, pill, "bold", 18, (4, 120, 87), anchor="mm")

    top = M + P + header
    for i, card in enumerate(cards):
        _draw_card(c, card, left + i * (CARD_W + GAP), top, card_h, lang)

    c.text(WIDTH / 2, top + card_h + footer / 2 + 4, T["footer"], "semibold", 16, MUTED, anchor="mm")
    return c.png()
