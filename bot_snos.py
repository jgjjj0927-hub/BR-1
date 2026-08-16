# coding: utf-8
"""
Brown V2 | bot-method
"""

import os
import asyncio
from datetime import datetime
from telethon import TelegramClient, functions, types
from telethon.errors import FloodWaitError
import config
from config import bot_logs
import keyboards

REPORT_TEXT = (
    "Dannyj bot rasprostranyaet personal'nye dannye pol'zovatelej. "
    "Proshu nezamedlitel'no zablokirovat'."
)
REPORT_REASON = types.InputReportReasonPersonalDetails()

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
main_bot = None
session_folder = 'sessions'
os.makedirs(session_folder, exist_ok=True)

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)


def set_bot_snos(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b


def _get_sessions():
    return [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]


def format_log_line(session, target, status):
    now = datetime.now().strftime("%H:%M:%S")
    return f"[{now}] {session}.session -> {target} - [{status}]"


async def _attack_with_session(session, bot_username):
    import random
    random_api = random.choice(API)
    api_id, api_hash = random_api.split(":")
    client = TelegramClient(
        f"./sessions/{session}", int(api_id), api_hash,
        system_version='4.16.30-vxCUSTOM'
    )
    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=10)
        except asyncio.TimeoutError:
            print(f"[BOT-SNOS] [{session}] timeout", flush=True)
            return 0
        if not await client.is_user_authorized():
            print(f"[BOT-SNOS] [{session}] not authorized", flush=True)
            return 0
        try:
            entity = await client.get_entity(bot_username)
        except Exception as e:
            print(f"[BOT-SNOS] [{session}] entity error: {e}", flush=True)
            return 0
        try:
            await client(functions.account.ReportPeerRequest(
                peer=entity,
                reason=REPORT_REASON,
                message=REPORT_TEXT
            ))
            print(f"[BOT-SNOS] [{session}] OK", flush=True)
            return 1
        except FloodWaitError as e:
            print(f"[BOT-SNOS] [{session}] flood {e.seconds}s", flush=True)
            return 0
        except Exception as e:
            print(f"[BOT-SNOS] [{session}] err: {str(e)[:60]}", flush=True)
            return 0
    except Exception as e:
        print(f"[BOT-SNOS] [{session}] {str(e)[:60]}", flush=True)
        return 0
    finally:
        if client.is_connected():
            await client.disconnect()


async def main_bot_snos(bot_username, reason_key, user, username, bot_url):
    import random
    from aiogram import types as aiogram_types

    try:
        import db as db_module
        check_target = bot_username.strip().lstrip('@').lower()
        if await db_module.is_target_whitelisted(check_target):
            await bot.send_message(
                user,
                "*\u26d4 \u0426\u0435\u043b\u044c \u0432 \u0431\u0435\u043b\u043e\u043c \u0441\u043f\u0438\u0441\u043a\u0435!*\n"
                "*\u0416\u0430\u043b\u043e\u0431\u044b \u043d\u0430 \u044d\u0442\u0443 \u0446\u0435\u043b\u044c \u0437\u0430\u043f\u0440\u0435\u0449\u0435\u043d\u044b.*",
                parse_mode="Markdown",
                reply_markup=keyboards.main_menu
            )
            try:
                await main_bot.send_message(
                    bot_logs,
                    "*\u26a0 \u041f\u043e\u043f\u044b\u0442\u043a\u0430 \u0441\u043d\u0435\u0441\u0442\u0438 \u0446\u0435\u043b\u044c \u0438\u0437 \u0431\u0435\u043b\u043e\u0433\u043e \u0441\u043f\u0438\u0441\u043a\u0430!*\n"
                    f"*\u0426\u0435\u043b\u044c:* `{bot_username}`\n"
                    f"*\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c:* `{user}` (@{username})\n"
                    "*\u041c\u0435\u0442\u043e\u0434:* \u0411\u043e\u0442-\u043c\u0435\u0442\u043e\u0434",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return
    except Exception as wl_e:
        print(f"[BOT-SNOS] whitelist check error: {wl_e}", flush=True)

    if "_" in username:
        username = "None"

    sessions = _get_sessions()
    total = len(sessions)

    print(f"[BOT-SNOS] start | target: {bot_url} | sessions: {total}", flush=True)

    tasks = [_attack_with_session(s, bot_username) for s in sessions]
    results = await asyncio.gather(*tasks)
    successful = sum(results)

    print(f"[BOT-SNOS] done: {successful}/{total}", flush=True)

    log_lines = [
        "Brown V2 log | bot-method",
        "-" * 42,
        f"User: {user} (@{username})",
        f"Target: {bot_url}",
        "-" * 42,
    ]
    for session, result in zip(sessions, results):
        status = "OK" if result == 1 else "FAIL"
        log_lines.append(format_log_line(session, bot_url, status))
    log_lines += ["-" * 42, f"Success: {successful}", f"Failed: {total - successful}"]

    log_name = f"brown_v2_bot_log_{os.urandom(10).hex()}.txt"
    log_path = os.path.join(LOG_FOLDER, log_name)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    caption_user = (
        f"*\U0001f916 \u0411\u043e\u0442-\u043c\u0435\u0442\u043e\u0434 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d!*\n\n"
        f"*\U0001f7e2 \u0423\u0441\u043f\u0435\u0448\u043d\u043e: {successful}*\n"
        f"*\U0001f534 \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c: {total - successful}*"
    )
    caption_log = (
        f"*\U0001f4c8 bot-method*\n\n"
        f"*\U0001f3af \u0426\u0435\u043b\u044c: {bot_url}*\n"
        f"\U0001f7e2 {successful} | \U0001f534 {total - successful}\n"
        f"\U0001f464 {user} (@{username})"
    )

    try:
        await bot.send_document(
            user, aiogram_types.InputFile(log_path),
            caption=caption_user, parse_mode="Markdown",
            reply_markup=keyboards.main_menu
        )
        await main_bot.send_document(
            bot_logs, aiogram_types.InputFile(log_path),
            caption=caption_log, parse_mode="Markdown"
        )
    except Exception as e:
        print(f"[BOT-SNOS] send error: {e}", flush=True)

    try:
        os.remove(log_path)
    except Exception:
        pass
