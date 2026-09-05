"""
Парсит ID и номер телефона из каждой lolz-сессии,
сортирует по возрасту аккаунта (меньший ID = старше).
"""

import asyncio
import os
import random
from telethon import TelegramClient

FOLDERS = ["sessions"]
MAX_CONCURRENT = 10

API_PAIRS = [
    ("24565698",  "5a084b434f8505ace703485b9da85040"),
    ("27904162",  "e7cba879b1c643ba77490bf328df5ebc"),
    ("23037915",  "50f06f5b2223586fde0d1379ea91ebc7"),
    ("29512095",  "0b29a7d42fff002856b9bed64f7ec919"),
    ("25055016",  "25edf5b7becebe91a2d61fe8d9d9931b"),
]


def _rand_api():
    api_id, api_hash = random.choice(API_PAIRS)
    return int(api_id), api_hash


async def get_session_info(session_path: str) -> dict | None:
    api_id, api_hash = _rand_api()
    client = TelegramClient(session_path, api_id, api_hash,
                            system_version="4.16.30-vxCUSTOM")
    try:
        await asyncio.wait_for(client.connect(), timeout=10)
        if not await client.is_user_authorized():
            return None
        me = await client.get_me()
        return {"id": me.id, "phone": me.phone or "—", "path": session_path}
    except Exception:
        return None
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main():
    sessions = []
    for folder in FOLDERS:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith(".session"):
                sessions.append((folder, os.path.join(folder, f.replace(".session", ""))))


    print(f"Найдено {len(sessions)} сессий, читаю...")

    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def _run(folder, path):
        async with sem:
            r = await get_session_info(path)
            if r:
                r["folder"] = folder
            return r

    results = await asyncio.gather(*[_run(f, p) for f, p in sessions])
    valid = [r for r in results if r is not None]
    valid.sort(key=lambda x: x["id"])

    print(f"\n{'№':<4} {'ID':<15} {'Телефон':<20} {'Папка':<16} {'Файл'}")
    print("─" * 75)
    for i, acc in enumerate(valid, 1):
        print(f"{i:<4} {acc['id']:<15} +{acc['phone']:<20} {acc['folder']:<16} {os.path.basename(acc['path'])}")

    print(f"\nВсего авторизовано: {len(valid)} из {len(sessions)}")


if __name__ == "__main__":
    asyncio.run(main())
