"""
update_mirrors_profile.py
Обновляет все зеркала: имя, описание (оба поля), аватарка через Telethon.

Запуск: python3 update_mirrors_profile.py
"""

import asyncio
import io
import json
import urllib.request
import urllib.parse

import config
import db

NAME             = "Brown V2"
DESCRIPTION      = "Наш сайт - br-v2.top"   # пустой чат
SHORT_DESC       = "Наш сайт - br-v2.top"   # поле «О боте» в профиле
MAIN_TOKEN       = config.TOKEN
API_ID           = int(config.AUREPORT_API_ID)
API_HASH         = config.AUREPORT_API_HASH


def _tg_json(token: str, method: str, **params) -> dict:
    """Синхронный HTTP-запрос к Bot API (без aiohttp)."""
    url  = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(params).encode()
    req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "description": str(e)}


def _tg_upload_photo(token: str, photo_bytes: bytes) -> dict:
    """Загружает фото через multipart/form-data (setMyPhoto)."""
    url      = f"https://api.telegram.org/bot{token}/setMyPhoto"
    boundary = b"----BRV2BOUNDARY"
    body     = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="photo"; filename="avatar.jpg"\r\n'
        b"Content-Type: image/jpeg\r\n\r\n"
        + photo_bytes + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "description": str(e)}


async def _fetch_main_avatar() -> bytes | None:
    """Скачивает аватарку главного бота через Telethon."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await asyncio.wait_for(client.connect(), timeout=15)
        await client.start(bot_token=MAIN_TOKEN)
        me = await client.get_me()
        photos = await client.get_profile_photos(me)
        if not photos:
            print("⚠️  У главного бота нет аватарки")
            await client.disconnect()
            return None
        buf = io.BytesIO()
        await client.download_media(photos[0], file=buf)
        await client.disconnect()
        data = buf.getvalue()
        print(f"📥 Аватарка скачана: {len(data):,} байт")
        return data
    except Exception as e:
        print(f"❌ Ошибка при скачивании аватарки: {e}")
        return None


async def _set_photo_telethon(token: str, photo_bytes: bytes) -> bool:
    """Загружает аватарку зеркалу через Telethon (надёжнее Bot API)."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.photos import UploadProfilePhotoRequest
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await asyncio.wait_for(client.connect(), timeout=15)
        await client.start(bot_token=token)
        buf = io.BytesIO(photo_bytes)
        buf.name = "avatar.jpg"
        file = await client.upload_file(buf, file_name="avatar.jpg")
        await client(UploadProfilePhotoRequest(file=file))
        await client.disconnect()
        return True
    except Exception as e:
        return False


async def update_one(token: str, photo: bytes | None, sem: asyncio.Semaphore):
    async with sem:
        short  = token[:22] + "..."
        errors = []

        loop = asyncio.get_event_loop()

        # Имя
        r = await loop.run_in_executor(None, lambda: _tg_json(token, "setMyName", name=NAME))
        if not r.get("ok"):
            errors.append(f"name: {r.get('description')}")

        # Описание (пустой чат)
        r = await loop.run_in_executor(None, lambda: _tg_json(token, "setMyDescription", description=DESCRIPTION))
        if not r.get("ok"):
            errors.append(f"desc: {r.get('description')}")

        # О боте (профиль)
        r = await loop.run_in_executor(None, lambda: _tg_json(token, "setMyShortDescription", short_description=SHORT_DESC))
        if not r.get("ok"):
            errors.append(f"short_desc: {r.get('description')}")

        # Аватарка — сначала пробуем Telethon, fallback на Bot API
        if photo:
            ok = await _set_photo_telethon(token, photo)
            if not ok:
                r = await loop.run_in_executor(None, lambda: _tg_upload_photo(token, photo))
                if not r.get("ok"):
                    errors.append(f"photo: {r.get('description')}")

        if errors:
            print(f"  ⚠️  {short} — {'; '.join(errors)}")
        else:
            print(f"  ✅ {short}")


async def main():
    await db.init_db()
    tokens = await db.get_all_mirror_tokens()
    if not tokens:
        print("Зеркал в БД нет.")
        return

    print(f"Найдено зеркал: {len(tokens)}\n")
    photo = await _fetch_main_avatar()

    print("\n🔄 Обновляю зеркала...\n")
    sem = asyncio.Semaphore(3)  # 3 параллельно — Telethon не любит больше
    await asyncio.gather(*[update_one(t, photo, sem) for t in tokens])
    print("\n✅ Готово.")


if __name__ == "__main__":
    asyncio.run(main())
