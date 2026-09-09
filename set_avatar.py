"""
Устанавливает аватарку бота через MTProto (Telethon).
Использует StringSession — не создаёт файлов сессий, не конфликтует с чужими.

Запуск:  python3 set_avatar.py
"""
import asyncio
import os
import sys
import requests

IMG_PATH = "/tmp/tg_logo_big.png"

# Ищем большой логотип (≥512px) — Telegram требует минимум ~160px
LOGO_URLS = [
    "https://telegram.org/img/t_logo_2x.png",
    "https://telegram.org/img/t_logo.png",
]


def download_logo() -> bool:
    for url in LOGO_URLS:
        try:
            print(f"📥 {url}")
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(IMG_PATH, "wb") as f:
                    f.write(r.content)
                size = len(r.content)
                print(f"   ✅ Скачано ({size} байт)")
                return True
            print(f"   ⚠️ Пропускаю ({r.status_code}, {len(r.content)} байт)")
        except Exception as e:
            print(f"   ⚠️ {e}")

    # Fallback — создаём простую синюю картинку 512x512 через PIL
    try:
        from PIL import Image, ImageDraw
        print("🎨 Генерирую логотип локально (PIL)...")
        img = Image.new("RGB", (512, 512), color=(41, 182, 246))
        draw = ImageDraw.Draw(img)
        # Рисуем простой белый самолётик (упрощённо)
        draw.polygon([(100, 256), (412, 150), (350, 380)], fill=(255, 255, 255))
        img.save(IMG_PATH)
        print(f"   ✅ Создан 512×512 PNG")
        return True
    except ImportError:
        pass

    return False


async def set_photo_telethon(api_id: int, api_hash: str, bot_token: str):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.photos import UploadProfilePhotoRequest

    print("🔗 Подключаюсь через Telethon (чистая сессия)...")
    # StringSession("") — не читает файлы на диске, всегда чистая сессия
    async with TelegramClient(StringSession(""), api_id, api_hash) as client:
        await client.sign_in(bot_token=bot_token)
        me = await client.get_me()
        print(f"✅ Авторизован как @{me.username}")

        uploaded = await client.upload_file(IMG_PATH)
        await client(UploadProfilePhotoRequest(file=uploaded))
        print("✅ Аватарка установлена!")


def main():
    # Читаем credentials из config проекта
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import config as cfg
        api_id   = int(getattr(cfg, "AUREPORT_API_ID",  0) or 0)
        api_hash = str(getattr(cfg, "AUREPORT_API_HASH", "") or "")
    except Exception:
        api_id, api_hash = 0, ""

    if not api_id or not api_hash:
        api_id   = int(input("API ID (с my.telegram.org): ").strip())
        api_hash = input("API Hash: ").strip()

    bot_token = input("🤖 Токен бота: ").strip()
    if not bot_token:
        print("❌ Токен пустой."); sys.exit(1)

    print("\n📥 Скачиваю логотип Telegram...")
    if not download_logo():
        print("❌ Не удалось скачать логотип. Установи PIL: pip install Pillow")
        sys.exit(1)

    asyncio.run(set_photo_telethon(api_id, api_hash, bot_token))

    try:
        os.remove(IMG_PATH)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
