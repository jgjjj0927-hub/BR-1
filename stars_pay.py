"""
Brown V2 | stars_pay.py
Оплата Telegram Stars через @Hemoroyybot.
Сессия: aureport_sessions/+61435551379.session
Схема: Stars → @Hemoroyybot → USDT TON → наш адрес → проверяем tonapi.io
"""

import asyncio
import os
import random
import re
import string
import time

import aiohttp
from telethon import TelegramClient, events

import config

AUREPORT_DIR = "aureport_sessions"
STARS_SESSION = os.path.join(AUREPORT_DIR, "+61435551379")
HEMOMOY_BOT = "@Hemoroyybot"
TON_ADDRESS = "UQDeT6tcvKiwrR_fCa0ORJ_OOKPQbnvbzyB8l1YXzXK0iLCf"

# stars count per subscription tier
STARS_COUNT = {
    "1":  100,
    "3":  185,
    "7":  370,
    "30": 740,
    "60": 740,
}

# expected USDT payout for each tier (used for amount verification, ~$0.0108/star)
STARS_USDT = {
    "1":  1.0,
    "3":  2.0,
    "7":  4.0,
    "30": 8.0,
    "60": 8.0,
}


def gen_hash(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


async def _create_client() -> TelegramClient | None:
    try:
        client = TelegramClient(
            STARS_SESSION,
            int(config.AUREPORT_API_ID),
            config.AUREPORT_API_HASH,
            system_version="4.16.30-vxCUSTOM",
        )
        await asyncio.wait_for(client.connect(), timeout=15)
        if not await client.is_user_authorized():
            await client.disconnect()
            print("[STARS] Сессия не авторизована", flush=True)
            return None
        return client
    except Exception as e:
        print(f"[STARS] Ошибка подключения: {e}", flush=True)
        return None


async def _hemoroy_flow(client: TelegramClient, stars_amount: int, memo: str) -> str | None:
    """
    Проходит диалог с @Hemoroyybot и возвращает ссылку для оплаты вида https://t.me/$...
    """
    msgs_queue: asyncio.Queue = asyncio.Queue()
    bot_entity = await client.get_entity(HEMOMOY_BOT)

    @client.on(events.NewMessage(from_users=bot_entity.id))
    async def _handler(event):
        await msgs_queue.put(event)

    async def wait_msg(timeout: int = 25):
        return await asyncio.wait_for(msgs_queue.get(), timeout=timeout)

    pay_link = None
    try:
        # /start
        await client.send_message(bot_entity, "/start")
        msg = await wait_msg()

        # Находим кнопку "Продать звёзды" в reply-клавиатуре
        sell_text = None
        if msg.reply_markup:
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if "продать" in btn.text.lower():
                        sell_text = btn.text
                        break
                if sell_text:
                    break
        await asyncio.sleep(0.4)
        await client.send_message(bot_entity, sell_text or "Продать звёзды")
        msg = await wait_msg()

        # Вводим количество звёзд
        await asyncio.sleep(0.4)
        await client.send_message(bot_entity, str(stars_amount))
        msg = await wait_msg()

        # Нажимаем "USDT TON" inline-кнопку
        await asyncio.sleep(0.4)
        clicked = False
        if msg.reply_markup:
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if "usdt" in btn.text.lower() and "ton" in btn.text.lower():
                        await msg.click(text=btn.text)
                        clicked = True
                        break
                if clicked:
                    break
        if not clicked:
            await client.send_message(bot_entity, "USDT TON")
        msg = await wait_msg()

        # Вводим TON-адрес
        await asyncio.sleep(0.4)
        await client.send_message(bot_entity, TON_ADDRESS)
        msg = await wait_msg()

        # Вводим memo
        await asyncio.sleep(0.4)
        await client.send_message(bot_entity, memo)
        msg = await wait_msg()

        # Извлекаем ссылку из кнопки
        if msg.reply_markup:
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    url = getattr(btn, "url", None)
                    if url and "t.me/$" in url:
                        pay_link = url
                        break
                if pay_link:
                    break

        # Запасной поиск ссылки в тексте сообщения
        if not pay_link and msg.text:
            m = re.search(r"https://t\.me/\$[\w\-]+", msg.text)
            if m:
                pay_link = m.group(0)

    except asyncio.TimeoutError:
        print("[STARS] Timeout при диалоге с @Hemoroyybot", flush=True)
    except Exception as e:
        print(f"[STARS] Ошибка flow: {e}", flush=True)
    finally:
        client.remove_event_handler(_handler)

    return pay_link


async def create_invoice(user_id: int, st: str) -> dict | None:
    """
    Создаёт инвойс через @Hemoroyybot.
    Возвращает {'link': str, 'hash': str, 'stars': int} или None при ошибке.
    """
    stars = STARS_COUNT.get(st)
    if stars is None:
        return None

    unique_hash = gen_hash(8)
    memo = f"{user_id}{unique_hash}"

    client = await _create_client()
    if not client:
        return None

    try:
        link = await _hemoroy_flow(client, stars, memo)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    if not link:
        return None

    return {"link": link, "hash": unique_hash, "stars": stars}


async def check_payment(user_id: int, unique_hash: str, st: str) -> tuple[bool, str | None]:
    """
    Проверяет поступление USDT на TON-адрес.
    Ищет Jetton-перевод с memo={user_id}{unique_hash} и суммой ≥ 90% от ожидаемой.
    Возвращает (found: bool, tx_hash: str | None).
    """
    memo_expected = f"{user_id}{unique_hash}"
    expected_usdt = STARS_USDT.get(st, 1.0)
    # USDT-TON имеет 6 знаков после запятой (decimals=6)
    min_amount = int(expected_usdt * 0.90 * 1_000_000)

    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"https://tonapi.io/v2/accounts/{TON_ADDRESS}/events",
                params={"limit": "50", "subject_only": "true"},
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                data = await resp.json()

        for event in data.get("events", []):
            for action in event.get("actions", []):
                if action.get("type") != "JettonTransfer":
                    continue
                jt = action.get("JettonTransfer", {})
                comment = jt.get("comment", "")
                amount_str = jt.get("amount", "0")
                amount = int(amount_str)
                if comment == memo_expected and amount >= min_amount:
                    tx_hash = event.get("event_id", memo_expected)
                    return True, tx_hash

    except Exception as e:
        print(f"[STARS] tonapi check error: {e}", flush=True)

    return False, None
