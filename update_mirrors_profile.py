"""
update_mirrors_profile.py
Обновляет все зеркала: имя → "Brown V2", описание → "Наш сайт - br-v2.top",
аватарка → копия с главного бота.

Запуск: python3 update_mirrors_profile.py
"""

import asyncio
import aiohttp
import io
import config
import db

NAME        = "Brown V2"
DESCRIPTION = "Наш сайт - br-v2.top"
MAIN_TOKEN  = config.TOKEN


async def fetch_main_bot_avatar(session: aiohttp.ClientSession) -> bytes | None:
    """Скачивает текущую аватарку главного бота."""
    try:
        # Узнаём ID главного бота
        async with session.get(f"https://api.telegram.org/bot{MAIN_TOKEN}/getMe") as r:
            me = (await r.json())["result"]
            bot_id = me["id"]

        # Берём первое фото профиля
        async with session.get(
            f"https://api.telegram.org/bot{MAIN_TOKEN}/getUserProfilePhotos",
            params={"user_id": bot_id, "limit": 1},
        ) as r:
            data = (await r.json())["result"]

        if not data.get("total_count"):
            print("⚠️  У главного бота нет аватарки")
            return None

        # Самый большой размер
        file_id = data["photos"][0][-1]["file_id"]

        async with session.get(
            f"https://api.telegram.org/bot{MAIN_TOKEN}/getFile",
            params={"file_id": file_id},
        ) as r:
            file_path = (await r.json())["result"]["file_path"]

        async with session.get(
            f"https://api.telegram.org/file/bot{MAIN_TOKEN}/{file_path}"
        ) as r:
            return await r.read()

    except Exception as e:
        print(f"❌ Не удалось скачать аватарку: {e}")
        return None


async def update_one(session: aiohttp.ClientSession, token: str, photo: bytes | None):
    short = token[:20] + "..."
    errors = []

    # Имя
    try:
        async with session.post(
            f"https://api.telegram.org/bot{token}/setMyName",
            json={"name": NAME},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            res = await r.json()
            if not res.get("ok"):
                errors.append(f"name: {res.get('description')}")
    except Exception as e:
        errors.append(f"name: {e}")

    # Описание
    try:
        async with session.post(
            f"https://api.telegram.org/bot{token}/setMyDescription",
            json={"description": DESCRIPTION},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            res = await r.json()
            if not res.get("ok"):
                errors.append(f"desc: {res.get('description')}")
    except Exception as e:
        errors.append(f"desc: {e}")

    # Аватарка
    if photo:
        try:
            form = aiohttp.FormData()
            form.add_field("photo", io.BytesIO(photo), filename="avatar.jpg", content_type="image/jpeg")
            async with session.post(
                f"https://api.telegram.org/bot{token}/setMyPhoto",
                data=form,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                res = await r.json()
                if not res.get("ok"):
                    errors.append(f"photo: {res.get('description')}")
        except Exception as e:
            errors.append(f"photo: {e}")

    if errors:
        print(f"  ⚠️  {short} — ошибки: {'; '.join(errors)}")
    else:
        print(f"  ✅ {short}")


async def main():
    await db.init_db()
    tokens = await db.get_all_mirror_tokens()
    if not tokens:
        print("Зеркал в БД нет.")
        return

    print(f"Найдено зеркал: {len(tokens)}")

    async with aiohttp.ClientSession() as session:
        print("📥 Скачиваю аватарку главного бота...")
        photo = await fetch_main_bot_avatar(session)
        if photo:
            print(f"   Размер: {len(photo):,} байт")

        print("\n🔄 Обновляю зеркала...")
        # По 5 параллельно чтобы не флудить Telegram
        sem = asyncio.Semaphore(5)

        async def bounded(tok):
            async with sem:
                await update_one(session, tok, photo)

        await asyncio.gather(*[bounded(t) for t in tokens])

    print("\n✅ Готово.")


if __name__ == "__main__":
    asyncio.run(main())
