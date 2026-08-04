import os
import random
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import PeerUser
from telethon.tl.functions.messages import ReportRequest
from aiogram import types
import aiosqlite
from telethon import types as telethon_types
from aiogram import Bot, Dispatcher, executor, types
import config
from config import bot_logs
import keyboards

reasons = [
    b'2',  # Child abuse
    b'3',  # Violence
    b'4',  # Illegal goods and services
    b'5',  # Illegal adult content
    b'6',  # Personal data
    b'7',  # Scam or fraud
    b'8',  # Copyright
    b'9',  # Spam
    b'a',  # Other
]

API = [
    '24565698:5a084b434f8505ace703485b9da85040',
    '27904162:e7cba879b1c643ba77490bf328df5eab',
    '23037915:50f06f5b2223586fde0d1379ea91ebc7',
    '29512095:0b29a7d42fff002856b9bed64f7ec919',
    '25055016:25edf5b7becebe91a2d61fe8d9d9931b',
    '21156147:90408de329b27f7dd411dff3e601acc6',
    '29840977:e20b6a9fd01cc9055de0a88a183a030b',
    '29412963:3e37e1d05422db9426aa85e617b441ea',
    '23140129:431e5e839aecf4abdce22d7663acffa7'
]

reasons_texts = [
    "Прошу заблокировать этого пользователя за нарушения.",
    "Заблокируйте, пожалуйста, этого пользователя. Он нарушает правила.",
    "Необходимо заблокировать данного пользователя.",
    "Этот пользователь должен быть заблокирован из-за нарушений.",
    "Просьба заблокировать аккаунт этого пользователя.",
    "Я прошу заблокировать этого пользователя в связи с нарушениями.",
    "Заблокируйте, пожалуйста, этого пользователя за нарушение правил.",
    "Этот пользователь явно нарушает правила, его нужно заблокировать.",
    "Пожалуйста, заблокируйте этого пользователя.",
    "Требую блокировки этого пользователя за нарушения.",
    "Заблокируйте этого пользователя за его действия.",
    "Считаю необходимым заблокировать этого пользователя.",
    "Этот пользователь не соблюдает правила, нужна блокировка.",
    "Заблокируйте, пожалуйста, пользователя, который нарушил правила.",
    "Прошу принять меры и заблокировать этого пользователя.",
    "Заблокируйте данного пользователя, он нарушает порядок.",
    "Этот аккаунт следует заблокировать за нарушения.",
    "Необходимо заблокировать этого пользователя за несоблюдение правил.",
    "Я настаиваю на блокировке этого пользователя.",
    "Прошу вас заблокировать этого пользователя за его поведение.",
    "Этот пользователь должен быть заблокирован немедленно.",
    "Прошу заблокировать этого пользователя, он нарушил правила.",
    "Нужно заблокировать этого пользователя.",
    "Данный пользователь заслуживает блокировки.",
    "Заблокируйте, пожалуйста, этого пользователя за нарушение.",
    "Этот пользователь ведет себя недопустимо, его надо заблокировать.",
    "Просьба о блокировке этого пользователя в связи с нарушениями.",
    "Этот пользователь явно не соблюдает правила, нужна блокировка.",
    "Пользователя нужно заблокировать, он нарушил порядок.",
    "Я прошу принять меры и заблокировать этого пользователя.",
    "Заблокируйте, пожалуйста, аккаунт данного пользователя.",
    "Необходимо заблокировать этого пользователя в связи с нарушениями.",
    "Этот пользователь должен быть заблокирован за свои действия.",
    "Прошу заблокировать этого пользователя за его поведение.",
    "Заблокируйте этого пользователя, он нарушает правила сообщества.",
    "Считаю, что этого пользователя нужно заблокировать.",
    "Этот пользователь заслужил блокировку.",
    "Пожалуйста, заблокируйте этого пользователя.",
    "Прошу заблокировать этого пользователя в кратчайшие сроки.",
    "Пользователь явно нарушает правила, нужна блокировка.",
    "Требую заблокировать этого пользователя немедленно.",
    "Просьба заблокировать пользователя, нарушившего правила.",
    "Этот пользователь нуждается в блокировке за свои нарушения.",
    "Заблокируйте этого пользователя за некорректное поведение.",
    "Прошу заблокировать этого пользователя из-за нарушения.",
    "Этот пользователь не соблюдает правила, заблокируйте его.",
    "Необходимо принять меры и заблокировать этого пользователя.",
    "Я прошу вас заблокировать этого пользователя.",
    "Заблокируйте, пожалуйста, данного пользователя.",
    "Этот пользователь должен быть заблокирован за нарушения.",
    "Прошу заблокировать пользователя за нарушение правил.",
    "Прошу заблокировать пользователя за нарушение правил.",
    "Пользователь нарушает правила. Прошу принять меры.",
    "Прошу о блокировке аккаунта за неоднократные нарушения.",
    "Пользователь ведет себя неподобающе. Прошу заблокировать.",
    "Прошу заблокировать за нарушения в чате.",
    "Пользователь нарушает правила сообщества. Прошу о блокировке.",
    "Прошу принять меры против пользователя за нарушения.",
    "Пользователь не соблюдает правила. Прошу заблокировать.",
    "Прошу о блокировке аккаунта за неподобающее поведение.",
    "Пользователь нарушает правила. Прошу заблокировать его.",
    "Прошу заблокировать за неоднократные нарушения.",
    "Пользователь ведет себя агрессивно. Прошу о блокировке.",
    "Прошу о блокировке пользователя за нарушения.",
    "Пользователь создает проблемы в чате. Прошу заблокировать.",
    "Прошу принять меры против пользователя.",
    "Пользователь нарушает правила общения. Прошу о блокировке.",
    "Прошу заблокировать за неподобающее поведение.",
    "Пользователь не соблюдает правила. Прошу принять меры.",
    "Прошу о блокировке аккаунта за нарушения.",
    "Пользователь ведет себя неуместно. Прошу заблокировать.",
    "Прошу заблокировать за нарушения в группе.",
    "Пользователь создает негативную атмосферу. Прошу о блокировке.",
    "Прошу о блокировке пользователя за неподобающее поведение.",
    "Пользователь нарушает правила. Прошу принять меры.",
    "Прошу заблокировать за неоднократные нарушения.",
    "Пользователь ведет себя неподобающе. Прошу о блокировке.",
    "Прошу о блокировке аккаунта за нарушения.",
    "Пользователь создает проблемы в чате. Прошу заблокировать.",
    "Прошу принять меры против пользователя за нарушения.",
    "Пользователь нарушает правила общения. Прошу о блокировке.",
    "Прошу заблокировать за неподобающее поведение.",
    "Пользователь не соблюдает правила. Прошу принять меры.",
    "Прошу о блокировке аккаунта за нарушения.",
    "Пользователь ведет себя агрессивно. Прошу о блокировке.",
    "Прошу о блокировке пользователя за нарушения.",
    "Пользователь создает негативную атмосферу. Прошу о блокировке.",
    "Прошу заблокировать за неподобающее поведение.",
    "Пользователь нарушает правила. Прошу принять меры.",
    "Прошу о блокировке аккаунта за неоднократные нарушения.",
    "Пользователь ведет себя неподобающе. Прошу о блокировке.",
    "Прошу о блокировке пользователя за нарушения.",
    "Пользователь создает проблемы в чате. Прошу заблокировать.",
    "Прошу принять меры против пользователя за нарушения.",
    "Пользователь нарушает правила общения. Прошу о блокировке.",
    "Прошу заблокировать за неподобающее поведение.",
    "Пользователь не соблюдает правила. Прошу принять меры.",
    "Прошу о блокировке аккаунта за нарушения.",
    "Пользователь ведет себя агрессивно. Прошу о блокировке.",
    "Прошу о блокировке пользователя за неподобающее поведение.",
    "Пользователь нарушает правила. Прошу заблокировать его.",
    "Please block this user for violations.",
    "Please block this user. He's breaking the rules.",
    "This user must be blocked.",
    "This user should be blocked due to violations.",
    "Please block this user's account.",
    "I ask you to block this user due to violations.",
    "Please block this user for violating the rules.",
    "This user is clearly violating the rules, and he needs to be blocked.",
    "Please block this user.",
    "I demand that this user be blocked for violations.",
    "Block this user for his actions.",
    "I consider it necessary to block this user.",
    "This user does not follow the rules, and they need to be blocked.",
    "Please block the user who violated the rules.",
    "Please take action and block this user.",
    "Block this user, he breaks the order.",
    "This account should be blocked for violations.",
    "It is necessary to block this user for non-compliance with the rules.",
    "I insist on blocking this user.",
    "I ask you to block this user for his behavior.",
    "This user should be blocked immediately.",
    "Please block this user, he violated the rules.",
    "You need to block this user.",
    "This user deserves to be blocked.",
    "Please block this user for violation.",
    "This user is behaving unacceptably, he should be blocked.",
    "Request to block this user due to violations.",
    "This user is clearly not following the rules, and they need to be blocked.",
    "The user needs to be blocked, he has violated the order.",
    "I ask you to take action and block this user.",
    "Please block this user's account.",
    "It is necessary to block this user due to violations.",
    "This user should be blocked for their actions.",
    "I ask you to block this user for his behavior.",
    "Block this user, he is violating the rules of the community.",
    "I think this user should be blocked.",
    "This user deserves to be blocked.",
    "Please block this user.",
    "Please block this user as soon as possible.",
    "The user is clearly violating the rules, and they need to be blocked.",
    "I demand to block this user immediately.",
    "Please block the user who violated the rules.",
    "This user needs to be blocked for his violations.",
    "Block this user for inappropriate behavior.",
    "Please block this user due to a violation.",
    "This user does not follow the rules, block him.",
    "It is necessary to take measures and block this user.",
    "I'm asking you to block this user.",
    "Please block this user.",
    "This user should be blocked for violations.",
    "I ask you to block the user for violating the rules."
]

bot = None  # инициализируется из main.py через set_bot()

def set_bot(b):
    global bot
    bot = b
session_folder = 'sessions'
os.makedirs(session_folder, exist_ok=True)
sessions = [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)

async def extract_username_and_message_id(message_url):
    # Убираем query string если есть
    message_url = message_url.split('?')[0].rstrip('/')
    path = message_url[len('https://t.me/'):].split('/')
    if len(path) == 2:
        # Обычный формат: t.me/username/123
        chat_username = path[0]
        message_id = int(path[1])
        return chat_username, message_id
    elif len(path) == 3:
        # Форум/тред: t.me/group/thread_id/message_id
        chat_username = path[0]
        message_id = int(path[2])
        return chat_username, message_id
    raise ValueError("Неверная ссылка!")

def format_log_line(session, message_url, status):
    now = datetime.now().strftime("%H:%M:%S")
    return f"[{now}] {session}.session -> {message_url} - [{status}]"

async def _report_one_session(session, chat_username, message_id, message_url, whitelist, target_ref):
    """
    Отправляет жалобу от одной сессии.
    target_ref — список [TARGET, target_username], общий для всех задач.
    Возвращает (status: str, flood_seconds: int | None)
    """
    random_api = random.choice(API)
    api_id, api_hash = random_api.split(":")
    random_reason = random.choice(reasons)
    random_reason_text = random.choice(reasons_texts)

    print(f"[BOTNET] [{session}] Подключаемся (api_id={api_id})...", flush=True)

    client = TelegramClient(
        f"./sessions/{session}", int(api_id), api_hash,
        system_version='4.16.30-vxCUSTOM'
    )
    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=3)
        except asyncio.TimeoutError:
            print(f"[BOTNET] [{session}] ❌ ОШИБКА СОЕДИНЕНИЯ (timeout)", flush=True)
            return "ОШИБКА СОЕДИНЕНИЯ", None

        if not await client.is_user_authorized():
            print(f"[BOTNET] [{session}] ❌ НЕВАЛИД (не авторизован)", flush=True)
            return "НЕВАЛИД", None

        await client.start()
        chat = await client.get_entity(chat_username)
        print(f"[BOTNET] [{session}] ✅ Подключён, чат получен: {chat_username}", flush=True)

        # Получаем TARGET только один раз (первая сессия, которая успела)
        if target_ref[0] is None:
            msg = await client.get_messages(chat, ids=message_id)
            if msg.from_id is not None:
                user_entity = await client.get_entity(msg.from_id)
                target_ref[0] = msg.from_id.user_id if isinstance(msg.from_id, PeerUser) else "?"
                target_ref[1] = user_entity.username or "Нет username"
                print(f"[BOTNET] [{session}] 🎯 Таргет определён: ID={target_ref[0]}, @{target_ref[1]}", flush=True)
                if target_ref[0] in whitelist:
                    print(f"[BOTNET] [{session}] 🍕 WHITELIST — таргет в белом списке", flush=True)
                    return "WHITELIST", None
            else:
                print(f"[BOTNET] [{session}] ⚠️ NO_ID — не удалось получить from_id сообщения", flush=True)
                return "NO_ID", None

        # Получаем список причин от сервера динамически (3-шаговый флоу)
        try:
            # Шаг 1: получаем категории
            print(f"[BOTNET] [{session}] 📤 Шаг 1: запрашиваем категории жалоб...", flush=True)
            r1 = await client(ReportRequest(peer=chat, id=[message_id], option=b'', message=''))
            if hasattr(r1, 'options') and r1.options:
                cat = random.choice(r1.options).option
                print(f"[BOTNET] [{session}] 📤 Шаг 2: выбрана категория {cat!r}", flush=True)
            else:
                cat = random_reason
                print(f"[BOTNET] [{session}] 📤 Шаг 2: категории не получены, используем fallback {cat!r}", flush=True)

            # Шаг 2: выбираем категорию — может вернуть подкатегории
            r2 = await client(ReportRequest(peer=chat, id=[message_id], option=cat, message=''))
            if hasattr(r2, 'options') and r2.options:
                sub = random.choice(r2.options).option
                print(f"[BOTNET] [{session}] 📤 Шаг 3: выбрана подкатегория {sub!r}, отправляем текст...", flush=True)
                # Шаг 3: выбираем подкатегорию и передаём текст
                await client(ReportRequest(peer=chat, id=[message_id], option=sub, message=random_reason_text))
            else:
                print(f"[BOTNET] [{session}] 📤 Шаг 3: подкатегорий нет, отправляем с текстом напрямую...", flush=True)
                # r2 уже ReportResultAddComment или Reported — отправляем с текстом
                await client(ReportRequest(peer=chat, id=[message_id], option=cat, message=random_reason_text))
        except Exception as report_err:
            # Fallback — просто отправляем с hardcoded option
            print(f"[BOTNET] [{session}] ⚠️ Ошибка в 3-шаговом флоу ({report_err!s:.60}), используем fallback...", flush=True)
            await client(ReportRequest(peer=chat, id=[message_id], option=random_reason, message=random_reason_text))

        await asyncio.sleep(random.uniform(0.05, 0.5))
        print(f"[BOTNET] [{session}] ✅ ДОСТАВЛЕНО", flush=True)
        return "ДОСТАВЛЕНО", None

    except FloodWaitError as e:
        print(f"[BOTNET] [{session}] 🌊 FLOOD — ждать {e.seconds}с", flush=True)
        return "FLOOD", e.seconds
    except Exception as e:
        if "Could not find" in str(e):
            print(f"[BOTNET] [{session}] ❌ NOT_FOUND — {e!s:.80}", flush=True)
            return "NOT_FOUND", None
        print(f"[BOTNET] [{session}] ❌ ОШИБКА — {e!s:.80}", flush=True)
        return f"ОШИБКА: {str(e)[:50]}", None
    finally:
        if client.is_connected():
            await client.disconnect()


async def main(chat_username, message_id, user, username, message_url):
    # Получаем вайтлист из PostgreSQL (db.py)
    try:
        import db as db_module
        whitelist = await db_module.get_whitelist()
    except Exception as e:
        print(f"[BOTNET] Ошибка получения вайтлиста: {e}", flush=True)
        whitelist = []

    if "_" in username:
        username = "None"

    print(f"\n{'='*50}", flush=True)
    print(f"[BOTNET] 🚀 Запуск ботнета", flush=True)
    print(f"[BOTNET] 👤 Пользователь: {user} (@{username})", flush=True)
    print(f"[BOTNET] 🔗 Ссылка: {message_url}", flush=True)
    print(f"[BOTNET] 📦 Сессий загружено: {len(sessions)}", flush=True)
    print(f"{'='*50}", flush=True)

    # Общий изменяемый объект для TARGET между параллельными задачами
    target_ref = [None, "Неизвестный пользователь"]

    # Запускаем все сессии параллельно
    tasks = [_report_one_session(s, chat_username, message_id, message_url, whitelist, target_ref) for s in sessions]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid, ne_valid, flood = 0, 0, 0
    log_lines = [
        "BreakRuin log | botnet-method",
        "-" * 42,
        f"Пользователь: {user} (@{username})",
        f"Ссылка: {message_url}",
        "-" * 42
    ]

    for session, result in zip(sessions, results):
        if isinstance(result, Exception):
            ne_valid += 1
            print(f"[BOTNET] [{session}] 💥 ИСКЛЮЧЕНИЕ: {str(result)[:80]}", flush=True)
            log_lines.append(format_log_line(session, message_url, f"ИСКЛЮЧЕНИЕ: {str(result)[:50]}"))
            continue

        status, flood_sec = result

        if status == "WHITELIST":
            print(f"[BOTNET] ⛔ Таргет в вайтлисте, прерываем", flush=True)
            await bot.send_message(user, "🍕 *Какая-то ошибка!*", parse_mode="Markdown", reply_markup=keyboards.main_menu)
            try:
                await bot.send_message(target_ref[0], f"🍕 *Попытка жалобы на* [сообщение]({message_url}) *от ID {user}!*", parse_mode="Markdown", disable_web_page_preview=True)
            except:
                pass
            return
        elif status == "NO_ID":
            print(f"[BOTNET] ⚠️ Не удалось получить ID пользователя", flush=True)
            await bot.send_message(user, "🍕 *Не удалось получить ID пользователя!*", parse_mode="Markdown", reply_markup=keyboards.main_menu)
            return
        elif status == "NOT_FOUND":
            print(f"[BOTNET] ❌ Не могу получить ID — NOT_FOUND", flush=True)
            await bot.send_message(user, "❌ *Не могу получить ID этого пользователя!*", parse_mode="Markdown", reply_markup=keyboards.main_menu)
            return
        elif status == "ДОСТАВЛЕНО":
            valid += 1
            log_lines.append(format_log_line(session, message_url, "ДОСТАВЛЕНО"))
        elif status == "FLOOD":
            flood += 1
            log_lines.append(format_log_line(session, message_url, f"FLOOD {flood_sec}s"))
        else:
            ne_valid += 1
            log_lines.append(format_log_line(session, message_url, status))

    TARGET = target_ref[0]
    target_username = target_ref[1]

    print(f"\n[BOTNET] {'='*50}", flush=True)
    print(f"[BOTNET] 🏁 Итоги:", flush=True)
    print(f"[BOTNET] 🎯 Таргет: ID={TARGET}, @{target_username}", flush=True)
    print(f"[BOTNET] ✅ Доставлено: {valid}", flush=True)
    print(f"[BOTNET] ❌ Не доставлено: {ne_valid}", flush=True)
    print(f"[BOTNET] 🌊 Флудов: {flood}", flush=True)
    print(f"[BOTNET] {'='*50}\n", flush=True)

    log_lines.append("-" * 42)
    log_lines.append("[TARGET]")
    log_lines.append(f"ID: {TARGET}")
    log_lines.append(f"USERNAME: @{target_username}")
    log_lines.append("-" * 42)
    log_lines.append(f"Успешно: {valid}")
    log_lines.append(f"Неуспешно: {ne_valid}")
    log_lines.append(f"Флудов: {flood}")

    log_name = f"breakruin_botnet_log_{os.urandom(10).hex()}.txt"
    log_path = os.path.join(LOG_FOLDER, log_name)

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    caption_user = (
        f"🍕 *Пицца доставлена!*\n"
        f"*└─📂 Пицца: обычная*\n\n"
        f"🟢 *Успешно отправлено: {valid}*\n"
        f"🔴 *Не удалось отправить: {ne_valid}*"
    )
    caption_log = (
        f"📈 *Бот завершил работу*\n* └─📂 Метод: B0tN3t-method*\n\n"
        f"🎯 *Таргет*\n*└─ ID: {TARGET}*\n*└─ USERNAME: @{target_username}*\n\n"
        f"🟢 *Успешно отправлено: {valid}*\n🔴 *Не удалось отправить: {ne_valid}*\n\n"
        f"⛓️‍💥 *Ссылка:* [тык]({message_url})\n👤 *Пользователь:* {user} (@{username})"
    )

    try:
        await bot.send_document(user, types.InputFile(log_path), caption=caption_user, parse_mode="Markdown", reply_markup=keyboards.main_menu)
        await bot.send_document(bot_logs, types.InputFile(log_path), caption=caption_log, parse_mode="Markdown")
    except Exception as e:
        print(f"Ошибка при отправке логов: {e}")

    try:
        os.remove(log_path)
    except Exception as e:
        print(f"Не удалось удалить лог: {e}")
