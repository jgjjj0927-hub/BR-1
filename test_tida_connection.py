"""
Тест подключения TIDA сессии к @TIDAbot.
Берёт первую сессию из tida_sessions/ и пишет /start в @TIDAbot.
Запуск: python3 test_tida_connection.py
"""
import asyncio
import os
from telethon import TelegramClient, events

TIDA_SESSIONS_DIR = "tida_sessions"
API_ID = 24565698
API_HASH = "5a084b434f8505ace703485b9da85040"


async def main():
    sessions = [f.replace(".session", "") for f in os.listdir(TIDA_SESSIONS_DIR) if f.endswith(".session")]
    if not sessions:
        print(f"❌ Нет сессий в папке {TIDA_SESSIONS_DIR}/")
        return

    session_name = sessions[0]
    session_path = os.path.join(TIDA_SESSIONS_DIR, session_name)
    print(f"📂 Используем сессию: {session_name}")

    client = TelegramClient(session_path, API_ID, API_HASH, system_version="4.16.30-vxCUSTOM")

    try:
        await asyncio.wait_for(client.connect(), timeout=15)
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        return

    if not await client.is_user_authorized():
        print("❌ Сессия не авторизована (невалидна)")
        await client.disconnect()
        return

    me = await client.get_me()
    print(f"✅ Авторизован как: @{me.username} ({me.first_name})")

    received = asyncio.Event()
    response_text = []

    @client.on(events.NewMessage(from_users="TIDAbot"))
    async def handler(event):
        msg = event.message.message
        print(f"\n📨 Ответ от @TIDAbot:\n{msg[:500]}")
        response_text.append(msg)
        received.set()

    print("\n📤 Отправляем /start в @TIDAbot...")
    try:
        bot_entity = await client.get_entity("TIDAbot")
        await client.send_message(bot_entity, "/start")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        await client.disconnect()
        return

    try:
        await asyncio.wait_for(received.wait(), timeout=20)
        print("\n✅ Соединение работает! TIDA бот отвечает.")
    except asyncio.TimeoutError:
        print("\n⏳ Таймаут — ответа от @TIDAbot не было 20 сек.")
        print("   Возможно бот заблокирован по гео или сессия в бане.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
