import requests
import sys

def main():
    token = input("🤖 Введи токен бота: ").strip()
    if not token:
        print("❌ Токен пустой.")
        sys.exit(1)

    # Проверяем токен
    me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    me_data = me.json()
    if not me_data.get("ok"):
        print(f"❌ Неверный токен: {me_data.get('description', '?')}")
        sys.exit(1)
    bot_name = me_data["result"].get("username", "?")
    print(f"✅ Бот найден: @{bot_name}")

    # Скачиваем логотип Telegram
    logo_urls = [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/240px-Telegram_logo.svg.png",
        "https://telegram.org/img/t_logo.png",
    ]

    img_data = None
    for url in logo_urls:
        try:
            print(f"📥 Скачиваю логотип: {url}")
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                img_data = r.content
                break
        except Exception as e:
            print(f"   ⚠️ Ошибка: {e}")

    if not img_data:
        print("❌ Не удалось скачать логотип Telegram.")
        sys.exit(1)

    print("🖼  Устанавливаю аватарку...")
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/setMyPhoto",
        files={"photo": ("tg_logo.png", img_data, "image/png")},
        timeout=30,
    )
    data = resp.json()
    if data.get("ok"):
        print(f"✅ Аватарка @{bot_name} успешно обновлена на логотип Telegram!")
    else:
        print(f"❌ Ошибка API: {data.get('description', 'Неизвестно')}")

if __name__ == "__main__":
    main()
