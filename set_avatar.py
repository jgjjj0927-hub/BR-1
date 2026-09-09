"""
Устанавливает аватарку бота через MTProto (Telethon).
Bot API не умеет менять фото на многих инстансах — используем MTProto.

Запуск:  python3 set_avatar.py
"""
import asyncio
import os
import sys
import requests

IMG_PATH = "/tmp/tg_logo.png"

LOGO_URLS = [
    "https://telegram.org/img/t_logo.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/512px-Telegram_logo.svg.png",
]


def download_logo() -> bool:
    for url in LOGO_URLS:
        try:
            print(f"📥 {url}")
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(IMG_PATH, "wb") as f:
                    f.write(r.content)
                print(f"   ✅ Скачано ({len(r.content)} байт)")
                return True
            print(f"   ⚠️ Пропускаю ({r.status_code}, {len(r.content)} байт)")
        except Exception as e:
            print(f"   ⚠️ {e}")
    return False


async def set_photo_telethon(api_id: int, api_hash: str, bot_token: str):
    from telethon import TelegramClient
    from telethon.tl.functions.photos import UploadProfilePhotoRequest

    print("🔗 Подключаюсь через Telethon...")
    async with TelegramClient("set_avatar_session", api_id, api_hash) as client:
        await client.start(bot_token=bot_token)
        print("✅ Авторизован как бот")
        uploaded = await client.upload_file(IMG_PATH)
        await client(UploadProfilePhotoRequest(file=uploaded))
        print("✅ Аватарка установлена через MTProto!")


def main():
    # Пробуем взять credentials из config проекта
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        import config as cfg
        api_id   = int(getattr(cfg, "AUREPORT_API_ID", 0) or 0)
        api_hash = str(getattr(cfg, "AUREPORT_API_HASH", "") or "")
    except Exception:
        api_id, api_hash = 0, ""

    if not api_id or not api_hash:
        api_id   = int(input("API ID (с my.telegram.org): ").strip())
        api_hash = input("API Hash: ").strip()

    bot_token = input("🤖 Токен бота: ").strip()
    if not bot_token:
        print("❌ Токен пустой."); sys.exit(1)

    print(f"\n📥 Скачиваю логотип Telegram...")
    if not download_logo():
        print("❌ Не удалось скачать логотип."); sys.exit(1)

    asyncio.run(set_photo_telethon(api_id, api_hash, bot_token))

    # Чистим временный файл и сессию
    for f in (IMG_PATH, "set_avatar_session.session"):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
