"""
Brown V2 | telegraph_snos.py
Метод: снос Telegraph статей через email-relay
- Парсит содержимое статьи
- Groq генерирует тему и текст (EN, макс 500 символов)
- Отправляет 12 писем через relay (4 почты × 3 адреса)
- spin_text/spin_subject для уникальности каждого письма
"""

import asyncio
import logging
import os
import re

import aiohttp

import config
from utils import now_msk
from mail_snos import spin_text, spin_subject, RELAY_URL, RELAY_TOKEN

logger = logging.getLogger(__name__)

GROQ_KEY = os.environ.get("GROQ_KEY", config.GROQ_KEY)

# ─── Отправители ──────────────────────────────────────────────────────────────
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

bot = None


def set_bot_telegraph(b):
    global bot
    bot = b


# ─── Парсинг статьи ───────────────────────────────────────────────────────────
async def fetch_telegraph_text(url: str) -> tuple[str, int]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"User-Agent": "Mozilla/5.0"}
            ) as resp:
                status = resp.status
                if status != 200:
                    return "", status
                html = await resp.text(errors="ignore")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:2000], 200
    except Exception as e:
        logger.error(f"[TELEGRAPH] fetch error: {e}")
        return "", 0


# ─── Groq генерация ───────────────────────────────────────────────────────────
async def generate_telegraph_text(article_url: str, article_text: str) -> tuple[str, str]:
    fallback_subject = f"ToS Violation Report"
    fallback_body = (
        f"Dear Telegram Support,\n\n"
        f"I am reporting a Telegraph article that violates Telegram's Terms of Service "
        f"(telegram.org/tos). The article contains prohibited content.\n\n"
        f"Article: {article_url}\n\n"
        f"Please review and take appropriate action.\n\nThank you."
    )

    prompt = (
        f"Write a short formal complaint email to Telegram support about a Telegraph article.\n"
        f"Article URL: {article_url}\n"
        f"Article content: {article_text[:600]}\n\n"
        f"Rules:\n"
        f"- English only\n"
        f"- Max 400 characters for the body\n"
        f"- Mention the article violates telegram.org/tos\n"
        f"- Include the article URL\n"
        f"- No legal references\n"
        f"- Be direct and formal\n\n"
        f"First line = email subject (max 60 chars)\n"
        f"Rest = email body\n"
        f"No labels, no formatting, just the text."
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
                    return fallback_subject, fallback_body

                content = data["choices"][0]["message"]["content"].strip()
                print(f"[TELEGRAPH] Groq raw: {content[:200]}", flush=True)

                lines = content.strip().split("\n")
                subject = lines[0].strip()[:100] if lines else fallback_subject
                body = "\n".join(lines[1:]).strip()[:600] if len(lines) > 1 else fallback_body

                if not subject:
                    subject = fallback_subject
                if not body:
                    body = fallback_body

                return subject, body

    except Exception as e:
        logger.error(f"[TELEGRAPH] Groq error: {e}")
        return fallback_subject, fallback_body


# ─── Отправка одного письма через relay ───────────────────────────────────────
async def _send_via_relay(session: aiohttp.ClientSession,
                          sender_email: str, sender_pass: str,
                          recipient: str, subject: str, body: str) -> bool:
    try:
        payload = {
            "token": RELAY_TOKEN,
            "from_email": sender_email,
            "from_pass": sender_pass,
            "to": recipient,
            "subject": subject,
            "body": body,
        }
        async with session.post(
            RELAY_URL,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            result = await resp.json(content_type=None)
            ok = result.get("ok") or result.get("status") == "ok" or resp.status == 200
            if not ok:
                logger.error(f"[TELEGRAPH] relay {sender_email}→{recipient}: {result}")
            return ok
    except Exception as e:
        logger.error(f"[TELEGRAPH] relay {sender_email}→{recipient}: {e}")
        return False


# ─── Главная функция ──────────────────────────────────────────────────────────
async def main_telegraph_snos(
    article_url: str,
    user_id: int,
    username: str,
    custom_text: str = "",
    custom_subject: str = "",
) -> dict:
    from config import bot_logs
    import keyboards
    from aiogram import types as aiogram_types

    print(f"\n[TELEGRAPH] 🚀 Старт | {article_url} | {user_id} (@{username})", flush=True)

    if custom_text and custom_subject:
        subject = custom_subject
        body = custom_text
        print(f"[TELEGRAPH] Используем пользовательский текст", flush=True)
    else:
        article_text, status = await fetch_telegraph_text(article_url)
        if status == 404:
            return {"ok": 0, "fail": 0, "error": "404"}
        print(f"[TELEGRAPH] Генерирую текст через Groq...", flush=True)
        subject, body = await generate_telegraph_text(article_url, article_text)

    print(f"[TELEGRAPH] Тема: {subject}", flush=True)
    print(f"[TELEGRAPH] Текст: {body[:80]}...", flush=True)

    ok = 0
    fail = 0
    total = len(SENDERS) * len(RECIPIENTS)

    # Все письма параллельно — каждое со своим спином
    async def send_one(sender_email, sender_pass, recipient):
        spun_subj = spin_subject(subject)
        spun_body = spin_text(body)
        async with aiohttp.ClientSession() as session:
            result = await _send_via_relay(session, sender_email, sender_pass, recipient, spun_subj, spun_body)
        return result, recipient

    tasks = [
        send_one(email, pwd, recipient)
        for email, pwd in SENDERS
        for recipient in RECIPIENTS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for result, recipient in results:
        if result:
            ok += 1
            print(f"[TELEGRAPH] ✅ → {recipient}", flush=True)
        else:
            fail += 1
            print(f"[TELEGRAPH] ❌ → {recipient}", flush=True)

    print(f"[TELEGRAPH] Итого: ✅ {ok} / ❌ {fail}", flush=True)

    # Добавляем в мониторинг
    if ok > 0:
        try:
            from monitor_snos import telegraph_monitor_add
            telegraph_monitor_add(article_url, user_id)
        except Exception as e:
            print(f"[TELEGRAPH] Ошибка мониторинга: {e}", flush=True)

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
