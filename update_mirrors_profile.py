"""
update_mirrors_profile.py — обновляет имя / описание / аватарку всех зеркал.
Запуск: python3 update_mirrors_profile.py
"""
import asyncio, io, sys
sys.path.insert(0, ".")
import aiohttp
import config, db

NAME       = "Brown V2"
DESC       = "Наш сайт - br-v2.top"
SHORT_DESC = "Наш сайт - br-v2.top"
MAIN_TOK   = sys.argv[1] if len(sys.argv) > 1 else config.TOKEN
CONCUR     = 20          # параллельных запросов


async def download_avatar(session: aiohttp.ClientSession) -> bytes:
    # id главного бота
    async with session.get(f"https://api.telegram.org/bot{MAIN_TOK}/getMe") as r:
        resp = await r.json()
    if not resp.get("ok"):
        raise RuntimeError(f"getMe failed: {resp}")
    bot_id = resp["result"]["id"]
    # список фото
    async with session.get(
        f"https://api.telegram.org/bot{MAIN_TOK}/getUserProfilePhotos",
        params={"user_id": bot_id, "limit": 1}
    ) as r:
        result = (await r.json())["result"]
    if not result["total_count"]:
        raise RuntimeError("У главного бота нет аватарки")
    file_id = result["photos"][0][-1]["file_id"]
    # путь к файлу
    async with session.get(
        f"https://api.telegram.org/bot{MAIN_TOK}/getFile",
        params={"file_id": file_id}
    ) as r:
        path = (await r.json())["result"]["file_path"]
    # скачиваем
    async with session.get(f"https://api.telegram.org/file/bot{MAIN_TOK}/{path}") as r:
        return await r.read()


async def api(session: aiohttp.ClientSession, token: str, method: str, **kw) -> dict:
    async with session.post(
        f"https://api.telegram.org/bot{token}/{method}",
        json=kw,
        timeout=aiohttp.ClientTimeout(total=12)
    ) as r:
        return await r.json()


async def set_photo(session: aiohttp.ClientSession, token: str, photo: bytes) -> dict:
    form = aiohttp.FormData()
    form.add_field("photo", io.BytesIO(photo), filename="avatar.jpg", content_type="image/jpeg")
    async with session.post(
        f"https://api.telegram.org/bot{token}/setMyPhoto",
        data=form,
        timeout=aiohttp.ClientTimeout(total=20)
    ) as r:
        return await r.json()


async def update(session: aiohttp.ClientSession, token: str, photo: bytes, sem: asyncio.Semaphore):
    async with sem:
        tag = token[:22] + "…"
        errs = []

        for method, kw in [
            ("setMyName",             {"name": NAME}),
            ("setMyDescription",      {"description": DESC}),
            ("setMyShortDescription", {"short_description": SHORT_DESC}),
        ]:
            try:
                r = await api(session, token, method, **kw)
                if not r.get("ok"):
                    errs.append(f"{method}: {r.get('description')}")
            except Exception as e:
                errs.append(f"{method}: {e}")

        try:
            r = await set_photo(session, token, photo)
            if not r.get("ok"):
                errs.append(f"setMyPhoto: {r.get('description')}")
        except Exception as e:
            errs.append(f"setMyPhoto: {e}")

        if errs:
            print(f"  ⚠  {tag}  —  {' | '.join(errs)}")
        else:
            print(f"  ✅ {tag}")


async def main():
    await db.init_db()
    tokens = await db.get_all_mirror_tokens()
    if not tokens:
        print("Зеркал нет."); return

    print(f"Зеркал: {len(tokens)}")
    connector = aiohttp.TCPConnector(limit=CONCUR)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("📥 Скачиваю аватарку главного бота…")
        photo = await download_avatar(session)
        print(f"   {len(photo):,} байт\n🔄 Обновляю…\n")

        sem = asyncio.Semaphore(CONCUR)
        await asyncio.gather(*[update(session, t, photo, sem) for t in tokens])

    print("\n✅ Готово.")


asyncio.run(main())
