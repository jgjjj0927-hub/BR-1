"""
Brown V2 | bot-method
Жалобы на Telegram-ботов через ReportPeerRequest
Схема: get_entity → ReportPeerRequest (без /start, как в рабочем скрипте)
"""

import os
import random
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonChildAbuse,
    InputReportReasonPornography,
    InputReportReasonOther,
    InputReportReasonPersonalDetails,
    InputReportReasonViolence,
    InputReportReasonCopyright,
    InputReportReasonGeoIrrelevant,
)
import config
from config import bot_logs
import keyboards
from report_texts import GENERAL_TEXTS

# ─── Тексты по категориям ──────────────────────────────────────────────────────

TEXTS = {
    "personal": [
        "Бот собирает и распространяет личные данные: ИНН, адреса, номера телефонов без согласия. Прошу заблокировать.",
        "This bot collects and distributes personal data: phone numbers, IDs, addresses without consent. Please block.",
        "Бот публикует конфиденциальные данные пользователей: паспортные данные, телефоны, адреса. Требую блокировки.",
        "Bot leaks private user data including phone numbers, home addresses and personal IDs. Immediate action required.",
        "Бот незаконно обрабатывает и продаёт персональные данные пользователей. Прошу немедленно заблокировать.",
        "This bot illegally processes and sells users' personal data including phone numbers and addresses. Block it.",
        "Бот собирает личные данные: номера телефонов, адреса, ИНН — и передаёт третьим лицам. Прошу разобраться.",
        "Bot harvests and distributes user personal data without consent: phones, addresses, IDs. Please block.",
    ],
    "adult": [
        "Бот распространяет порнографический контент без верификации возраста пользователей. Прошу заблокировать.",
        "This bot sends explicit adult content to users without age verification. Please block immediately.",
        "Бот рассылает контент 18+ без проверки возраста и без согласия получателей. Требую блокировки.",
        "This bot distributes pornographic material without age verification and user consent. Block required.",
        "Бот публикует материалы сексуального характера без ограничений по возрасту. Прошу принять меры.",
        "Bot sends unsolicited explicit content to users with no age gate or consent. Immediate block needed.",
        "Бот распространяет порнографию без верификации — нарушает ToS Telegram. Прошу заблокировать.",
        "This bot violates Telegram ToS by distributing adult content without age checks. Please block.",
    ],
    "children": [
        "Бот содержит и распространяет незаконный контент с участием несовершеннолетних. Требую немедленной блокировки.",
        "This bot distributes illegal content involving minors. This is CSAM. Block this bot immediately.",
        "Бот публикует материалы сексуального насилия над детьми. Требую немедленного удаления и блокировки.",
        "This bot contains child sexual abuse material (CSAM). Immediate removal and block is required.",
        "Бот распространяет незаконный контент с несовершеннолетними. Это уголовно наказуемо. Заблокируйте.",
        "Bot distributes illegal CSAM content. This violates Telegram ToS and international law. Block immediately.",
        "Бот содержит детскую порнографию. Требую экстренной блокировки и передачи данных в органы.",
        "This bot spreads child abuse material. Urgent action and block required. Report to authorities.",
    ],
    "snoser": [
        "Бот предоставляет услуги массовой атаки на аккаунты пользователей Telegram. Прошу заблокировать.",
        "This bot offers paid harassment services targeting Telegram users. It must be blocked immediately.",
        "Бот используется для организации массовых жалоб и блокировки аккаунтов. Прошу принять меры.",
        "This bot provides tools to mass-report and ban innocent Telegram accounts. Please block it.",
        "Бот продаёт услуги по незаконному преследованию и атакам на пользователей. Требую блокировки.",
        "Bot sells illegal account attack and harassment services against Telegram users. Block required.",
        "Бот нарушает ToS — предоставляет инструменты для атаки на аккаунты. Прошу заблокировать.",
        "This bot violates Telegram ToS by offering paid user attack and ban services. Please block.",
    ],
    "other": [
        "Бот систематически нарушает правила Telegram и используется для мошеннической деятельности. Прошу заблокировать.",
        "This bot violates Telegram Terms of Service and engages in fraudulent activity. Please block.",
        "Бот ведёт мошенническую деятельность и систематически нарушает правила платформы. Требую блокировки.",
        "This bot conducts fraudulent operations and repeatedly violates platform rules. Immediate block needed.",
        "Бот нарушает правила Telegram и причиняет вред пользователям. Прошу немедленно заблокировать.",
        "This bot breaks Telegram rules and harms users through systematic violations. Please block.",
        "Бот используется для обмана пользователей и нарушения ToS Telegram. Прошу принять меры.",
        "Bot is used for user deception and systematic ToS violations. Action and block required.",
    ],
    "funstat": [
        "Бот используется для массового сбора и парсинга данных пользователей без их согласия. Прошу заблокировать.",
        "This bot scrapes and harvests user data at scale without consent, violating privacy rules. Please block.",
        "Бот парсит личные данные пользователей Telegram: имена, телефоны, аккаунты. Нарушает ToS. Прошу заблокировать.",
        "This bot mass-parses Telegram user data including names and phone numbers without consent. Block it.",
        "Бот осуществляет незаконный сбор персональных данных пользователей (парсинг). Прошу разобраться и заблокировать.",
        "Bot illegally collects and stores personal Telegram user data through automated scraping. Please block.",
        "Бот нарушает конфиденциальность: массово собирает данные пользователей без разрешения. Требую блокировки.",
        "This bot violates user privacy by mass-collecting personal data without permission. Immediate block required.",
    ],
}

# Маппинг причины → Telethon тип (основная + дополнительная для двойного удара)
REASONS = {
    "personal": (InputReportReasonPersonalDetails(), InputReportReasonSpam()),
    "adult":    (InputReportReasonPornography(),     InputReportReasonSpam()),
    "children": (InputReportReasonChildAbuse(),      InputReportReasonChildAbuse()),
    "snoser":   (InputReportReasonViolence(),        InputReportReasonSpam()),
    "other":    (InputReportReasonOther(),           InputReportReasonGeoIrrelevant()),
    "funstat":  (InputReportReasonOther(),           InputReportReasonOther()),
}

REASON_LABELS = {
    "personal": "🔐 Персональные данные",
    "adult": "🔞 18+ контент",
    "children": "👶 Детский контент",
    "snoser": "💥 Сносер",
    "other": "📝 Прочее",
    "funstat": "📊 FunStat (парсинг)",
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


def _get_sessions():
    return [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)


def set_bot_snos(b):
    global bot
    bot = b


def format_log_line(session, target, status):
    now = datetime.now().strftime("%H:%M:%S")
    return f"[{now}] {session}.session -> {target} - [{status}]"


async def _report_one_bot_session(session, bot_username, reason_key):
    """
    Отправляет жалобу на бота от одной сессии.
    3-шаговый флоу как в ботнете: ReportRequest с динамическими категориями.
    """
    random_api = random.choice(API)
    api_id, api_hash = random_api.split(":")
    reason_main, _ = REASONS[reason_key]
    # Fallback причина в bytes для ReportRequest
    reason_bytes_map = {
        "personal": b'6', "adult": b'5', "children": b'2',
        "snoser": b'3', "other": b'a', "funstat": b'a',
    }
    fallback_reason = reason_bytes_map.get(reason_key, b'a')

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

        peer = await client.get_entity(bot_username)
        print(f"[BOT-SNOS] [{session}] ✅ Подключён к {bot_username}", flush=True)

        # Берём случайное сообщение из объединённого пула
        combined_texts = TEXTS[reason_key] + GENERAL_TEXTS
        random_reason_text = random.choice(combined_texts)

        sent = 0
        for attempt in range(2):
            try:
                # 3-шаговый флоу
                try:
                    print(f"[BOT-SNOS] [{session}] 📤 Шаг 1: запрашиваем категории...", flush=True)
                    r1 = await client(ReportRequest(peer=peer, id=[], option=b'', message=''))
                    if hasattr(r1, 'options') and r1.options:
                        cat = random.choice(r1.options).option
                    else:
                        cat = fallback_reason
                    r2 = await client(ReportRequest(peer=peer, id=[], option=cat, message=''))
                    if hasattr(r2, 'options') and r2.options:
                        sub = random.choice(r2.options).option
                        await client(ReportRequest(peer=peer, id=[], option=sub, message=random_reason_text))
                    else:
                        await client(ReportRequest(peer=peer, id=[], option=cat, message=random_reason_text))
                    print(f"[BOT-SNOS] [{session}] ✅ 3-шаг завершён", flush=True)
                except Exception as e3:
                    # Fallback — старый ReportPeerRequest
                    print(f"[BOT-SNOS] [{session}] ⚠️ 3-шаг ошибка ({str(e3)[:40]}), fallback...", flush=True)
                    await client(ReportPeerRequest(
                        peer=peer, reason=reason_main, message=random_reason_text
                    ))
                sent += 1
                await asyncio.sleep(random.uniform(0.5, 1.2))
            except FloodWaitError as e:
                print(f"[BOT-SNOS] [{session}] 🌊 FLOOD {e.seconds}с", flush=True)
                return f"FLOOD {e.seconds}s"
            except Exception as e:
                print(f"[BOT-SNOS] [{session}] ⚠️ Репорт {attempt+1} ошибка: {str(e)[:60]}", flush=True)
                break

        if sent > 0:
            print(f"[BOT-SNOS] [{session}] ✅ ДОСТАВЛЕНО ({sent}/2)", flush=True)
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
    _sessions = _get_sessions()
    print(f"[BOT-SNOS] 📦 Сессий: {len(_sessions)}", flush=True)
    print(f"{'='*50}", flush=True)

    # Запускаем пачками по 8
    BATCH_SIZE = 8
    results = []
    for i in range(0, len(_sessions), BATCH_SIZE):
        batch = _sessions[i:i + BATCH_SIZE]
        batch_tasks = [_report_one_bot_session(s, bot_username, reason_key) for s in batch]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        results.extend(zip(batch, batch_results))
        if i + BATCH_SIZE < len(_sessions):
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
