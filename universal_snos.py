# coding: utf-8
"""
Brown V2 | universal_snos.py
Универсальный метод — жалобы через все доступные методы по одной ссылке.
"""

import re
import os
import random
import asyncio
import logging
from typing import Optional

from telethon import TelegramClient
from telethon.errors import UsernameNotOccupiedError, UsernameInvalidError, ChannelPrivateError

import config
import keyboards
from utils import now_msk

logger = logging.getLogger(__name__)

bot = None
main_bot = None

def set_bot_universal(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b

# ─── API для резолва ──────────────────────────────────────────────────────────
API = [
    '24565698:5a084b434f8505ace703485b9da85040',
    '27904162:e7cba879b1c643ba77490bf328df5eab',
    '23037915:50f06f5b2223586fde0d1379ea91ebc7',
]

SESSION_FOLDER = 'sessions'

def _get_sessions():
    if not os.path.exists(SESSION_FOLDER):
        return []
    return [f.replace('.session', '') for f in os.listdir(SESSION_FOLDER) if f.endswith('.session')]

def _random_creds():
    raw = random.choice(API)
    api_id, api_hash = raw.split(':', 1)
    return int(api_id), api_hash

# ─── Парсер ссылок ────────────────────────────────────────────────────────────

# Типы результата
TYPE_PRIVATE_CHANNEL = "private_channel"   # t.me/c/... — запрещено
TYPE_INVITE          = "invite"            # t.me/+..., joinchat, uppercase hash
TYPE_MESSAGE         = "message"           # t.me/username/123
TYPE_BOT             = "bot"               # t.me/somebot
TYPE_USER_CHANNEL    = "user_channel"      # t.me/username
TYPE_INVALID         = "invalid"           # не распознана


def parse_link(raw: str) -> dict:
    """
    Возвращает:
      {
        "type": TYPE_*,
        "username": str | None,
        "message_id": int | None,
        "normalized": str,          # https://t.me/...
        "error": str | None,
      }
    """
    raw = raw.strip()

    # Извлечь URL из Markdown формата [текст](url)
    md = re.search(r'\[.*?\]\((https?://[^\)]+)\)', raw)
    if md:
        raw = md.group(1)

    # @username → https://t.me/username
    if raw.startswith('@') and '/' not in raw:
        raw = 'https://t.me/' + raw[1:]

    # Нормализовать схему
    if raw.startswith('t.me/'):
        raw = 'https://' + raw
    elif raw.startswith('http://t.me/'):
        raw = 'https://t.me/' + raw[len('http://t.me/'):]

    # Должно начинаться с https://t.me/
    if not raw.startswith('https://t.me/'):
        return _inv("Не распознана как ссылка Telegram")

    path = raw[len('https://t.me/'):].strip('/')

    if not path:
        return _inv("Пустой путь")

    # 1. Приватный канал t.me/c/NUMBER/NUMBER — запрещено
    if re.match(r'^c/\d+(/\d+)?$', path):
        return {
            "type": TYPE_PRIVATE_CHANNEL,
            "username": None, "message_id": None,
            "normalized": raw, "error": None,
        }

    # 2. Инвайт: t.me/+ или t.me/joinchat/
    if path.startswith('+') or path.startswith('joinchat/'):
        return {
            "type": TYPE_INVITE,
            "username": None, "message_id": None,
            "normalized": raw, "error": None,
        }

    # 3. Сегмент содержит заглавные буквы и нет слэша — инвайт-хэш
    segment = path.split('/')[0]
    if re.search(r'[A-Z]', segment) and '/' not in path:
        return {
            "type": TYPE_INVITE,
            "username": None, "message_id": None,
            "normalized": raw, "error": None,
        }

    # 4. Ссылка на сообщение: t.me/username/NUMBER
    msg_match = re.match(r'^([a-zA-Z][a-zA-Z0-9_]{3,})/(\d+)$', path)
    if msg_match:
        uname = msg_match.group(1).lower()
        mid = int(msg_match.group(2))
        return {
            "type": TYPE_MESSAGE,
            "username": uname, "message_id": mid,
            "normalized": f"https://t.me/{uname}/{mid}", "error": None,
        }

    # 5. Просто username
    if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,}$', path):
        uname = path.lower()
        link_type = TYPE_BOT if uname.endswith('bot') else TYPE_USER_CHANNEL
        return {
            "type": link_type,
            "username": uname, "message_id": None,
            "normalized": f"https://t.me/{uname}", "error": None,
        }

    return _inv("Формат ссылки не распознан")


def _inv(msg: str) -> dict:
    return {"type": TYPE_INVALID, "username": None, "message_id": None, "normalized": "", "error": msg}


# ─── Валидация через Telegram API ─────────────────────────────────────────────

async def validate_link(parsed: dict) -> dict:
    """
    Для инвайтов и приват-каналов не валидируем (нельзя без вступления).
    Для остальных — резолвим через Telethon.
    Возвращает parsed обновлённый, добавляет "valid": bool, "error" если есть.
    """
    t = parsed["type"]

    if t in (TYPE_PRIVATE_CHANNEL, TYPE_INVALID):
        return {**parsed, "valid": False}

    if t == TYPE_INVITE:
        # Нельзя проверить без вступления — доверяем формату
        return {**parsed, "valid": True}

    # Нужна Telethon-сессия
    sessions = _get_sessions()
    if not sessions:
        logger.warning("[UNIVERSAL] Нет сессий для валидации, пропускаем")
        return {**parsed, "valid": True}

    session_path = os.path.join(SESSION_FOLDER, random.choice(sessions))
    api_id, api_hash = _random_creds()

    try:
        client = TelegramClient(session_path, api_id, api_hash,
                                system_version='4.16.30-vxCUSTOM')
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return {**parsed, "valid": True}  # сессия протухла — пропускаем

        uname = parsed["username"]
        try:
            entity = await client.get_entity(uname)
        except (UsernameNotOccupiedError, UsernameInvalidError):
            await client.disconnect()
            return {**parsed, "valid": False, "error": f"@{uname} не существует"}
        except ChannelPrivateError:
            await client.disconnect()
            return {**parsed, "valid": False, "error": "Канал приватный"}
        except Exception as e:
            await client.disconnect()
            logger.warning(f"[UNIVERSAL] get_entity error: {e}")
            return {**parsed, "valid": True}  # при ошибке не блокируем

        # Для сообщения — проверяем что оно существует
        if parsed["type"] == TYPE_MESSAGE and parsed["message_id"]:
            try:
                msgs = await client.get_messages(entity, ids=[parsed["message_id"]])
                if not msgs or msgs[0] is None:
                    await client.disconnect()
                    return {**parsed, "valid": False,
                            "error": f"Сообщение #{parsed['message_id']} не найдено"}
            except Exception as e:
                logger.warning(f"[UNIVERSAL] get_messages error: {e}")

        await client.disconnect()
        return {**parsed, "valid": True}

    except Exception as e:
        logger.warning(f"[UNIVERSAL] validate error: {e}")
        return {**parsed, "valid": True}


# ─── Запуск всех методов ──────────────────────────────────────────────────────

async def run_universal(parsed: dict, tida_text: str, user: int, username: str,
                        status_msg_id: int, bot_instance):
    """
    Запускает все подходящие методы параллельно.
    Обновляет status_msg_id по ходу выполнения.
    """
    from botnet_snos import main as botnet_main, set_bot as botnet_set_bot
    from botnet_snos_premium import main2 as botnet_main2, set_bot2 as botnet_set_bot2
    from aureport_snos import main_aureport, set_bot_aureport
    from tida_snos import main_tida, set_bot_tida
    from channel_snos import main_channel_snos, set_bot_channel
    from dsa_snos import main_dsa_snos, set_bot_dsa
    from bot_snos import main_bot_snos, set_bot_snos

    link_type = parsed["type"]
    norm = parsed["normalized"]
    uname = parsed.get("username")
    mid = parsed.get("message_id")

    # Настраиваем боты
    for fn in (botnet_set_bot, botnet_set_bot2, set_bot_aureport,
               set_bot_tida, set_bot_channel, set_bot_dsa, set_bot_snos):
        try:
            fn(bot_instance)
        except Exception:
            pass

    # DSA defaults
    dsa_reason = "scam"
    dsa_sub = "None"
    dsa_text = tida_text or "This account is involved in scam or spam activity."

    # Определяем набор методов — lambdas чтобы корутины создавались лениво
    tasks_info = []  # (label, factory)

    if link_type == TYPE_MESSAGE:
        tasks_info = [
            ("🕸 Ботнет",      lambda: botnet_main(uname, mid, user, username, norm)),
            ("👑 Ботнет Прем", lambda: botnet_main2(uname, mid, user, username, norm)),
            ("🔍 AU Report",   lambda: main_aureport(norm, user, username)),
            ("🎵 TIDA",        lambda: main_tida(norm, dsa_text, user, username)),
            ("📢 Канал",       lambda: main_channel_snos(uname, "spam", user, username, mid)),
            ("🇪🇺 DSA",        lambda: main_dsa_snos(norm, user, username, dsa_reason, dsa_sub, dsa_text)),
        ]

    elif link_type == TYPE_INVITE:
        tasks_info = [
            ("🔍 AU Report",   lambda: main_aureport(norm, user, username)),
            ("🎵 TIDA",        lambda: main_tida(norm, dsa_text, user, username)),
        ]

    elif link_type == TYPE_BOT:
        tasks_info = [
            ("🤖 Бот-метод",   lambda: main_bot_snos(f"@{uname}", "personal", user, username, norm)),
            ("🇪🇺 DSA",        lambda: main_dsa_snos(norm, user, username, dsa_reason, dsa_sub, dsa_text)),
            ("🔍 AU Report",   lambda: main_aureport(norm, user, username)),
            ("🎵 TIDA",        lambda: main_tida(norm, dsa_text, user, username)),
        ]

    elif link_type == TYPE_USER_CHANNEL:
        tasks_info = [
            ("🇪🇺 DSA",        lambda: main_dsa_snos(norm, user, username, dsa_reason, dsa_sub, dsa_text)),
            ("🔍 AU Report",   lambda: main_aureport(norm, user, username)),
            ("🎵 TIDA",        lambda: main_tida(norm, dsa_text, user, username)),
        ]

    import time as _time

    total = len(tasks_info)
    results = {}       # label -> "✅" | "❌"
    start_ts = _time.monotonic()

    BAR_LEN = 15

    def _bar(pct: int) -> str:
        filled = round(BAR_LEN * pct / 100)
        return "🟩" * filled + "⬜" * (BAR_LEN - filled)

    def _eta(done: int) -> str:
        if done == 0:
            return ""
        elapsed = _time.monotonic() - start_ts
        per_task = elapsed / done
        remaining_sec = int(per_task * (total - done))
        if remaining_sec < 60:
            return f"~{remaining_sec} сек"
        return f"~{remaining_sec // 60} мин {remaining_sec % 60} сек"

    def _status_text() -> str:
        done = sum(1 for v in results.values() if v in ("✅", "❌"))
        pct = round(done / total * 100) if total else 100
        lines = [f"⚙️ *Универсальный метод*\n`{norm}`\n"]
        if done < total:
            eta = _eta(done)
            eta_str = f" — {eta}" if eta else ""
            lines.append(f"{_bar(pct)} *{pct}%*{eta_str}\n")
        for label, _ in tasks_info:
            mark = results.get(label, "⏳")
            lines.append(f"{mark} {label}")
        ok = sum(1 for v in results.values() if v == "✅")
        fail = sum(1 for v in results.values() if v == "❌")
        if done == total:
            lines.append(f"\n{_bar(100)} *100%*")
            lines.append(f"✅ *{ok}/{total}* успешно, ❌ *{fail}* ошибок")
        return "\n".join(lines)

    async def _update():
        try:
            await bot_instance.edit_message_text(
                user, status_msg_id, _status_text(), parse_mode="Markdown")
        except Exception:
            pass

    async def _run_one(label: str, factory):
        try:
            await factory()
            results[label] = "✅"
        except Exception as e:
            logger.warning(f"[UNIVERSAL] {label} error: {e}")
            results[label] = "❌"
        await _update()

    # Начальное состояние
    await _update()

    # Запуск параллельно
    await asyncio.gather(*[_run_one(label, factory) for label, factory in tasks_info])
