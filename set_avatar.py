"""
Устанавливает аватарку бота через MTProto.
Использует уже авторизованную сессию из trap_session/trap.

Запуск:  python3 set_avatar.py
"""
import asyncio
import os
import sys
import requests

IMG_PATH     = "/tmp/tg_logo_big.png"
SESSION_PATH = "trap_session/trap"

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
                print(f"   ✅ Скачано ({len(r.content)} байт)")
                return True
            print(f"   ⚠️ Пропускаю ({r.status_code}, {len(r.content)} байт)")
        except Exception as e:
            print(f"   ⚠️ {e}")

    # Fallback — генерируем 512×512 через Pillow
    try:
        from PIL import Image, ImageDraw
        print("🎨 Генерирую логотип локально (PIL)...")
        img = Image.new("RGB", (512, 512), color=(41, 182, 246))
        draw = ImageDraw.Draw(img)
        draw.polygon([(100, 256), (412, 150), (350, 380)], fill=(255, 255, 255))
        img.save(IMG_PATH)
        print("   ✅ Создан 512×512 PNG")
        return True
    except ImportError:
        pass

    return False


async def set_photo(api_id: int, api_hash: str, bot_token: str):
    from telethon import TelegramClient
    from telethon.tl.functions.photos import UploadProfilePhotoRequest

    print(f"🔗 Подключаюсь через сессию: {SESSION_PATH}")
    async with TelegramClient(SESSION_PATH, api_id, api_hash) as client:
        # Сессия уже авторизована — если нет, логинимся как бот
        if not await client.is_user_authorized():
            print("⚠️  Сессия не авторизована, логинюсь по токену бота...")
            await client.sign_in(bot_token=bot_token)

        me = await client.get_me()
        print(f"✅ Используем аккаунт: {me.first_name} (@{me.username})")

        uploaded = await client.upload_file(IMG_PATH)
        await client(UploadProfilePhotoRequest(file=uploaded))
        print("✅ Аватарка установлена!")


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config as cfg
    api_id   = int(cfg.AUREPORT_API_ID)
    api_hash = cfg.AUREPORT_API_HASH

    bot_token = input("🤖 Токен бота: ").strip()
    if not bot_token:
        print("❌ Токен пустой."); sys.exit(1)

    print("\n📥 Скачиваю логотип Telegram...")
    if not download_logo():
        print("❌ Не удалось скачать. Установи PIL: pip install Pillow")
        sys.exit(1)

    asyncio.run(set_photo(api_id, api_hash, bot_token))

    try:
        os.remove(IMG_PATH)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
