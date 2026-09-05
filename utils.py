"""
Brown V2 | utils.py
Общие утилиты.
"""
from datetime import datetime
import pytz
import sqlite3

_MSK = pytz.timezone("Europe/Moscow")


def now_msk() -> datetime:
    """Возвращает текущее время в московском часовом поясе (UTC+3)."""
    return datetime.now(_MSK).replace(tzinfo=None)


def enable_wal(session_path: str):
    """Переключает SQLite-сессию Telethon в WAL-режим (устраняет 'database is locked')."""
    db_path = session_path if session_path.endswith(".session") else session_path + ".session"
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.close()
    except Exception:
        pass
