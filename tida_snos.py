"""
Brown V2 | tida_snos.py
TIDA метод — жалобы через @TIDABOT.
Сессии берутся из папки tida_sessions/
Прокси обязательны — берутся из config.TIDA_PROXY (env) или proxies.txt.
"""

import asyncio
import logging
import os
import socks
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonCallback
import config
from config import bot_logs
from aiogram import Bot, types
import keyboards
from utils import now_msk

logger = logging.getLogger(__name__)

TIDA_DIR = "tida_sessions"
os.makedirs(TIDA_DIR, exist_ok=True)

bot = None
main_bot = None

def set_bot_tida(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)


def _get_sessions():
    files = [f for f in os.listdir(TIDA_DIR) if f.endswith(".session")]
    return [os.path.join(TIDA_DIR, f.replace(".session", "")) for f in files]


def _get_proxy():
    """Возвращает прокси для TIDA из env или proxies.txt."""
    # Приоритет 1: env переменные
    host = os.environ.get("TIDA_PROXY_HOST", "")
    port = os.environ.get("TIDA_PROXY_PORT", "")
    user = os.environ.get("TIDA_PROXY_USER", "")
    password = os.environ.get("TIDA_PROXY_PASS", "")

    if host and port:
        if user and password:
            return (socks.SOCKS5, host, int(port), True, user, password)
        return (socks.SOCKS5, host, int(port))

    # Приоритет 2: proxies.txt
    for fname in ["proxies.txt", "proxy_input.txt"]:
        if os.path.exists(fname):
            with open(fname, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or ":" not in line:
                        continue
                    if line.startswith("http://"):
                        continue  # HTTP не поддерживается Telethon
                    try:
                        line = line.replace("socks5://", "").replace("socks4://", "")
                        if "@" in line:
                            auth, hostport = line.split("@")
                            u, p = auth.split(":")
                            h, pt = hostport.split(":")
                        else:
                            parts = line.split(":")
                            if len(parts) == 4:
                                h, pt, u, p = parts
                            elif len(parts) == 2:
                                h, pt = parts[0], parts[1]
                                u, p = None, None
                            else:
                                continue
                        if u and p:
                            return (socks.SOCKS5, h, int(pt), True, u, p)
                        return (socks.SOCKS5, h, int(pt))
                    except Exception:
                        continue
            break  # нашли файл — дальше не ищем

    return None


async def _create_client(session_path: str, proxy=None):
    try:
        api_id = int(config.TIDA_API_ID)
        api_hash = config.TIDA_API_HASH
        client = TelegramClient(session_path, api_id, api_hash, proxy=proxy,
                                system_version='4.16.30-vxCUSTOM')
        await asyncio.wait_for(client.connect(), timeout=15)
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        return client
    except Exception as e:
        logger.warning(f"[TIDA] Ошибка подключения {session_path}: {e}")
        return None


async def _send_one_report(client, bot_entity, target: str, custom_text: str, report_num: int) -> bool:
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
            logger.info(f"[TIDA] [{session_name}] [{report_num}] Ссылка отправлена")

        elif "select the reason" in text and step == 1:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, "Non-consensual intimate image sharing")
            step = 2
            logger.info(f"[TIDA] [{session_name}] [{report_num}] Причина отправлена")

        elif "why the content is illegal" in text and step == 2:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, custom_text)
            step = 3
            logger.info(f"[TIDA] [{session_name}] [{report_num}] Описание отправлено")

        elif "documentation" in text and step == 3:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, "Proceed without documentation")
            step = 4
            logger.info(f"[TIDA] [{session_name}] [{report_num}] Документация пропущена")

        elif "by submitting this report" in text and step == 4:
            await asyncio.sleep(0.3)
            if markup and markup.rows:
                for row in markup.rows:
                    for btn in row.buttons:
                        if "confirm" in btn.text.lower():
                            if isinstance(btn, KeyboardButtonCallback):
                                await client.request(btn.click(bot_entity))
                                step = 5
                                logger.info(f"[TIDA] [{session_name}] [{report_num}] Подтверждено (кнопка)")
                                return
            await client.send_message(bot_entity, "Confirm")
            step = 5
            logger.info(f"[TIDA] [{session_name}] [{report_num}] Подтверждено (текст)")

        elif "thank you for your report" in text:
            success = True
            done.set()
            logger.info(f"[TIDA] [{session_name}] [{report_num}] ✅ Успешно!")

        elif "invalid" in text or "not found" in text:
            logger.warning(f"[TIDA] [{session_name}] [{report_num}] ❌ Ошибка от бота")
            done.set()

    await client.send_message(bot_entity, "/start")
    logger.info(f"[TIDA] [{session_name}] [{report_num}] /start отправлен")

    try:
        await asyncio.wait_for(done.wait(), timeout=30)
    except asyncio.TimeoutError:
        logger.warning(f"[TIDA] [{session_name}] [{report_num}] ⏳ Таймаут")

    client.remove_event_handler(handler)
    return success


async def _single_session_flow(session_path: str, target: str, custom_text: str, proxy=None) -> bool:
    session_name = os.path.basename(session_path)
    client = await _create_client(session_path, proxy)
    if not client:
        return False

    try:
        bot_entity = await client.get_entity("TIDABOT")
        logger.info(f"[TIDA] [{session_name}] Бот найден")

        success = await _send_one_report(client, bot_entity, target, custom_text, 1)
        return success
    except Exception as e:
        logger.error(f"[TIDA] [{session_name}] Ошибка: {e}")
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main_tida(target_link: str, custom_text: str, user: int, username: str):
    sessions = _get_sessions()
    if not sessions:
        await bot.send_message(user,
            "❌ *Нет сессий для TIDA!*\n*Положи .session файлы в папку* `tida_sessions/`",
            parse_mode="Markdown", reply_markup=keyboards.main_menu)
        return

    # Нормализуем target
    target = target_link.strip()
    if target.startswith("@"):
        target = f"t.me/{target[1:]}"
    elif not target.startswith("t.me/") and not target.startswith("https://t.me/"):
        target = f"t.me/{target}"
    target = target.replace("https://", "")

    proxy = _get_proxy()
    if not proxy:
        await bot.send_message(user,
            "⚠️ *TIDA работает без прокси — это может не сработать.*\n*Рекомендуется добавить SOCKS5 прокси.*",
            parse_mode="Markdown")

    successful = 0
    total = len(sessions)

    logger.info(f"[TIDA] 🚀 Запуск | Цель: {target} | Сессий: {total} | Прокси: {'есть' if proxy else 'нет'}")

    results = await asyncio.gather(*[_single_session_flow(s, target, custom_text, proxy) for s in sessions], return_exceptions=True)
    successful = sum(1 for r in results if r is True)

    logger.info(f"[TIDA] 🏁 Итог: {successful}/{total}")

    now_str = now_msk().strftime("%d.%m.%Y %H:%M:%S")

    target_escaped = target.replace('_', '\\_')
    caption_user = (
        f"🟣 *TIDA завершён!*\n\n"
        f"🎯 *Цель:* {target_escaped}\n"
        f"🕐 *Время:* {now_str}\n\n"
        f"🟢 *Успешно: {successful}*\n"
        f"🔴 *Не удалось: {total - successful}*"
    )
    caption_log = (
        f"🟣 *TIDA*\n\n"
        f"🎯 *Цель:* {target_escaped}\n"
        f"🗒️ *Текст:* {custom_text[:100]}{'...' if len(custom_text) > 100 else ''}\n"
        f"👤 *Пользователь:* {user} (@{username})\n"
        f"🕐 *Время:* {now_str}\n\n"
        f"🟢 *Успешно: {successful}*\n"
        f"🔴 *Не удалось: {total - successful}*"
    )

    try:
        await bot.send_message(user, caption_user, parse_mode="Markdown", reply_markup=keyboards.main_menu)
    except Exception as e:
        logger.error(f"[TIDA] Ошибка отправки результата пользователю: {e}")

    try:
        await main_bot.send_message(bot_logs, caption_log, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"[TIDA] Ошибка отправки лога: {e}")
