"""
Brown V2 | telegraph_snos.py
Метод: снос Telegraph/Teletype статей
- Парсит содержимое статьи
- Groq генерирует тему и текст письма (EN, макс 500 символов, без законов)
- 4 rambler-почты шлют на abuse/support/dmca@telegram.org
- Задержка 10-25 сек между отправками
"""

import asyncio
import random
import smtplib
import logging
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiohttp

import config
from utils import now_msk

logger = logging.getLogger(__name__)

GROQ_KEY = os.environ.get("GROQ_KEY", config.GROQ_KEY)

# ─── Почты-отправители ────────────────────────────────────────────────────────
SENDERS = [
    ("jfjtwncyeb@rambler.ru",  "7066987lMSG2Z"),
    ("ifzenleixs@rambler.ru",  "69679436xM9U4"),
    ("gozpezocmj@rambler.ru",  "8282635Gkvuvq"),
    ("asagkqfygx@rambler.ru",  "90629300zd5Xm"),
]

# ─── Получатели ───────────────────────────────────────────────────────────────
RECIPIENTS = [
    "abuse@telegram.org",
    "support@telegram.org",
    "dmca@telegram.org",
]

SMTP_HOST = "smtp.rambler.ru"
SMTP_PORT = 465
SMTP_TIMEOUT = 15

bot = None


def set_bot_telegraph(b):
    global bot
    bot = b


# ─── Парсинг статьи ───────────────────────────────────────────────────────────
async def fetch_telegraph_text(url: str) -> tuple[str, int]:
    """
    Скачивает текст статьи.
    Возвращает (текст, http_status).
    Если 404 — статья удалена.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"User-Agent": "Mozilla/5.0"}
            ) as resp:
                status = resp.status
                if status == 404:
                    return "", 404
                if status != 200:
                    return "", status
                html = await resp.text(errors="ignore")

        # Вытаскиваем текст из <article> или <p>
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:2000], 200
    except Exception as e:
        logger.error(f"[TELEGRAPH] fetch error: {e}")
        return "", 0


# ─── Groq генерация ───────────────────────────────────────────────────────────
async def generate_telegraph_text(article_url: str, article_text: str) -> tuple[str, str]:
    """
    Генерирует тему и текст письма через Groq.
    Возвращает (subject, body).
    """
    prompt = (
        f"You are writing a formal complaint email to Telegram support.\n"
        f"Article URL: {article_url}\n"
        f"Article content (excerpt): {article_text[:800]}\n\n"
        f"Generate:\n"
        f"1. A short email subject line (max 60 characters, English)\n"
        f"2. Email body (English only, max 500 characters total, "
        f"mention the article violates Telegram Terms of Service at telegram.org/tos, "
        f"include the article URL, be direct and formal, "
        f"no laws or legal references, no filler phrases)\n\n"
        f"Response format (exactly):\n"
        f"SUBJECT: <subject here>\n"
        f"BODY: <body here>"
    )

    fallback_subject = f"ToS Violation Report: {article_url}"
    fallback_body = (
        f"Dear Telegram Support,\n\n"
        f"I am reporting a Telegraph article that violates Telegram's Terms of Service "
        f"(telegram.org/tos). The article contains prohibited content.\n\n"
        f"Article: {article_url}\n\n"
        f"Please review and take appropriate action.\n\nThank you."
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                    "messages": [
                        {"role": "system", "content": "You generate formal complaint emails. Be concise and professional."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.7,
                },
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json(content_type=None)
                if "choices" not in data:
                    logger.error(f"[TELEGRAPH] Groq unexpected: {data}")
                    return fallback_subject, fallback_body

                content = data["choices"][0]["message"]["content"].strip()

                # Парсим SUBJECT и BODY
                subject = fallback_subject
                body = fallback_body

                subj_match = re.search(r"SUBJECT:\s*(.+?)(?:\n|$)", content)
                body_match = re.search(r"BODY:\s*(.+?)$", content, re.DOTALL)

                if subj_match:
                    subject = subj_match.group(1).strip()[:100]
                if body_match:
                    body = body_match.group(1).strip()[:600]

                return subject, body

    except Exception as e:
        logger.error(f"[TELEGRAPH] Groq error: {e}")
        return fallback_subject, fallback_body


# ─── SMTP отправка одного письма ──────────────────────────────────────────────
def _send_one(sender_email: str, sender_pass: str,
              recipient: str, subject: str, body: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT)
        server.login(sender_email, sender_pass)
        server.sendmail(sender_email, recipient, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"[TELEGRAPH] SMTP {sender_email} → {recipient}: {e}")
        return False


# ─── Главная функция ──────────────────────────────────────────────────────────
async def main_telegraph_snos(
    article_url: str,
    user_id: int,
    username: str,
    custom_text: str = "",       # если пользователь написал свой текст
    custom_subject: str = "",    # если пользователь написал свою тему
) -> dict:
    """
    Основная функция Telegraph-метода.
    Возвращает dict с результатами: ok, fail, subject, body
    """
    from config import bot_logs
    import keyboards
    from aiogram import types as aiogram_types

    print(f"\n[TELEGRAPH] 🚀 Старт | {article_url} | {user_id} (@{username})", flush=True)

    # Используем текст пользователя или Groq
    if custom_text and custom_subject:
        subject = custom_subject
        body = custom_text
        print(f"[TELEGRAPH] Используем пользовательский текст", flush=True)
    else:
        # Парсим статью
        article_text, status = await fetch_telegraph_text(article_url)
        if status == 404:
            print(f"[TELEGRAPH] 404 — статья удалена", flush=True)
            return {"ok": 0, "fail": 0, "error": "404"}

        # Groq генерация
        print(f"[TELEGRAPH] Генерирую текст через Groq...", flush=True)
        subject, body = await generate_telegraph_text(article_url, article_text)

    print(f"[TELEGRAPH] Тема: {subject}", flush=True)
    print(f"[TELEGRAPH] Текст: {body[:80]}...", flush=True)

    ok = 0
    fail = 0
    total = len(SENDERS) * len(RECIPIENTS)

    # Рассылка: каждый отправитель → все получатели, задержка между отправками
    for i, (sender_email, sender_pass) in enumerate(SENDERS):
        for recipient in RECIPIENTS:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _send_one, sender_email, sender_pass, recipient, subject, body
            )
            if result:
                ok += 1
                print(f"[TELEGRAPH] ✅ → {recipient}", flush=True)
            else:
                fail += 1
                print(f"[TELEGRAPH] ❌ → {recipient}", flush=True)

            # Задержка 10-25 сек между каждым письмом
            if ok + fail < total:
                delay = random.uniform(10, 25)
                print(f"[TELEGRAPH] ⏳ Жду {delay:.0f}с...", flush=True)
                await asyncio.sleep(delay)

    print(f"[TELEGRAPH] Итого: ✅ {ok} / ❌ {fail}", flush=True)

    # Добавляем статью в мониторинг если хоть одно письмо ушло
    if ok > 0:
        try:
            from monitor_snos import telegraph_monitor_add
            telegraph_monitor_add(article_url, user_id)
            print(f"[TELEGRAPH] Статья добавлена в мониторинг", flush=True)
        except Exception as e:
            print(f"[TELEGRAPH] Ошибка добавления в мониторинг: {e}", flush=True)

    # Формируем отчёт
    body_preview = body[:80] + "..." if len(body) > 80 else body

    caption = (
        f"📄 *Telegraph снос завершён!*\n"
        f"*└─* [Статья]({article_url})\n\n"
        f"📨 *Жалоб отправлено:* `{ok}/{total}`\n"
        f"✅ *Успешно:* `{ok}`\n"
        f"❌ *Ошибок:* `{fail}`\n\n"
        f"📝 *Текст:* `{body_preview}`"
    )

    caption_log = (
        f"📄 *Telegraph*\n"
        f"*└─* [Статья]({article_url})\n"
        f"✅ {ok} | ❌ {fail}\n"
        f"👤 {user_id} (@{username})"
    )

    try:
        await bot.send_message(
            user_id, caption,
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu,
            disable_web_page_preview=True
        )
        await bot.send_message(
            bot_logs, caption_log,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[TELEGRAPH] Ошибка отправки отчёта: {e}", flush=True)

    return {"ok": ok, "fail": fail, "subject": subject, "body": body}
