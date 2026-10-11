FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.bot

WORKDIR /app

# fonts-dejavu-core — "pul tushdi" xabaridagi tariflar rasmi uchun shrift
# (`plan_image.py`). Usiz rasm Pillow'ning ichki shriftida chiqadi.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bot backend modellaridan foydalanadi — ikkalasi ham nusxalanadi.
COPY backend/ /backend/
COPY bot/ /app/

CMD ["python", "main.py"]
