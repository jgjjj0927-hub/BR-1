"""
list_sessions.py
Получает реальный Telegram ID каждой сессии через get_me()
и сортирует по нему (меньший ID = старше аккаунт).
Запуск: python3 list_sessions.py
"""

import asyncio
import os

try:
    from telethon import TelegramClient
except ImportError:
    print("pip install telethon")
    import sys; sys.exit(1)

API_ID   = 24565698
API_HASH = "5a084b434f8505ace703485b9da85040"
TIMEOUT  = 8
MAX_PARALLEL = 15

FOLDERS = [
    "sessions",
    "prem_sessions",
    "aureport_sessions",
    "tida_sessions",
    "lolz",
    "trap_session",
]

sem = asyncio.Semaphore(MAX_PARALLEL)


async def get_real_id(session_path: str, folder: str, filename: str) -> tuple:
    """Подключается к сессии и возвращает реальный Telegram user_id."""
    async with sem:
        client = TelegramClient(
            session_path, API_ID, API_HASH,
            system_version="4.16.30-vxCUSTOM"
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=TIMEOUT)
            if not await client.is_user_authorized():
                await client.disconnect()
                return (filename, folder, None, "не авторизован")
            me = await asyncio.wait_for(client.get_me(), timeout=TIMEOUT)
            await client.disconnect()
            if me:
                return (filename, folder, me.id, f"+{me.phone}" if me.phone else "-")
            return (filename, folder, None, "нет данных")
        except asyncio.TimeoutError:
            try: await client.disconnect()
            except: pass
            return (filename, folder, None, "таймаут")
        except Exception as e:
            try: await client.disconnect()
            except: pass
            return (filename, folder, None, str(e)[:40])


async def main():
    all_sessions = []
    for folder in FOLDERS:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith(".session"):
                stem = f.replace(".session", "")
                path = os.path.join(folder, stem)
                all_sessions.append((path, folder, f))

    total = len(all_sessions)
    print(f"\n{'='*70}")
    print(f"  Сессий найдено: {total} | Получаю реальные Telegram ID...")
    print(f"{'='*70}\n")

    tasks = [get_real_id(p, f, fn) for p, f, fn in all_sessions]
    results = await asyncio.gather(*tasks)

    # Сортируем: сначала авторизованные по реальному ID (меньший = старше)
    # потом неавторизованные
    def sort_key(r):
        filename, folder, real_id, info = r
        folder_order = {f: i for i, f in enumerate(FOLDERS)}
        if real_id is not None:
            return (0, folder_order.get(folder, 99), real_id)
        return (1, folder_order.get(folder, 99), 0)

    results = sorted(results, key=sort_key)

    # Вывод таблицы
    print(f"{'#':<5} {'Файл':<40} {'Папка':<20} {'Telegram ID':<15} {'Инфо'}")
    print("-" * 90)

    ok_count = 0
    for i, (filename, folder, real_id, info) in enumerate(results, 1):
        stem = filename.replace(".session", "")
        if real_id is not None:
            ok_count += 1
            icon = "✅"
            print(f"{icon} {i:<4} {stem:<40} {folder:<20} {real_id:<15} {info}")
        else:
            icon = "❌"
            print(f"{icon} {i:<4} {stem:<40} {folder:<20} {'—':<15} {info}")

    print("-" * 90)
    print(f"\n✅ Авторизован: {ok_count}")
    print(f"❌ Нет доступа: {total - ok_count}")
    print(f"📦 Всего      : {total}\n")

    # Разбивка по папкам
    from collections import Counter
    counts = Counter(r[1] for r in results)
    for folder in FOLDERS:
        if folder in counts:
            print(f"  {folder}: {counts[folder]}")


if __name__ == "__main__":
    asyncio.run(main())
