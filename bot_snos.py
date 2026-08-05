"""
Brown V2 | bot-method
Жалобы на Telegram-ботов через ReportPeerRequest
"""

import os
import random
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonChildAbuse,
    InputReportReasonPornography,
    InputReportReasonOther,
    InputReportReasonPersonalDetails,
)
import config
from config import bot_logs
import keyboards

# ─── Тексты по категориям ──────────────────────────────────────────────────────

TEXTS = {
    "personal": [
        "This bot collects and distributes personal data without consent.",
        "Бот незаконно собирает персональные данные и передаёт третьим лицам.",
        "This violates Telegram ToS: https://telegram.org/tos — bot harvests user credentials and phone numbers.",
        "Это нарушает правила ToS: https://telegram.org/tos — бот собирает конфиденциальные данные пользователей.",
        "Bot is harvesting personal information including passwords and financial data.",
        "Данный бот запрашивает конфиденциальную информацию с целью её кражи.",
        "This violates Telegram ToS: https://telegram.org/tos — unauthorized personal data collection.",
        "Это нарушает правила ToS: https://telegram.org/tos — бот собирает данные без разрешения.",
    ],
    "adult": [
        "This bot distributes explicit adult content without age verification.",
        "Бот распространяет контент для взрослых без проверки возраста.",
        "This violates Telegram ToS: https://telegram.org/tos — bot sends unsolicited pornographic content.",
        "Это нарушает правила ToS: https://telegram.org/tos — бот публикует материалы сексуального характера без согласия.",
        "Bot is sending unsolicited explicit material to users.",
        "Данный бот рассылает неприемлемый контент для взрослых без ограничений.",
        "This violates Telegram ToS: https://telegram.org/tos — explicit content distributed without age check.",
        "Это нарушает правила ToS: https://telegram.org/tos — распространение контента 18+ без верификации.",
    ],
    "children": [
        "This bot distributes illegal content involving minors.",
        "Бот распространяет материалы, эксплуатирующие несовершеннолетних.",
        "This violates Telegram ToS: https://telegram.org/tos — bot contains child abuse material.",
        "Это нарушает правила ToS: https://telegram.org/tos — бот публикует незаконный контент с участием детей.",
        "Bot is spreading CSAM and must be removed immediately.",
        "Данный бот публикует материалы сексуального насилия над детьми.",
        "This violates Telegram ToS: https://telegram.org/tos — illegal content involving minors detected.",
        "Это нарушает правила ToS: https://telegram.org/tos — незаконный контент с несовершеннолетними.",
    ],
    "snoser": [
        "This bot provides illegal services to harm other Telegram users.",
        "Бот используется для массовых атак и преследования пользователей.",
        "This violates Telegram ToS: https://telegram.org/tos — bot is used for targeted harassment and abuse.",
        "Это нарушает правила ToS: https://telegram.org/tos — бот используется для незаконной деятельности против пользователей.",
        "Bot offers paid attack services against innocent users.",
        "Данный бот предоставляет платные услуги по атаке на аккаунты пользователей.",
        "This violates Telegram ToS: https://telegram.org/tos — bot is a scam attack tool.",
        "Это нарушает правила ToS: https://telegram.org/tos — бот используется для незаконного давления на пользователей.",
    ],
    "other": [
        "This bot engages in systematic violation of platform rules.",
        "Бот систематически нарушает правила платформы.",
        "This violates Telegram ToS: https://telegram.org/tos — bot must be removed immediately.",
        "Это нарушает правила ToS: https://telegram.org/tos — данный бот нарушает политику Telegram.",
        "Bot is conducting fraudulent and abusive activities.",
        "Данный бот ведёт мошенническую деятельность и нарушает ToS.",
        "This violates Telegram ToS: https://telegram.org/tos — systematic rule violations detected.",
        "Это нарушает правила ToS: https://telegram.org/tos — систематические нарушения правил платформы.",
    ],
}

# Маппинг причины → Telethon тип
REASONS = {
    "personal": InputReportReasonPersonalDetails(),
    "adult": InputReportReasonPornography(),
    "children": InputReportReasonChildAbuse(),
    "snoser": InputReportReasonSpam(),
    "other": InputReportReasonOther(),
}

REASON_LABELS = {
    "personal": "🔐 Персональные данные",
    "adult": "🔞 18+ контент",
    "children": "👶 Детский контент",
    "snoser": "💥 Сносер",
    "other": "📝 Прочее",
}

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

bot = None
session_folder = 'sessions'
os.makedirs(session_folder, exist_ok=True)
sessions = [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)


def set_bot_snos(b):
    global bot
    bot = b


def format_log_line(session, target, status):
    now = datetime.now().strftime("%H:%M:%S")
    return f"[{now}] {session}.session -> {target} - [{status}]"


async def _report_one_bot_session(session, bot_username, reason_key):
    """Отправляет жалобу на бота от одной сессии."""
    random_api = random.choice(API)
    api_id, api_hash = random_api.split(":")
    reason = REASONS[reason_key]
    text = random.choice(TEXTS[reason_key])

    print(f"[BOT-SNOS] [{session}] Подключаемся...", flush=True)

    client = TelegramClient(
        f"./sessions/{session}", int(api_id), api_hash,
        system_version='4.16.30-vxCUSTOM'
    )
    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=8)
        except asyncio.TimeoutError:
            print(f"[BOT-SNOS] [{session}] ❌ ОШИБКА СОЕДИНЕНИЯ", flush=True)
            return "ОШИБКА СОЕДИНЕНИЯ"

        if not await client.is_user_authorized():
            print(f"[BOT-SNOS] [{session}] ❌ НЕВАЛИД", flush=True)
            return "НЕВАЛИД"

        await client.start()
        peer = await client.get_entity(bot_username)
        print(f"[BOT-SNOS] [{session}] ✅ Подключён, отправляем жалобу на {bot_username}...", flush=True)

        result = await client(ReportPeerRequest(peer=peer, reason=reason, message=text))
        print(f"[BOT-SNOS] [{session}] 📥 Ответ сервера: {type(result).__name__} | {result}", flush=True)

        if result:
            print(f"[BOT-SNOS] [{session}] ✅ ДОСТАВЛЕНО", flush=True)
            return "ДОСТАВЛЕНО"
        else:
            print(f"[BOT-SNOS] [{session}] ⚠️ ОТКЛОНЕНО", flush=True)
            return "ОТКЛОНЕНО"

    except FloodWaitError as e:
        print(f"[BOT-SNOS] [{session}] 🌊 FLOOD {e.seconds}с", flush=True)
        return f"FLOOD {e.seconds}s"
    except Exception as e:
        err = str(e)[:60]
        print(f"[BOT-SNOS] [{session}] ❌ ОШИБКА: {err}", flush=True)
        return f"ОШИБКА: {err}"
    finally:
        if client.is_connected():
            await client.disconnect()


async def main_bot_snos(bot_username, reason_key, user, username, bot_url):
    """Главная функция жалоб на бота."""
    if "_" in username:
        username = "None"

    reason_label = REASON_LABELS.get(reason_key, reason_key)

    print(f"\n{'='*50}", flush=True)
    print(f"[BOT-SNOS] 🚀 Запуск bot-метода", flush=True)
    print(f"[BOT-SNOS] 👤 Пользователь: {user} (@{username})", flush=True)
    print(f"[BOT-SNOS] 🎯 Цель: {bot_url}", flush=True)
    print(f"[BOT-SNOS] 📋 Причина: {reason_label}", flush=True)
    print(f"[BOT-SNOS] 📦 Сессий: {len(sessions)}", flush=True)
    print(f"{'='*50}", flush=True)

    # Запускаем пачками по 8
    BATCH_SIZE = 8
    results = []
    for i in range(0, len(sessions), BATCH_SIZE):
        batch = sessions[i:i + BATCH_SIZE]
        batch_tasks = [_report_one_bot_session(s, bot_username, reason_key) for s in batch]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        results.extend(zip(batch, batch_results))
        if i + BATCH_SIZE < len(sessions):
            delay = random.uniform(3, 5)
            print(f"[BOT-SNOS] ⏳ Пачка {i//BATCH_SIZE + 1} завершена, ждём {delay:.1f}с...", flush=True)
            await asyncio.sleep(delay)

    valid, ne_valid, flood = 0, 0, 0
    log_lines = [
        "Brown V2 log | bot-method",
        "-" * 42,
        f"Пользователь: {user} (@{username})",
        f"Цель: {bot_url}",
        f"Причина: {reason_label}",
        "-" * 42,
    ]

    for session, result in results:
        if isinstance(result, Exception):
            ne_valid += 1
            log_lines.append(format_log_line(session, bot_url, f"ИСКЛЮЧЕНИЕ: {str(result)[:50]}"))
            continue

        status = result
        if status == "ДОСТАВЛЕНО":
            valid += 1
            log_lines.append(format_log_line(session, bot_url, "ДОСТАВЛЕНО"))
        elif "FLOOD" in str(status):
            flood += 1
            log_lines.append(format_log_line(session, bot_url, status))
        else:
            ne_valid += 1
            log_lines.append(format_log_line(session, bot_url, status))

    print(f"\n[BOT-SNOS] {'='*50}", flush=True)
    print(f"[BOT-SNOS] 🏁 Итоги: ✅ {valid} | ❌ {ne_valid} | 🌊 {flood}", flush=True)
    print(f"[BOT-SNOS] {'='*50}\n", flush=True)

    log_lines += [
        "-" * 42,
        f"Успешно: {valid}",
        f"Неуспешно: {ne_valid}",
        f"Флудов: {flood}",
    ]

    log_name = f"brown_v2_bot_log_{os.urandom(10).hex()}.txt"
    log_path = os.path.join(LOG_FOLDER, log_name)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    from aiogram import types as aiogram_types
    caption_user = (
        f"🤖 *Бот-метод завершён!*\n"
        f"*└─ Причина: {reason_label}*\n\n"
        f"🟢 *Успешно: {valid}*\n"
        f"🔴 *Не удалось: {ne_valid}*"
    )
    caption_log = (
        f"📈 *bot-method*\n"
        f"*└─ Причина: {reason_label}*\n\n"
        f"🎯 *Цель: {bot_url}*\n"
        f"🟢 {valid} | 🔴 {ne_valid}\n"
        f"👤 {user} (@{username})"
    )

    try:
        await bot.send_document(user, aiogram_types.InputFile(log_path), caption=caption_user, parse_mode="Markdown", reply_markup=keyboards.main_menu)
        await bot.send_document(bot_logs, aiogram_types.InputFile(log_path), caption=caption_log, parse_mode="Markdown")
    except Exception as e:
        print(f"[BOT-SNOS] Ошибка отправки лога: {e}", flush=True)

    try:
        os.remove(log_path)
    except Exception:
        pass
