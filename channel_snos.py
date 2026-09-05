"""
Brown V2 | channel_snos.py
Жалобы на Telegram-каналы через ReportPeerRequest.
Схема: get_entity(channel) → ReportPeerRequest × 2 от каждой сессии.
"""

import os
import random
import asyncio
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
from utils import now_msk
from aiogram import types as aiogram_types
from report_texts import GENERAL_TEXTS

# ─── Тексты по категориям ──────────────────────────────────────────────────────

CHANNEL_TEXTS = {
    "personal": [
        "Канал собирает и распространяет личные данные пользователей: ИНН, адреса, телефоны. Прошу заблокировать.",
        "This channel collects and distributes personal data: phone numbers, IDs, addresses. Please block.",
        "Канал публикует конфиденциальные данные пользователей без их согласия. Требую блокировки.",
        "Channel leaks private user data including phone numbers, home addresses and IDs. Block required.",
        "Канал незаконно распространяет персональные данные: паспорта, телефоны, адреса. Прошу заблокировать.",
        "This channel illegally distributes personal data: passports, phones, addresses. Please block.",
        "Канал публикует личные данные людей без согласия. Нарушает ToS. Прошу разобраться.",
        "Channel posts personal data of users without consent, violating Telegram ToS. Block it.",
    ],
    "spam": [
        "Канал распространяет массовый спам и мошеннические предложения. Прошу заблокировать.",
        "This channel distributes mass spam and fraudulent offers. Please block immediately.",
        "Канал рассылает спам-контент и обманывает пользователей. Требую блокировки.",
        "Channel is spreading spam and scam content to users. Immediate block required.",
        "Канал нарушает правила Telegram: массовый спам и мошенничество. Прошу разобраться.",
        "This channel violates Telegram ToS through mass spam and fraud. Please block.",
        "Канал используется для распространения спама и фишинга. Прошу заблокировать.",
        "Channel conducts phishing and spam campaigns against users. Block required.",
    ],
    "adult": [
        "Канал распространяет порнографический контент без верификации возраста. Прошу заблокировать.",
        "This channel distributes explicit adult content without age verification. Please block.",
        "Канал публикует контент 18+ без проверки возраста подписчиков. Требую блокировки.",
        "Channel posts pornographic material without age gates or consent. Immediate block needed.",
        "Канал рассылает неприемлемый контент для взрослых без ограничений. Прошу принять меры.",
        "This channel spreads adult content without age verification violating ToS. Please block.",
        "Канал нарушает ToS Telegram: публикует порнографию без верификации. Прошу заблокировать.",
        "Channel violates Telegram ToS by distributing adult content without age checks. Block it.",
    ],
    "children": [
        "Канал содержит и распространяет незаконный контент с несовершеннолетними. Требую блокировки.",
        "This channel distributes illegal content involving minors (CSAM). Block immediately.",
        "Канал публикует материалы сексуального насилия над детьми. Требую экстренной блокировки.",
        "Channel contains child sexual abuse material. Urgent block and report to authorities.",
        "Канал распространяет незаконный контент с участием детей. Это уголовно наказуемо. Заблокируйте.",
        "This channel spreads illegal CSAM content. Immediate removal and block required.",
        "Канал содержит детскую порнографию. Требую немедленного удаления и блокировки.",
        "Channel distributes child abuse material violating international law. Block immediately.",
    ],
    "violence": [
        "Канал публикует контент, пропагандирующий насилие и призывающий к жестокости. Прошу заблокировать.",
        "This channel promotes violence and incites users to commit violent acts. Please block.",
        "Канал распространяет материалы, пропагандирующие насилие и экстремизм. Требую блокировки.",
        "Channel spreads violent content and extremist propaganda. Immediate block required.",
        "Канал публикует призывы к насилию и жестокие материалы. Прошу принять меры.",
        "This channel incites violence and distributes harmful extremist content. Please block.",
        "Канал нарушает ToS Telegram: пропаганда насилия и жестокости. Прошу заблокировать.",
        "Channel violates Telegram ToS by promoting violence and extremism. Block required.",
    ],
    "other": [
        "Канал систематически нарушает правила Telegram и ведёт мошенническую деятельность. Прошу заблокировать.",
        "This channel systematically violates Telegram ToS and engages in fraud. Please block.",
        "Канал нарушает правила платформы и причиняет вред пользователям. Требую блокировки.",
        "Channel breaks Telegram rules and harms users through repeated violations. Block needed.",
        "Канал ведёт незаконную деятельность и нарушает ToS Telegram. Прошу разобраться.",
        "This channel conducts illegal activities and violates Telegram Terms of Service. Block it.",
        "Канал систематически нарушает правила и используется для обмана. Прошу заблокировать.",
        "Channel is used for systematic fraud and ToS violations. Immediate action required.",
    ],
}

CHANNEL_REASONS = {
    "personal": (InputReportReasonPersonalDetails(), InputReportReasonSpam()),
    "spam":     (InputReportReasonSpam(),            InputReportReasonOther()),
    "adult":    (InputReportReasonPornography(),     InputReportReasonSpam()),
    "children": (InputReportReasonChildAbuse(),      InputReportReasonChildAbuse()),
    "violence": (InputReportReasonViolence(),        InputReportReasonSpam()),
    "other":    (InputReportReasonOther(),           InputReportReasonGeoIrrelevant()),
}

CHANNEL_REASON_LABELS = {
    "personal": "🔐 Персональные данные",
    "spam":     "📢 Спам / Мошенничество",
    "adult":    "🔞 18+ Контент",
    "children": "👶 Детский контент",
    "violence": "💥 Насилие / Экстремизм",
    "other":    "📝 Прочее",
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
main_bot = None  # основной бот — всегда для логов в bot_logs
session_folder = 'sessions'
os.makedirs(session_folder, exist_ok=True)

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)


def set_bot_channel(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b


def _get_sessions():
    return [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]


def format_log_line(session, target, status):
    now = now_msk().strftime("%H:%M:%S")
    return f"[{now}] {session}.session -> {target} - [{status}]"


async def _report_one_channel_session(session, channel_username, reason_key, message_id=None):
    """Отправляет жалобу на канал от одной сессии."""
    random_api = random.choice(API)
    api_id, api_hash = random_api.split(":", 1)
    reason_main, _ = CHANNEL_REASONS[reason_key]

    client = TelegramClient(
        f"./sessions/{session}", int(api_id), api_hash,
        system_version='4.16.30-vxCUSTOM'
    )
    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=8)
        except asyncio.TimeoutError:
            print(f"[CH-SNOS] [{session}] ❌ ОШИБКА СОЕДИНЕНИЯ", flush=True)
            return "ОШИБКА СОЕДИНЕНИЯ"

        if not await client.is_user_authorized():
            print(f"[CH-SNOS] [{session}] ❌ НЕВАЛИД", flush=True)
            return "НЕВАЛИД"

        peer = await client.get_entity(channel_username)
        print(f"[CH-SNOS] [{session}] ✅ Подключён к {channel_username}", flush=True)

        # Fallback причина
        reason_bytes_map = {
            "personal": b'6', "spam": b'9', "adult": b'5',
            "children": b'2', "violence": b'3', "other": b'a',
        }
        fallback_reason = reason_bytes_map.get(reason_key, b'a')
        combined_texts = CHANNEL_TEXTS[reason_key] + GENERAL_TEXTS
        random_reason_text = random.choice(combined_texts)[:200]

        sent = 0
        for attempt in range(2):
            try:
                msg_ids = [message_id] if message_id else []
                # 3-шаговый флоу
                try:
                    print(f"[CH-SNOS] [{session}] 📤 Шаг 1: запрашиваем категории...", flush=True)
                    r1 = await client(ReportRequest(peer=peer, id=msg_ids, option=b'', message=''))
                    if hasattr(r1, 'options') and r1.options:
                        cat = random.choice(r1.options).option
                    else:
                        cat = fallback_reason
                    r2 = await client(ReportRequest(peer=peer, id=msg_ids, option=cat, message=''))
                    if hasattr(r2, 'options') and r2.options:
                        sub = random.choice(r2.options).option
                        await client(ReportRequest(peer=peer, id=msg_ids, option=sub, message=random_reason_text))
                    else:
                        await client(ReportRequest(peer=peer, id=msg_ids, option=cat, message=random_reason_text))
                    print(f"[CH-SNOS] [{session}] ✅ 3-шаг завершён", flush=True)
                except Exception as e3:
                    # Fallback — старый метод
                    print(f"[CH-SNOS] [{session}] ⚠️ 3-шаг ошибка ({str(e3)[:40]}), fallback...", flush=True)
                    if message_id:
                        await client(ReportRequest(
                            peer=peer, id=[message_id],
                            reason=reason_main, message=random_reason_text
                        ))
                    else:
                        await client(ReportPeerRequest(
                            peer=peer, reason=reason_main, message=random_reason_text
                        ))
                sent += 1
                await asyncio.sleep(random.uniform(0.5, 1.2))
            except FloodWaitError as e:
                print(f"[CH-SNOS] [{session}] 🌊 FLOOD {e.seconds}с", flush=True)
                return f"FLOOD {e.seconds}s"
            except Exception as e:
                print(f"[CH-SNOS] [{session}] ⚠️ Репорт {attempt+1} ошибка: {str(e)[:60]}", flush=True)
                break

        if sent > 0:
            print(f"[CH-SNOS] [{session}] ✅ ДОСТАВЛЕНО ({sent}/2)", flush=True)
            return "ДОСТАВЛЕНО"
        else:
            print(f"[CH-SNOS] [{session}] ⚠️ ОТКЛОНЕНО", flush=True)
            return "ОТКЛОНЕНО"

    except FloodWaitError as e:
        print(f"[CH-SNOS] [{session}] 🌊 FLOOD {e.seconds}с", flush=True)
        return f"FLOOD {e.seconds}s"
    except Exception as e:
        err = str(e)[:60]
        print(f"[CH-SNOS] [{session}] ❌ ОШИБКА: {err}", flush=True)
        return f"ОШИБКА: {err}"
    finally:
        if client.is_connected():
            await client.disconnect()


async def main_channel_snos(channel_username, reason_key, user, username, message_id=None, _log_user=None):
    """Главная функция жалоб на канал."""
    reason_label = CHANNEL_REASON_LABELS.get(reason_key, reason_key)
    _sessions = _get_sessions()

    # ─── Проверка белого списка ────────────────────────────────────────────────
    try:
        import db as db_module
        # Нормализуем username для проверки
        check_target = channel_username.strip().lstrip('@').lower()
        if await db_module.is_target_whitelisted(check_target):
            await bot.send_message(user,
                "❌ *Цель в белом списке!*\n*└─ Жалобы на эту цель запрещены.*",
                parse_mode="Markdown", reply_markup=keyboards.main_menu)
            # Лог для администратора
            try:
                await main_bot.send_message(bot_logs,
                    f"⚠️ *Попытка снести цель из белого списка!*\n"
                    f"*└─ Цель:* `{channel_username}`\n"
                    f"*└─ Пользователь:* `{_log_user if _log_user is not None else user}` (@{username})\n"
                    f"*└─ Метод:* Канал-метод",
                    parse_mode="Markdown")
            except Exception as log_e:
                print(f"[CH-SNOS] Ошибка отправки лога WL: {log_e}", flush=True)
            return
    except Exception as wl_e:
        print(f"[CH-SNOS] Ошибка проверки белого списка: {wl_e}", flush=True)
    # ──────────────────────────────────────────────────────────────────────────

    print(f"\n{'='*50}", flush=True)
    print(f"[CH-SNOS] 🚀 Запуск жалоб на канал", flush=True)
    print(f"[CH-SNOS] 👤 Пользователь: {_log_user if _log_user is not None else user} (@{username})", flush=True)
    print(f"[CH-SNOS] 🎯 Цель: {channel_username}", flush=True)
    if message_id:
        print(f"[CH-SNOS] 📌 Сообщение: #{message_id}", flush=True)
    print(f"[CH-SNOS] 📋 Причина: {reason_label}", flush=True)
    print(f"[CH-SNOS] 📦 Сессий: {len(_sessions)}", flush=True)
    print(f"{'='*50}", flush=True)

    BATCH_SIZE = 8
    results = []
    for i in range(0, len(_sessions), BATCH_SIZE):
        batch = _sessions[i:i + BATCH_SIZE]
        batch_tasks = [_report_one_channel_session(s, channel_username, reason_key, message_id) for s in batch]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        results.extend(zip(batch, batch_results))
        if i + BATCH_SIZE < len(_sessions):
            delay = random.uniform(3, 5)
            print(f"[CH-SNOS] ⏳ Пачка {i//BATCH_SIZE + 1} завершена, ждём {delay:.1f}с...", flush=True)
            await asyncio.sleep(delay)

    valid, ne_valid, flood = 0, 0, 0
    log_lines = [
        "Brown V2 log | channel-method",
        "-" * 42,
        f"Пользователь: {_log_user if _log_user is not None else user} (@{username})",
        f"Цель: {channel_username}",
        f"Сообщение: #{message_id}" if message_id else "Сообщение: весь канал",
        f"Причина: {reason_label}",
        "-" * 42,
    ]

    for session, result in results:
        if isinstance(result, Exception):
            ne_valid += 1
            log_lines.append(format_log_line(session, channel_username, f"ИСКЛЮЧЕНИЕ: {str(result)[:50]}"))
            continue
        status = result
        if status == "ДОСТАВЛЕНО":
            valid += 1
            log_lines.append(format_log_line(session, channel_username, "ДОСТАВЛЕНО"))
        elif "FLOOD" in str(status):
            flood += 1
            log_lines.append(format_log_line(session, channel_username, status))
        else:
            ne_valid += 1
            log_lines.append(format_log_line(session, channel_username, status))

    print(f"\n[CH-SNOS] {'='*50}", flush=True)
    print(f"[CH-SNOS] 🏁 Итоги: ✅ {valid} | ❌ {ne_valid} | 🌊 {flood}", flush=True)
    print(f"[CH-SNOS] {'='*50}\n", flush=True)

    log_lines += [
        "-" * 42,
        f"Успешно: {valid}",
        f"Неуспешно: {ne_valid}",
        f"Флудов: {flood}",
    ]

    log_name = f"brown_v2_channel_log_{os.urandom(10).hex()}.txt"
    log_path = os.path.join(LOG_FOLDER, log_name)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    caption_user = (
        f"📢 *Жалобы на канал завершены!*\n"
        f"*└─ Цель: {channel_username}*\n"
        + (f"*└─ Сообщение: #{message_id}*\n" if message_id else "")
        + f"\n🟢 *Успешно: {valid}*\n"
        f"🔴 *Не удалось: {ne_valid}*"
    )
    caption_log = (
        f"📈 *Канал-метод завершён*\n"
        f"*└─ Цель: {channel_username}*\n"
        + (f"*└─ Сообщение: #{message_id}*\n" if message_id else "")
        + f"*└─ Причина: {reason_label}*\n\n"
        f"🟢 *Успешно: {valid}*\n🔴 *Не удалось: {ne_valid}*\n\n"
        f"👤 *Пользователь:* {_log_user if _log_user is not None else user} (@{username})"
    )

    try:
        await bot.send_document(user, aiogram_types.InputFile(log_path),
            caption=caption_user, parse_mode="Markdown", reply_markup=keyboards.main_menu)
        await main_bot.send_document(bot_logs, aiogram_types.InputFile(log_path),
            caption=caption_log, parse_mode="Markdown")
    except Exception as e:
        print(f"[CH-SNOS] Ошибка отправки лога: {e}", flush=True)

    try:
        os.remove(log_path)
    except Exception:
        pass
