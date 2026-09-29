"""
probe_bot.py — проверяет незащищённые admin callback в боте.
Запуск: python3 probe_bot.py
"""
import asyncio
import sys
import os

TARGET_BOT = "@kpixabot"

CALLBACKS = [
    "admin", "admin_panel", "panel", "admin_menu",
    "admin_main", "settings", "admin_settings",
    "manage", "admin_manage", "control", "dashboard",
    "users", "admin_users", "stats", "admin_stats",
    "broadcast", "admin_broadcast", "mailing",
    "ban", "unban", "give", "add_balance",
    "admin_give", "admin_ban", "promo", "admin_promo",
]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


ADMIN_COMMANDS = [
    "/admin", "/panel", "/manage", "/stats",
    "/broadcast", "/ban", "/users", "/dashboard",
    "/control", "/settings", "/promo",
]


async def probe(session_path: str, api_id: int, api_hash: str):
    from telethon import TelegramClient

    client = TelegramClient(session_path, api_id, api_hash,
                            system_version="4.16.30-vxCUSTOM")
    await client.connect()
    if not await client.is_user_authorized():
        print("❌ Сессия не авторизована")
        await client.disconnect()
        return

    me = await client.get_me()
    print(f"✅ Вошёл как @{me.username} ({me.id})")

    # 1. Пробуем admin-команды
    print(f"\n🔍 Пробую admin-команды в {TARGET_BOT}...\n")
    for cmd in ADMIN_COMMANDS:
        await client.send_message(TARGET_BOT, cmd)
        await asyncio.sleep(1.2)
        msgs = await client.get_messages(TARGET_BOT, limit=1)
        if msgs:
            text = (msgs[0].text or msgs[0].caption or "")[:120]
            print(f"  [{cmd}] → {text or '(пусто)'}")
        else:
            print(f"  [{cmd}] → нет ответа")

    # 2. Кликаем все реальные кнопки из /start
    print(f"\n🔘 Кликаю реальные кнопки из /start...\n")
    await client.send_message(TARGET_BOT, "/start")
    await asyncio.sleep(1.5)

    msgs = await client.get_messages(TARGET_BOT, limit=10)
    bot_msg = next((m for m in msgs if m.buttons), None)

    if not bot_msg:
        print("⚠️  Нет сообщений с кнопками")
    else:
        print(f"📋 message_id={bot_msg.id}, кнопок: {sum(len(r) for r in bot_msg.buttons)}\n")
        for row in bot_msg.buttons:
            for btn in row:
                cb_data = btn.data.decode() if btn.data else None
                print(f"  Кнопка: «{btn.text}» → callback_data={cb_data!r}")
                try:
                    await btn.click()
                    await asyncio.sleep(1.2)
                    new_msgs = await client.get_messages(TARGET_BOT, limit=1)
                    if new_msgs:
                        text = (new_msgs[0].text or new_msgs[0].caption or "")[:150]
                        btns_info = ""
                        if new_msgs[0].buttons:
                            btns_info = " [+кнопки: " + ", ".join(
                                b.data.decode() if b.data else b.text
                                for row2 in new_msgs[0].buttons for b in row2
                            ) + "]"
                        print(f"    → {text}{btns_info}")
                except Exception as e:
                    print(f"    ⚠️  {e}")

    print("\n✅ Готово")
    await client.disconnect()


async def login(api_id: int, api_hash: str) -> str:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError

    session_path = "/tmp/probe_session"
    client = TelegramClient(session_path, api_id, api_hash,
                            system_version="4.16.30-vxCUSTOM")
    await client.connect()

    if not await client.is_user_authorized():
        phone = input("📱 Номер телефона (с +): ").strip()
        await client.send_code_request(phone)
        code = input("📩 Код из Telegram: ").strip()
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("🔐 Пароль 2FA: ").strip()
            await client.sign_in(password=password)

    me = await client.get_me()
    print(f"✅ Авторизован как @{me.username} ({me.id})")
    await client.disconnect()
    return session_path


def main():
    import config as cfg
    api_id   = int(cfg.AUREPORT_API_ID)
    api_hash = cfg.AUREPORT_API_HASH

    session_path = asyncio.run(login(api_id, api_hash))
    asyncio.run(probe(session_path, api_id, api_hash))


if __name__ == "__main__":
    main()
