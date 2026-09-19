"""
Brown V2 | tida_snos.py
TIDA метод — жалобы через @TIDABOT.
Сессии берутся из папки tida_sessions/
Прокси обязательны — берутся из config.TIDA_PROXY (env) или proxies.txt.
"""

import asyncio
import logging
import os
import random
import socks
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonCallback
import config
from config import bot_logs
from aiogram import Bot, types
import keyboards
from utils import now_msk, ProgressBar

logger = logging.getLogger(__name__)

GROQ_KEY = os.environ.get("GROQ_KEY", config.GROQ_KEY)

TARGET_LABELS = {
    "account": "user account",
    "bot": "bot",
    "chat": "group chat",
    "channel": "channel",
}

TIDA_SYSTEM_PROMPT = """You are a TIDA report text generator for Telegram's @TIDABOT reporting system.
Generate a formal complaint text in English. Maximum 350 characters total. Do not exceed this limit.
Rules:
- Professional and legal tone
- Reference TIDA/Telegram framework rules relevant to the violation:
  * Personal data / doxxing → Telegram ToS §4 (Privacy), TIDA Privacy Violation category
  * CSAM / child content → Telegram ToS §4 (CSAM), TIDA Child Safety category, UN CRC Art.34
  * Non-consensual intimate images → Telegram ToS §4 (NCII), TIDA Non-Consensual Intimate Images category
  * Illegal goods / drugs → Telegram ToS §4 (Illegal Activities), TIDA Illegal Goods category
  * Violence / terrorism → Telegram ToS §4 (Violence), TIDA Violent Speech category
  * Spam / fraud → Telegram ToS §4 (Spam), TIDA Spam & Scam category
  * Other violations → Telegram ToS (telegram.org/tos), TIDA Other category
- The final sentence MUST say "Requesting permanent {action} of this {target}." where {target} is provided
- Do NOT mention URLs or usernames
- Use ONLY facts from the provided content or description
- Output ONLY the complaint text, nothing else"""


def _classify_violation(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ['csam', 'child', 'minor', 'младенц', 'ребен', 'дет', 'несовершеннолет']):
        return "Child sexual abuse material (CSAM) — explicit sexual content involving minors"
    if any(k in t for k in ['наркот', 'drug', 'мефедрон', 'амфет', 'героин', 'кокаин', 'марихуан', 'закладк']):
        return "Illegal drug distribution and narcotics sales"
    if any(k in t for k in ['пробив', 'доксинг', 'dox', 'личные данные', 'персональн']):
        return "Doxxing and illegal personal data trading"
    if any(k in t for k in ['скам', 'мошен', 'fraud', 'scam', 'развод']):
        return "Fraud and scam activity"
    if any(k in t for k in ['террор', 'экстремизм', 'взрыв', 'убийств', 'насили']):
        return "Terrorism, extremism and violent content"
    if any(k in t for k in ['спам', 'spam', 'реклам']):
        return "Spam and unsolicited advertising"
    return "Systematic violation of Telegram Terms of Service"


async def generate_tida_text(content: str, target_type: str, is_description: bool = False) -> str:
    """Генерирует текст жалобы через Groq для TIDA."""
    target_label = TARGET_LABELS.get(target_type, "resource")
    action = "suspension" if target_type in ("account", "bot") else "removal"

    system = TIDA_SYSTEM_PROMPT.replace("{action}", action).replace("{target}", target_label)

    # Не слать сырое описание — только абстрактную категорию нарушения
    violation_category = _classify_violation(content)
    user_content = f"Violation category: {violation_category}\nTarget type: {target_label}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content}
                    ],
                    "max_tokens": 200,
                    "temperature": 0.7,
                    "reasoning_effort": "low",
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json(content_type=None)
                if "choices" not in data:
                    logger.error(f"[TIDA-AI] Groq error: {data}")
                    return ""
                msg = data["choices"][0]["message"]
                import re
                text = msg.get("content", "").strip()
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                return text[:350]
    except Exception as e:
        logger.error(f"[TIDA-AI] Groq error: {e}")
        return ""


async def analyze_tida_link(link: str) -> dict:
    """
    Анализирует ссылку и возвращает:
    {
        target_type: "channel"|"chat"|"bot"|"account",
        has_message_id: bool,
        message_id: int|None,
        username: str,
        is_public: bool,
        message_text: str,  # если публичная + есть msg_id
    }
    """
    result = {
        "target_type": "channel",
        "has_message_id": False,
        "message_id": None,
        "username": link,
        "is_public": False,
        "message_text": "",
    }

    # Нормализуем ссылку
    clean = link.strip()
    is_private = False

    if "joinchat" in clean or "+A" in clean or (clean.startswith("https://t.me/+") or clean.startswith("t.me/+")):
        is_private = True
        result["is_public"] = False
        result["target_type"] = "chat"
        return result

    # Парсим username и message_id
    for prefix in ["https://t.me/", "http://t.me/", "t.me/"]:
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break
    if clean.startswith("@"):
        clean = clean[1:]

    parts = clean.rstrip("/").split("?")[0].split("/")
    username = parts[0]
    result["username"] = username

    if len(parts) >= 2 and parts[-1].isdigit():
        result["has_message_id"] = True
        result["message_id"] = int(parts[-1])

    # Пробуем получить entity через Telethon
    try:
        import os as _os
        session_folder = "sessions"
        sessions = [f.replace(".session", "") for f in _os.listdir(session_folder)
                    if f.endswith(".session")] if _os.path.exists(session_folder) else []
        if not sessions:
            result["is_public"] = False
            return result

        session_path = _os.path.join(session_folder, random.choice(sessions))
        client = TelegramClient(session_path, int(config.TIDA_API_ID), config.TIDA_API_HASH,
                                system_version="4.16.30-vxCUSTOM")
        for _a in range(3):
            try:
                await asyncio.wait_for(client.connect(), timeout=12)
                break
            except (asyncio.TimeoutError, OSError):
                if _a == 2:
                    return result
                await asyncio.sleep(1)
        if not await client.is_user_authorized():
            await client.disconnect()
            return result

        try:
            entity = await client.get_entity(username)
            from telethon.tl.types import (Channel, Chat, User,
                                            InputPeerChannel, InputPeerChat)

            if hasattr(entity, 'megagroup') and entity.megagroup:
                result["target_type"] = "chat"
            elif isinstance(entity, Channel):
                result["target_type"] = "channel"
            elif isinstance(entity, User):
                result["target_type"] = "bot" if entity.bot else "account"
            elif isinstance(entity, Chat):
                result["target_type"] = "chat"

            result["is_public"] = True

            # Если есть message_id — читаем текст сообщения
            if result["has_message_id"] and result["message_id"]:
                try:
                    msg = await client.get_messages(entity, ids=result["message_id"])
                    if msg:
                        result["message_text"] = (msg.text or msg.caption or "")[:500]
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"[TIDA-AI] get_entity error: {e}")
            result["is_public"] = False

        await client.disconnect()
    except Exception as e:
        logger.warning(f"[TIDA-AI] analyze error: {e}")

    # Если entity-lookup не удался и тип остался "channel" —
    # для голого юзернейма (без message_id, не joinchat) ставим "account"
    if result["target_type"] == "channel" and not result["has_message_id"] and not is_private:
        result["target_type"] = "account"

    return result


async def fetch_tida_message_text(link: str) -> str:
    """Получает текст сообщения по публичной ссылке."""
    try:
        clean = link.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
        parts = clean.rstrip("/").split("/")
        if len(parts) < 2:
            return ""
        username = parts[0]
        msg_id = int(parts[-1])

        session_folder = "sessions"
        import os as _os
        sessions = [f.replace(".session", "") for f in _os.listdir(session_folder)
                    if f.endswith(".session")] if _os.path.exists(session_folder) else []
        if not sessions:
            return ""

        session_path = _os.path.join(session_folder, random.choice(sessions))
        client = TelegramClient(session_path, int(config.TIDA_API_ID), config.TIDA_API_HASH,
                                system_version="4.16.30-vxCUSTOM")
        for _a in range(3):
            try:
                await asyncio.wait_for(client.connect(), timeout=12)
                break
            except (asyncio.TimeoutError, OSError):
                if _a == 2:
                    return ""
                await asyncio.sleep(1)
        if not await client.is_user_authorized():
            await client.disconnect()
            return ""
        msg = await client.get_messages(username, ids=msg_id)
        text = ""
        if msg:
            text = msg.text or msg.caption or ""
        await client.disconnect()
        logger.info(f"[TIDA-AI] получен текст: {text[:80]}")
        return text[:500]
    except Exception as e:
        logger.warning(f"[TIDA-AI] fetch error: {e}")
        return ""

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


def _parse_proxy_str(line: str):
    """Парсит строку прокси в tuple для Telethon. Возвращает tuple или None."""
    try:
        line = line.strip()
        if not line or line.startswith("http://"):
            return None
        line = line.replace("socks5://", "").replace("socks4://", "")
        if "@" in line:
            auth, hostport = line.rsplit("@", 1)
            u, p = auth.split(":", 1)
            h, pt = hostport.rsplit(":", 1)
            return (socks.SOCKS5, h, int(pt), True, u, p)
        else:
            parts = line.split(":")
            if len(parts) == 4:
                h, pt, u, p = parts
                return (socks.SOCKS5, h, int(pt), True, u, p)
            elif len(parts) == 2:
                h, pt = parts
                return (socks.SOCKS5, h, int(pt))
    except Exception:
        pass
    return None


def _get_all_proxies() -> list:
    """Возвращает список всех прокси для TIDA."""
    # Приоритет 1: env переменные (один прокси)
    host = os.environ.get("TIDA_PROXY_HOST", "")
    port = os.environ.get("TIDA_PROXY_PORT", "")
    user = os.environ.get("TIDA_PROXY_USER", "")
    password = os.environ.get("TIDA_PROXY_PASS", "")

    if host and port:
        if user and password:
            return [(socks.SOCKS5, host, int(port), True, user, password)]
        return [(socks.SOCKS5, host, int(port))]

    # Приоритет 2: proxies.txt / proxy_input.txt
    for fname in ["proxies.txt", "proxy_input.txt"]:
        if os.path.exists(fname):
            with open(fname, "r") as f:
                result = []
                for line in f:
                    p = _parse_proxy_str(line)
                    if p:
                        result.append(p)
            if result:
                return result
            break

    return []


def _get_proxy():
    """Возвращает один прокси (обратная совместимость)."""
    proxies = _get_all_proxies()
    return proxies[0] if proxies else None




async def _create_client(session_path: str, proxy=None):
    try:
        api_id = int(config.TIDA_API_ID)
        api_hash = config.TIDA_API_HASH
        client = TelegramClient(session_path, api_id, api_hash, proxy=proxy,
                                system_version='4.16.30-vxCUSTOM')
        connected = False
        for db_attempt in range(3):
            try:
                await asyncio.wait_for(client.connect(), timeout=15)
                connected = True
                break
            except (asyncio.TimeoutError, OSError):
                if db_attempt == 2:
                    logger.warning(f"[TIDA] Таймаут подключения {session_path}")
                    return None
                await asyncio.sleep(1)
            except Exception as e:
                if "database is locked" in str(e) and db_attempt < 2:
                    await asyncio.sleep(random.uniform(1, 2))
                else:
                    raise
        if not connected:
            return None
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        return client
    except Exception as e:
        logger.warning(f"[TIDA] Ошибка подключения {session_path}: {e}")
        return None


async def _send_one_report(client, bot_entity, target: str, custom_text: str, report_num: int) -> tuple[bool, bool]:
    """Возвращает (success, region_blocked)."""
    done = asyncio.Event()
    step = 0
    success = False
    region_blocked = False
    session_name = os.path.basename(client.session.filename)

    @client.on(events.NewMessage(from_users=bot_entity.id))
    async def handler(event):
        nonlocal step, success, region_blocked
        text = event.message.message.strip().lower()
        markup = event.message.reply_markup

        logger.info(f"[TIDA] [{session_name}] [{report_num}] 📨 TIDABOT: step={step} | text={text[:120]!r}")

        if "not available in your region" in text:
            logger.warning(f"[TIDA] [{session_name}] [{report_num}] 🌍 Регион заблокирован — нужен другой прокси")
            region_blocked = True
            done.set()
            return

        if ("please enter a t.me" in text or "enter the link" in text or "enter a link" in text or "t.me link" in text) and step == 0:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, target)
            step = 1
            logger.info(f"[TIDA] [{session_name}] [{report_num}] Ссылка отправлена")

        elif ("select the reason" in text or "choose the reason" in text or "reason for" in text or "select a reason" in text) and step == 1:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, "Non-consensual intimate image sharing")
            step = 2
            logger.info(f"[TIDA] [{session_name}] [{report_num}] Причина отправлена")

        elif ("why the content is illegal" in text or "describe" in text or "explain" in text or "provide details" in text or "additional information" in text) and step == 2:
            await asyncio.sleep(0.3)
            await client.send_message(bot_entity, custom_text)
            step = 3
            logger.info(f"[TIDA] [{session_name}] [{report_num}] Описание отправлено")

        elif ("documentation" in text or "evidence" in text or "attach" in text or "upload" in text or "skip" in text) and step == 3:
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

        elif "create_report_failed" in text or "failed" in text:
            logger.warning(f"[TIDA] [{session_name}] [{report_num}] ❌ CREATE_REPORT_FAILED — нужен другой прокси")
            done.set()

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
    return success, region_blocked


async def _single_session_flow(session_path: str, target: str, custom_text: str,
                                proxy=None, tida_peer_ref=None, all_proxies=None) -> bool:
    session_name = os.path.basename(session_path)
    if tida_peer_ref is None:
        tida_peer_ref = [None]

    proxies_pool = list(all_proxies) if all_proxies else []
    if proxy and proxy not in proxies_pool:
        proxies_pool.insert(0, proxy)
    random.shuffle(proxies_pool)
    if proxy in proxies_pool:
        proxies_pool.remove(proxy)
        proxies_pool.insert(0, proxy)

    tried = set()
    candidates = proxies_pool if proxies_pool else [None]

    for attempt, current_proxy in enumerate(candidates):
        proxy_key = current_proxy[1] if current_proxy else "нет"
        if proxy_key in tried:
            continue
        tried.add(proxy_key)

        client = await _create_client(session_path, current_proxy)
        if not client:
            logger.warning(f"[TIDA] [{session_name}] Не удалось подключиться через {proxy_key}, пробую следующий прокси")
            continue

        try:
            try:
                bot_entity = await client.get_entity("TIDABOT")
                if tida_peer_ref[0] is None:
                    tida_peer_ref[0] = bot_entity.id
            except Exception as e:
                if tida_peer_ref[0] is not None and "No user has" in str(e):
                    bot_entity = await client.get_entity(tida_peer_ref[0])
                else:
                    logger.error(f"[TIDA] [{session_name}] Не найден TIDABOT: {e}")
                    await client.disconnect()
                    return False

            logger.info(f"[TIDA] [{session_name}] Попытка {attempt + 1} | прокси: {proxy_key}")
            success, region_blocked = await _send_one_report(client, bot_entity, target, custom_text, attempt + 1)

            if success:
                return True

            if region_blocked:
                logger.info(f"[TIDA] [{session_name}] Регион — пробую следующий прокси...")
                # продолжаем цикл с другим прокси
            else:
                logger.warning(f"[TIDA] [{session_name}] Неудача (не регион) на прокси {proxy_key}")

        except Exception as e:
            logger.error(f"[TIDA] [{session_name}] Ошибка: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    logger.warning(f"[TIDA] [{session_name}] Все прокси исчерпаны")
    return False


async def main_tida(target_link: str, custom_text: str, user: int, username: str, _log_user=None, silent: bool = False, notify_bot=None):
    _notify = notify_bot or bot
    sessions = _get_sessions()
    if not sessions:
        await _notify.send_message(user,
            "❌ *Нет сессий для TIDA!*\n*Положи .session файлы в папку* `tida_sessions/`",
            parse_mode="Markdown", reply_markup=keyboards.main_menu)
        return

    # Нормализуем target → всегда t.me/username[/msg_id]
    target = target_link.strip()
    # Убираем любые протоколы
    target = target.replace("https://", "").replace("http://", "")
    # Убираем @ в начале
    if target.startswith("@"):
        target = target[1:]
    # Убираем www.
    target = target.replace("www.", "")
    # Если уже начинается с t.me/ — ок, иначе добавляем
    if not target.startswith("t.me/"):
        target = f"t.me/{target}"
    # Защита от t.me/ без юзернейма
    parts = target.split("/")
    if len(parts) < 2 or not parts[1]:
        await _notify.send_message(user, "❌ *Неверная ссылка!*", parse_mode="Markdown", reply_markup=keyboards.main_menu)
        return

    all_proxies = _get_all_proxies()
    if not all_proxies:
        await _notify.send_message(user,
            "⚠️ *TIDA работает без прокси — это может не сработать.*\n*Рекомендуется добавить SOCKS5 прокси.*",
            parse_mode="Markdown")

    successful = 0
    total = len(sessions)

    logger.info(f"[TIDA] 🚀 Запуск | Цель: {target} | Сессий: {total} | Прокси: {len(all_proxies)}")

    tida_peer_ref = [None]
    pb = ProgressBar(_notify, user, total=total, title="🎵 *TIDA*", silent=silent)
    await pb.start()
    done_ref = [0]
    _sem = asyncio.Semaphore(10)

    async def _tracked(s):
        async with _sem:
            result = await _single_session_flow(
                s, target, custom_text,
                random.choice(all_proxies) if all_proxies else None,
                tida_peer_ref,
                all_proxies if all_proxies else None)
            done_ref[0] += 1
            await pb.update(done_ref[0])
            return result

    results = await asyncio.gather(*[_tracked(s) for s in sessions], return_exceptions=True)
    await pb.finish()
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
    try:
        import db as _db_mod
        _is_hid = await _db_mod.get_is_hidden(user)
        _log_uid = "скрыт" if _is_hid else str(user)
        _log_uname = "скрыт" if _is_hid else username
    except Exception:
        _log_uid, _log_uname = str(user), username

    caption_log = (
        f"🟣 *TIDA*\n\n"
        f"🎯 *Цель:* {target_escaped}\n"
        f"🗒️ *Текст:* {custom_text[:100]}{'...' if len(custom_text) > 100 else ''}\n"
        f"👤 *Пользователь:* {_log_uid} (@{_log_uname})\n"
        f"🕐 *Время:* {now_str}\n\n"
        f"🟢 *Успешно: {successful}*\n"
        f"🔴 *Не удалось: {total - successful}*"
    )

    if not silent:
        try:
            await _notify.send_message(user, caption_user, parse_mode="Markdown", reply_markup=keyboards.main_menu)
        except Exception as e:
            logger.error(f"[TIDA] Ошибка отправки результата пользователю: {e}")

        try:
            await main_bot.send_message(bot_logs, caption_log, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"[TIDA] Ошибка отправки лога: {e}")

    return (successful, total)
