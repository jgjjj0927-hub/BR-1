"""
Brown V2 | lolz_worker.py
Автоматическая пересадка lolz-аккаунтов.

Цикл каждые 10 минут:
1. Берём сессию из lolz/ (без суффикса _new)
2. Кикаем все чужие сессии (ResetAuthorizations)
3. Запрашиваем код входа (SendCode) на номер аккаунта
4. Читаем код из диалога с Telegram через lolz-сессию
5. Авторизуем новую сессию sessions/НОМЕР_new.session
6. Ставим облачный пароль Ali095095 через СТАРУЮ lolz-сессию
7. Logout старой сессии + удаляем файл lolz/

Запуск: python3 lolz_worker.py
Или как systemd-сервис.
"""

import asyncio
import os
import re
import logging
import random

from telethon import TelegramClient
from telethon.tl.functions.auth import (
    ResetAuthorizationsRequest,
    SendCodeRequest,
    SignInRequest,
)
from telethon.errors import FloodWaitError

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/lolz_worker.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("lolz_worker")

# ─── Конфиг ───────────────────────────────────────────────────────────────────
LOLZ_FOLDER      = "lolz"
OUTPUT_FOLDER    = "sessions"      # куда кладём _new сессии
PREM_FOLDER      = "prem_sessions"
CLOUD_PASS       = "Ali095095"
CHECK_INTERVAL   = 10 * 60        # 10 минут
CODE_WAIT        = 60             # секунд ждём код
CODE_RETRIES     = 6              # попыток прочитать код

API_PAIRS = [
    ("24565698",  "5a084b434f8505ace703485b9da85040"),
    ("27904162",  "e7cba879b1c643ba77490bf328df5eab"),
    ("23037915",  "50f06f5b2223586fde0d1379ea91ebc7"),
    ("29512095",  "0b29a7d42fff002856b9bed64f7ec919"),
    ("25055016",  "25edf5b7becebe91a2d61fe8d9d9931b"),
]

os.makedirs(LOLZ_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# FloodWait-кэш: session_name -> timestamp до которого нельзя трогать
_flood_until: dict[str, float] = {}

# ─── Утилиты ──────────────────────────────────────────────────────────────────

def _get_lolz_sessions() -> list[str]:
    """Возвращает пути к lolz-сессиям без суффикса _new."""
    result = []
    if not os.path.exists(LOLZ_FOLDER):
        return result
    for f in os.listdir(LOLZ_FOLDER):
        if f.endswith(".session") and "_new" not in f:
            stem = f.replace(".session", "")
            result.append(os.path.join(LOLZ_FOLDER, stem))
    return result


def _rand_api() -> tuple[int, str]:
    api_id, api_hash = random.choice(API_PAIRS)
    return int(api_id), api_hash


async def _read_tg_code(client: TelegramClient, timeout: int = CODE_WAIT) -> str | None:
    """
    Polling: каждые 5 секунд проверяем новые сообщения от 777000.
    Надёжнее event-handler, который может не сработать при connect-only.
    """
    import time

    # Запоминаем ID последнего сообщения ДО запроса кода
    last_msg_id = 0
    try:
        msgs = await client.get_messages(777000, limit=1)
        if msgs:
            last_msg_id = msgs[0].id
    except Exception:
        pass

    deadline = time.monotonic() + timeout
    poll_interval = 5  # секунд между проверками

    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)
        try:
            msgs = await client.get_messages(777000, limit=5)
            for msg in msgs:
                if msg.id <= last_msg_id:
                    continue
                text = msg.text or ""
                match = re.search(r'\b(\d{5})\b', text)
                if match:
                    code = match.group(1)
                    logger.info(f"Код получен: {code} (msg_id={msg.id})")
                    return code
        except Exception as e:
            logger.warning(f"Ошибка при чтении кода: {e}")

    return None


async def _set_cloud_password(client: TelegramClient, password: str) -> bool:
    """Ставит облачный пароль через СТАРУЮ сессию используя Telethon edit_2fa."""
    try:
        await client.edit_2fa(new_password=password, hint="")
        logger.info("Облачный пароль установлен ✅")
        return True
    except Exception as e:
        logger.warning(f"Ошибка установки пароля: {e}")
        return False


# ─── Основная логика обработки одной сессии ──────────────────────────────────

async def process_lolz_session(session_path: str) -> bool:
    """
    Обрабатывает одну lolz-сессию.
    Возвращает True если успешно.
    """
    import time
    session_name = os.path.basename(session_path)

    # Проверяем FloodWait-кэш
    if session_name in _flood_until:
        remaining = _flood_until[session_name] - time.monotonic()
        if remaining > 0:
            logger.info(f"[{session_name}] ⏸ FloodWait кэш — жду ещё {remaining:.0f}с, пропускаю")
            return False

    logger.info(f"[{session_name}] Начинаю обработку...")

    api_id, api_hash = _rand_api()

    # Подключаемся к lolz-сессии
    lolz_client = TelegramClient(
        session_path, api_id, api_hash,
        system_version="4.16.30-vxCUSTOM"
    )

    try:
        await asyncio.wait_for(lolz_client.connect(), timeout=15)

        if not await lolz_client.is_user_authorized():
            logger.warning(f"[{session_name}] Не авторизован, пропускаю")
            await lolz_client.disconnect()
            return False

        me = await lolz_client.get_me()
        phone = me.phone
        logger.info(f"[{session_name}] Аккаунт: +{phone}")

        # ── Шаг 1: Кикаем все чужие сессии ───────────────────────────────────
        logger.info(f"[{session_name}] Кикаю все сессии...")
        try:
            await lolz_client(ResetAuthorizationsRequest())
            logger.info(f"[{session_name}] Все сессии кикнуты ✅")
        except FloodWaitError as e:
            logger.warning(f"[{session_name}] FloodWait {e.seconds}с — пропускаю на этот раз")
            await lolz_client.disconnect()
            return False
        except Exception as e:
            logger.warning(f"[{session_name}] Ошибка кика: {e}")
            await lolz_client.disconnect()
            return False

        await asyncio.sleep(2)

        # ── Шаг 2: Запрашиваем код входа ─────────────────────────────────────
        logger.info(f"[{session_name}] Запрашиваю код входа...")
        new_api_id, new_api_hash = _rand_api()
        new_session_name = f"{session_name}_new"
        new_session_path = os.path.join(OUTPUT_FOLDER, new_session_name)

        new_client = TelegramClient(
            new_session_path, new_api_id, new_api_hash,
            system_version="4.16.30-vxCUSTOM"
        )

        try:
            await asyncio.wait_for(new_client.connect(), timeout=15)

            from telethon.tl.types import CodeSettings
            sent = await new_client(SendCodeRequest(
                phone_number=f"+{phone}",
                api_id=new_api_id,
                api_hash=new_api_hash,
                settings=CodeSettings()
            ))
            phone_code_hash = sent.phone_code_hash
            logger.info(f"[{session_name}] Код запрошен, ждём...")

        except Exception as e:
            logger.warning(f"[{session_name}] Ошибка запроса кода: {e}")
            # Если FloodWait — запоминаем сколько ждать
            import time as _time
            flood_match = re.search(r'wait of (\d+) seconds', str(e))
            if flood_match:
                wait_sec = int(flood_match.group(1))
                _flood_until[session_name] = _time.monotonic() + wait_sec
                logger.info(f"[{session_name}] FloodWait {wait_sec}с — следующая попытка через {wait_sec//60}м")
            try:
                await new_client.disconnect()
            except Exception:
                pass
            await lolz_client.disconnect()
            # Чистим неполную сессию
            for ext in [".session", ".session-journal"]:
                try:
                    os.remove(new_session_path + ext)
                except Exception:
                    pass
            return False

        # ── Шаг 3: Читаем код из диалога с Telegram ───────────────────────────
        code = await _read_tg_code(lolz_client, timeout=CODE_WAIT)

        if not code:
            logger.warning(f"[{session_name}] Код не получен за {CODE_WAIT}с")
            try:
                await new_client.disconnect()
            except Exception:
                pass
            await lolz_client.disconnect()
            for ext in [".session", ".session-journal"]:
                try:
                    os.remove(new_session_path + ext)
                except Exception:
                    pass
            return False

        # ── Шаг 4: Авторизуем новую сессию ───────────────────────────────────
        logger.info(f"[{session_name}] Авторизую новую сессию с кодом {code}...")
        try:
            await new_client(SignInRequest(
                phone_number=f"+{phone}",
                phone_code_hash=phone_code_hash,
                phone_code=code,
            ))
            logger.info(f"[{session_name}] Новая сессия авторизована ✅")
        except Exception as e:
            logger.warning(f"[{session_name}] Ошибка авторизации: {e}")
            try:
                await new_client.disconnect()
            except Exception:
                pass
            await lolz_client.disconnect()
            for ext in [".session", ".session-journal"]:
                try:
                    os.remove(new_session_path + ext)
                except Exception:
                    pass
            return False

        # ── Шаг 5: Ставим облачный пароль через СТАРУЮ сессию ────────────────
        logger.info(f"[{session_name}] Ставлю облачный пароль через старую сессию...")
        await _set_cloud_password(lolz_client, CLOUD_PASS)

        # ── Шаг 6: Logout старой + удаление ──────────────────────────────────
        logger.info(f"[{session_name}] Выхожу из старой сессии и удаляю...")
        try:
            await lolz_client.log_out()
        except Exception:
            pass
        try:
            await lolz_client.disconnect()
        except Exception:
            pass

        # Удаляем lolz-сессию
        for ext in [".session", ".session-journal"]:
            path = session_path + ext
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Удалён: {path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить {path}: {e}")

        # Закрываем новый клиент
        try:
            await new_client.disconnect()
        except Exception:
            pass

        logger.info(f"[{session_name}] ✅ Готово! Новая сессия: {new_session_path}.session")
        return True

    except Exception as e:
        logger.error(f"[{session_name}] Неожиданная ошибка: {e}")
        try:
            await lolz_client.disconnect()
        except Exception:
            pass
        return False


# ─── Главный цикл ─────────────────────────────────────────────────────────────

async def worker_loop():
    logger.info("=" * 50)
    logger.info("Lolz Worker запущен")
    logger.info(f"Папка lolz: {os.path.abspath(LOLZ_FOLDER)}")
    logger.info(f"Интервал: {CHECK_INTERVAL // 60} минут")
    logger.info("=" * 50)

    while True:
        sessions = _get_lolz_sessions()

        if not sessions:
            logger.info("Нет сессий в lolz/ — жду...")
        else:
            logger.info(f"Найдено {len(sessions)} lolz-сессий, обрабатываю...")
            for session_path in sessions:
                try:
                    success = await process_lolz_session(session_path)
                    if success:
                        logger.info(f"✅ {os.path.basename(session_path)} обработана успешно")
                    else:
                        logger.info(f"⏳ {os.path.basename(session_path)} — не удалось, попробую позже")
                except Exception as e:
                    logger.error(f"❌ {session_path}: {e}")

                # Пауза между аккаунтами
                await asyncio.sleep(5)

        logger.info(f"Следующая проверка через {CHECK_INTERVAL // 60} минут...")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(worker_loop())
