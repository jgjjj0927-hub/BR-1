"""
Brown V2 | bot-method
Жалобы на Telegram-ботов через ReportPeerRequest
Схема: /start → ReportPeerRequest (основная причина) + ReportPeerRequest(Spam) → ContactsBlockRequest
"""

import os
import random
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserBotError, ChatWriteForbiddenError
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.functions.messages import SendMessageRequest
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
    "funstat": [
        "Бот используется для массого сбора информации о пользователях(парсинг) тем самым нарушая конфеденциальность пользователей. Прошу разобраться",
        "Бот используется для массого сбора информации о пользователях(парсинг) тем самым нарушая конфеденциальность пользователей. Прошу разобраться",
        "Бот используется для массого сбора информации о пользователях(парсинг) тем самым нарушая конфеденциальность пользователей. Прошу разобраться",
        "Бот используется для массого сбора информации о пользователях(парсинг) тем самым нарушая конфеденциальность пользователей. Прошу разобраться",
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
    """
    Отправляет жалобу на бота от одной сессии.
    - Обычные причины: /start → ReportPeerRequest × 2
    - funstat: /start → получаем сообщение → 3-шаговый ReportRequest × 4
      (Персональные данные → Другие личные данные → текст funstat)
    """
    random_api = random.choice(API)
    api_id, api_hash = random_api.split(":")
    reason_main, reason_secondary = REASONS[reason_key]
    text = random.choice(TEXTS[reason_key])[:200]

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
        print(f"[BOT-SNOS] [{session}] ✅ Подключён к {bot_username}", flush=True)

        # ── Шаг 1: отправляем /start чтобы "познакомиться" с ботом ──────────
        msg_id = None
        try:
            sent = await client(SendMessageRequest(peer=peer, message='/start', random_id=random.randint(1, 2**31)))
            # Получаем ID отправленного сообщения для использования в ReportRequest
            if hasattr(sent, 'id'):
                msg_id = sent.id
            elif hasattr(sent, 'updates'):
                for upd in sent.updates:
                    if hasattr(upd, 'id'):
                        msg_id = upd.id
                        break
            print(f"[BOT-SNOS] [{session}] 📨 /start отправлен, msg_id={msg_id}", flush=True)
            await asyncio.sleep(random.uniform(0.5, 1.5))
        except (ChatWriteForbiddenError, UserBotError):
            pass
        except Exception as e:
            print(f"[BOT-SNOS] [{session}] ⚠️ /start не удался: {str(e)[:50]}", flush=True)

        # ── FunStat: 3-шаговый флоу через messages.ReportRequest × 4 ─────────
        if reason_key == "funstat" and msg_id:
            from telethon.tl.functions.messages import ReportRequest
            funstat_text = TEXTS["funstat"][0]
            reported = False
            for attempt in range(4):
                try:
                    # Шаг 1: получаем категории
                    r1 = await client(ReportRequest(peer=peer, id=[msg_id], option=b'', message=''))
                    print(f"[BOT-SNOS] [{session}] 📋 Категории: {[o.option for o in r1.options] if hasattr(r1, 'options') and r1.options else 'нет'}", flush=True)

                    # Шаг 2: ищем "Персональные данные" (b'6' или берём первую подходящую)
                    personal_opt = None
                    if hasattr(r1, 'options') and r1.options:
                        # Пробуем найти категорию личных данных по байту b'6'
                        for opt in r1.options:
                            if opt.option == b'6':
                                personal_opt = opt.option
                                break
                        if personal_opt is None:
                            # Берём последнюю категорию (обычно "Другое/Личные данные")
                            personal_opt = r1.options[-1].option
                    else:
                        personal_opt = b'6'  # fallback

                    print(f"[BOT-SNOS] [{session}] 🔎 Выбрана категория: {personal_opt!r}", flush=True)
                    r2 = await client(ReportRequest(peer=peer, id=[msg_id], option=personal_opt, message=''))

                    # Шаг 3: выбираем подкатегорию — берём последнюю ("Другие личные данные")
                    if hasattr(r2, 'options') and r2.options:
                        sub_opt = r2.options[-1].option
                        print(f"[BOT-SNOS] [{session}] 🔎 Подкатегория: {sub_opt!r}", flush=True)
                        r3 = await client(ReportRequest(peer=peer, id=[msg_id], option=sub_opt, message=funstat_text))
                    else:
                        # Нет подкатегорий — отправляем с текстом напрямую
                        r3 = await client(ReportRequest(peer=peer, id=[msg_id], option=personal_opt, message=funstat_text))

                    print(f"[BOT-SNOS] [{session}] 📥 Репорт {attempt+1}/4 (funstat 3-шаг): {type(r3).__name__}", flush=True)
                    reported = True
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                except Exception as e:
                    print(f"[BOT-SNOS] [{session}] ⚠️ Ошибка репорта {attempt+1}/4: {str(e)[:60]}", flush=True)
                    break

            if reported:
                print(f"[BOT-SNOS] [{session}] ✅ ДОСТАВЛЕНО (funstat)", flush=True)
                return "ДОСТАВЛЕНО"
            else:
                print(f"[BOT-SNOS] [{session}] ⚠️ ОТКЛОНЕНО (funstat)", flush=True)
                return "ОТКЛОНЕНО"

        # ── Обычные причины: 2 репорта через ReportPeerRequest ───────────────
        r1 = await client(ReportPeerRequest(peer=peer, reason=reason_main, message=text))
        print(f"[BOT-SNOS] [{session}] 📥 Репорт 1 ({type(reason_main).__name__}): {r1}", flush=True)
        print(f"[BOT-SNOS] [{session}] 📝 Текст 1: {text[:60]}...", flush=True)

        await asyncio.sleep(random.uniform(0.3, 0.8))

        text2 = random.choice(TEXTS[reason_key])[:200]
        r2 = await client(ReportPeerRequest(peer=peer, reason=reason_secondary, message=text2))
        print(f"[BOT-SNOS] [{session}] 📥 Репорт 2 ({type(reason_secondary).__name__}): {r2}", flush=True)

        if r1 or r2:
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
