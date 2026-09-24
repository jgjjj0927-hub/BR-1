"""
Brown V2 | aureport_snos.py
AU Report метод — жалобы через @AuReportBot.
Сессии берутся из папки aureport_sessions/
Прокси берутся из proxies.txt (если есть).
"""

import asyncio
import json
import logging
import os
import random
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonCallback
import config
from config import bot_logs
from utils import now_msk, ProgressBar, esc_md
from aiogram import Bot, types
import keyboards

logger = logging.getLogger(__name__)

AUREPORT_DIR = "aureport_sessions"
os.makedirs(AUREPORT_DIR, exist_ok=True)

MAIL_DOMAIN = "br-v2.com"
CODES_DIR = "/tmp/mailcodes"
os.makedirs(CODES_DIR, exist_ok=True)


async def _wait_for_code_file(session_email: str, timeout: int = 60) -> str | None:
    """Poll /tmp/mailcodes/<email> until mailpipe.py writes a fresh code or timeout."""
    fname = session_email.replace("@", "_at_").replace("/", "_")
    code_file = os.path.join(CODES_DIR, fname)
    # Remove stale file before waiting
    try:
        os.remove(code_file)
    except FileNotFoundError:
        pass
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if os.path.exists(code_file):
            try:
                with open(code_file) as f:
                    data = json.load(f)
                os.remove(code_file)
                return data["code"]
            except Exception:
                pass
        await asyncio.sleep(1)
    return None

bot = None
main_bot = None

def set_bot_aureport(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)


def _get_sessions():
    files = [f for f in os.listdir(AUREPORT_DIR) if f.endswith(".session")]
    return [os.path.join(AUREPORT_DIR, f.replace(".session", "")) for f in files]


def _load_proxies():
    proxies = []
    for fname in ["proxies.txt", "proxy_input.txt"]:
        if os.path.exists(fname):
            with open(fname, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and ":" in line:
                        proxies.append(line)
            break
    return proxies


def _parse_proxy(proxy_str):
    """Парсит строку proxy в формат Telethon: (type, host, port, True, user, pass)"""
    try:
        import socks
        proxy_str = proxy_str.replace("socks5://", "").replace("http://", "")
        if "@" in proxy_str:
            auth, hostport = proxy_str.rsplit("@", 1)
            user, password = auth.split(":", 1)
            host, port = hostport.rsplit(":", 1)
        else:
            parts = proxy_str.split(":")
            if len(parts) == 4:
                host, port, user, password = parts
            else:
                host, port = parts[0], parts[1]
                user, password = None, None
        if user and password:
            return (socks.SOCKS5, host, int(port), True, user, password)
        return (socks.SOCKS5, host, int(port))
    except Exception:
        return None


async def _create_client(session_path: str, proxy=None):
    try:
        api_id = int(config.AUREPORT_API_ID)
        api_hash = config.AUREPORT_API_HASH
        client = TelegramClient(session_path, api_id, api_hash, proxy=proxy,
                                system_version='4.16.30-vxCUSTOM')
        connected = False
        for _a in range(3):
            try:
                await asyncio.wait_for(client.connect(), timeout=12)
                connected = True
                break
            except (asyncio.TimeoutError, OSError):
                if _a == 2:
                    return None
                await asyncio.sleep(1)
        if not connected:
            return None
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        return client
    except Exception as e:
        logger.warning(f"[AUREPORT] Ошибка подключения {session_path}: {e}")
        return None


async def _send_one_report(client, bot_entity, session_email: str, target: str, report_num: int) -> bool:
    done = asyncio.Event()
    step = 0
    success = False
    session_name = os.path.basename(client.session.filename)

    @client.on(events.NewMessage(from_users=bot_entity.id))
    async def handler(event):
        nonlocal step, success
        text = event.message.message.strip().lower()
        markup = event.message.reply_markup

        if "please enter a t.me" in text and step == 0:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, target)
            step = 1
            logger.info(f"[AUREPORT] [{session_name}] [{report_num}] Ссылка отправлена")

        elif "select the reason" in text and step == 1:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, "Drug-related material")
            step = 2
            logger.info(f"[AUREPORT] [{session_name}] [{report_num}] Причина отправлена")

        elif "why the content is illegal" in text and step == 2:
            await asyncio.sleep(0.3)
            await client.send_message(
                bot_entity,
                "This account facilitates the active sale and distribution of illegal narcotics."
            )
            step = 3
            logger.info(f"[AUREPORT] [{session_name}] [{report_num}] Описание отправлено")

        elif "documentation" in text and step == 3:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, "Proceed without documentation")
            step = 4
            logger.info(f"[AUREPORT] [{session_name}] [{report_num}] Документация пропущена")

        elif "by submitting this report" in text and step == 4:
            await asyncio.sleep(0.3)
            if markup and markup.rows:
                for row in markup.rows:
                    for btn in row.buttons:
                        if "confirm" in btn.text.lower():
                            if isinstance(btn, KeyboardButtonCallback):
                                await client.request(btn.click(bot_entity))
                                step = 5
                                logger.info(f"[AUREPORT] [{session_name}] [{report_num}] Подтверждено (кнопка)")
                                return
            await client.send_message(bot_entity, "Confirm")
            step = 5
            logger.info(f"[AUREPORT] [{session_name}] [{report_num}] Подтверждено (текст)")

        elif "please enter your email" in text and step == 5:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, session_email)
            step = 6
            logger.info(f"[AUREPORT] [{session_name}] [{report_num}] Email отправлен ({session_email}), жду код...")

        elif ("sent a" in text and "code" in text or "verification code" in text) and step == 6:
            code = await _wait_for_code_file(session_email, timeout=60)
            if code:
                await asyncio.sleep(0.5)
                await client.send_message(bot_entity, code)
                step = 7
                logger.info(f"[AUREPORT] [{session_name}] [{report_num}] Код отправлен: {code}")
            else:
                logger.warning(f"[AUREPORT] [{session_name}] [{report_num}] ⏳ Код не пришёл за 60с")
                done.set()

        elif "thank you for your report" in text or "report has been submitted" in text or "report received" in text:
            success = True
            done.set()
            logger.info(f"[AUREPORT] [{session_name}] [{report_num}] ✅ Успешно!")

        elif ("invalid" in text or "not found" in text or "incorrect" in text or "expired" in text) and step >= 5:
            logger.warning(f"[AUREPORT] [{session_name}] [{report_num}] ❌ Ошибка верификации")
            done.set()
        elif "invalid" in text or "not found" in text:
            logger.warning(f"[AUREPORT] [{session_name}] [{report_num}] ❌ Ошибка от бота")
            done.set()

    await client.send_message(bot_entity, "/start")
    logger.info(f"[AUREPORT] [{session_name}] [{report_num}] /start отправлен")

    try:
        await asyncio.wait_for(done.wait(), timeout=120)
    except asyncio.TimeoutError:
        logger.warning(f"[AUREPORT] [{session_name}] [{report_num}] ⏳ Таймаут")

    client.remove_event_handler(handler)
    return success


async def _single_session_flow(session_path: str, target: str, session_email: str, proxy=None) -> bool:
    session_name = os.path.basename(session_path)
    client = await _create_client(session_path, proxy)
    if not client:
        return False

    try:
        bot_entity = await client.get_entity("AuReportBot")
        logger.info(f"[AUREPORT] [{session_name}] Бот найден | email: {session_email}")

        success1 = await _send_one_report(client, bot_entity, session_email, target, 1)

        return success1
    except Exception as e:
        logger.error(f"[AUREPORT] [{session_name}] Ошибка: {e}")
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main_aureport(target_link: str, user: int, username: str, silent: bool = False, notify_bot=None):
    _notify = notify_bot or bot
    sessions = _get_sessions()
    if not sessions:
        await _notify.send_message(user,
            "❌ *Нет сессий для AU Report!*\n*Положи .session файлы в папку* aureport_sessions/",
            parse_mode="Markdown", reply_markup=keyboards.main_menu)
        return

    # Нормализуем target
    target = target_link.strip()
    if target.startswith("@"):
        target = f"t.me/{target[1:]}"
    elif target.startswith("https://t.me/"):
        target = target[len("https://"):]
    elif target.startswith("http://t.me/"):
        target = target[len("http://"):]
    elif not target.startswith("t.me/"):
        target = f"t.me/{target}"

    proxies = _load_proxies()
    total = len(sessions)

    logger.info(f"[AUREPORT] 🚀 Запуск | Цель: {target} | Сессий: {total} | Прокси: {len(proxies)}")

    pb = ProgressBar(_notify, user, total=total, title="🔍 *AU Report*", silent=silent)
    await pb.start()
    done_ref = [0]
    _sem = asyncio.Semaphore(10)

    async def _run(i, session_path):
        async with _sem:
            proxy = _parse_proxy(proxies[i % len(proxies)]) if proxies else None
            session_email = f"s{i:03d}@{MAIL_DOMAIN}"
            result = await _single_session_flow(session_path, target, session_email, proxy)
            done_ref[0] += 1
            await pb.update(done_ref[0])
            return result

    results = await asyncio.gather(*[_run(i, s) for i, s in enumerate(sessions)], return_exceptions=True)
    await pb.finish()
    successful = sum(1 for r in results if r is True)

    logger.info(f"[AUREPORT] 🏁 Итог: {successful}/{total}")

    now_str = now_msk().strftime("%d.%m.%Y %H:%M:%S")

    target_escaped = target.replace('_', '\\_')
    caption_user = (
        f"🇦🇺 *AU Report завершён!*\n\n"
        f"🎯 *Цель:* {target_escaped}\n"
        f"🕐 *Время:* {now_str}\n\n"
        f"🟢 *Успешно: {successful}*\n"
        f"🔴 *Не удалось: {total - successful}*"
    )
    try:
        import db as _db_mod
        _is_hid = await _db_mod.get_is_hidden(user)
        _log_uid = "скрыт" if _is_hid else str(user)
        _log_uname = "скрыт" if _is_hid else username
    except Exception:
        _log_uid, _log_uname = str(user), username

    caption_log = (
        f"🇦🇺 *AU Report*\n\n"
        f"🎯 *Цель:* {target_escaped}\n"
        f"👤 *Пользователь:* {_log_uid} (*@{_log_uname}*)\n"
        f"🕐 *Время:* {now_str}\n\n"
        f"🟢 *Успешно: {successful}*\n"
        f"🔴 *Не удалось: {total - successful}*"
    )

    if not silent:
        try:
            await _notify.send_message(user, caption_user, parse_mode="Markdown", reply_markup=keyboards.main_menu)
        except Exception as e:
            logger.error(f"[AUREPORT] Ошибка отправки результата пользователю: {e}")

        for attempt in range(3):
            try:
                _log_bot = main_bot or bot
                if _log_bot:
                    await _log_bot.send_message(bot_logs, caption_log, parse_mode="Markdown")
                    break
            except Exception as e:
                logger.error(f"[AUREPORT] Ошибка отправки лога (попытка {attempt+1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(2)

    return (successful, total)
