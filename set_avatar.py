import requests
import sys
import os

IMG_PATH = "/tmp/tg_logo.png"

LOGO_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/512px-Telegram_logo.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/240px-Telegram_logo.svg.png",
    "https://telegram.org/img/t_logo.png",
]

# setMyPhoto добавлен в Bot API 7.3; на старых инстансах — setMyProfilePhoto
METHODS = ["setMyPhoto", "setMyProfilePhoto"]

def download_logo():
    for url in LOGO_URLS:
        try:
            print(f"📥 {url}")
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(IMG_PATH, "wb") as f:
                    f.write(r.content)
                print(f"   ✅ Скачано ({len(r.content)} байт)")
                return True
            else:
                print(f"   ⚠️ Пропускаю ({r.status_code}, {len(r.content)} байт)")
        except Exception as e:
            print(f"   ⚠️ Ошибка: {e}")
    return False

def try_set_photo(token, method):
    with open(IMG_PATH, "rb") as f:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            files={"photo": ("tg_logo.png", f, "image/png")},
            timeout=30,
        )
    return resp.json()

def main():
    token = input("🤖 Введи токен бота: ").strip()
    if not token:
        print("❌ Токен пустой.")
        sys.exit(1)

    me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10).json()
    if not me.get("ok"):
        print(f"❌ Неверный токен: {me.get('description')}")
        sys.exit(1)
    bot_name = me["result"].get("username", "?")
    print(f"✅ Бот: @{bot_name}")

    print("\n📥 Скачиваю логотип Telegram...")
    if not download_logo():
        print("❌ Не удалось скачать логотип.")
        sys.exit(1)

    print("\n🖼  Устанавливаю аватарку...")
    for method in METHODS:
        data = try_set_photo(token, method)
        print(f"   [{method}] → {data}")
        if data.get("ok"):
            print(f"\n✅ Аватарка @{bot_name} обновлена!")
            os.remove(IMG_PATH)
            return
        if data.get("error_code") == 404:
            print(f"   Метод не найден, пробую следующий...")
            continue
        # Другая ошибка — выводим и выходим
        print(f"\n❌ Ошибка: {data.get('description')}")
        sys.exit(1)

    print("\n❌ Ни один метод не сработал. Проверь версию Bot API.")

if __name__ == "__main__":
    main()
