"""
Brown V2 | utils.py
Общие утилиты.
"""
from datetime import datetime
import pytz

_MSK = pytz.timezone("Europe/Moscow")


def now_msk() -> datetime:
    """Возвращает текущее время в московском часовом поясе (UTC+3)."""
    return datetime.now(_MSK).replace(tzinfo=None)
