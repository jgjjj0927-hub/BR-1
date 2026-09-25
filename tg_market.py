"""
tg_market.py — TG Маркет: работа с пулом .session файлов Telethon.
"""
import os
import re
import sqlite3
import random

MARKET_DIR = "TG market"
ARH_DIR = "TG Arh"

_API_ID   = 24565698
_API_HASH = "5a084b434f8505ace703485b9da85040"


def get_available_count() -> int:
    if not os.path.exists(MARKET_DIR):
        return 0
    return len([f for f in os.listdir(MARKET_DIR) if f.endswith('.session')])


def _get_phone_from_session(path: str) -> str | None:
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT phone FROM sessions LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return f"+{row[0]}" if row and row[0] else None
    except Exception:
        return None


def pick_session() -> tuple[str, str] | tuple[None, None]:
    """Берёт случайный .session из MARKET_DIR. Возвращает (filename, phone) или (None, None)."""
    if not os.path.exists(MARKET_DIR):
        return None, None
    files = [f for f in os.listdir(MARKET_DIR) if f.endswith('.session')]
    if not files:
        return None, None
    filename = random.choice(files)
    phone = _get_phone_from_session(os.path.join(MARKET_DIR, filename))
    return filename, phone


def archive_session(filename: str):
    """Перемещает файл из MARKET_DIR в ARH_DIR."""
    src = os.path.join(MARKET_DIR, filename)
    os.makedirs(ARH_DIR, exist_ok=True)
    dst = os.path.join(ARH_DIR, filename)
    if os.path.exists(src):
        os.rename(src, dst)


async def get_auth_code(session_filename: str) -> str | None:
    """
    Подключается к аккаунту через Telethon и ищет последний код авторизации
    в сообщениях от 777000.
    """
    try:
        from telethon import TelegramClient

        # Ищем файл — сначала в архиве, потом в пуле
        path = None
        for directory in (ARH_DIR, MARKET_DIR):
            candidate = os.path.join(directory, session_filename)
            if os.path.exists(candidate):
                path = candidate
                break
        if path is None:
            return None

        # Telethon принимает путь без .session
        session_path = path[:-8] if path.endswith('.session') else path

        client = TelegramClient(session_path, _API_ID, _API_HASH,
                                system_version="4.16.30-vxCUSTOM")
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None

        msgs = await client.get_messages(777000, limit=10)
        await client.disconnect()

        for msg in msgs:
            if msg and msg.text:
                match = re.search(r'\b(\d{5,6})\b', msg.text)
                if match:
                    return match.group(1)
        return None
    except Exception as e:
        print(f"[tg_market] get_auth_code error: {e}")
        return None
