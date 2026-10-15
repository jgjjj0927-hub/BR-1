"""
Run once from the MAIN account to download personal chat history.
Saves to EXPORT_PATH so persona_builder can analyze writing style.
"""
import asyncio
import json
import os

from telethon import TelegramClient
from telethon.tl.types import User

import config

MAIN_PHONE = input("Номер основного аккаунта (например +79991234567): ").strip()

# Messages to fetch per chat (more = better persona, slower download)
MSGS_PER_CHAT = 300
# Max chats to scan
MAX_CHATS = 150

SESSION = "main_export_session"


async def main():
    client = TelegramClient(SESSION, config.API_ID, config.API_HASH)
    await client.start(phone=lambda: MAIN_PHONE)

    me = await client.get_me()
    owner_from_id = f"user{me.id}"
    print(f"[export] signed in as {me.first_name} (id={me.id})")

    os.makedirs(config.EXPORT_PATH, exist_ok=True)

    all_chats = []
    chat_count = 0

    async for dialog in client.iter_dialogs():
        if chat_count >= MAX_CHATS:
            break

        entity = dialog.entity
        # Only real users, skip bots / groups / channels
        if not isinstance(entity, User):
            continue
        if entity.bot:
            continue

        chat_id = dialog.id
        contact_name = (entity.first_name or "") + (" " + entity.last_name if entity.last_name else "")
        print(f"[export] fetching '{contact_name}' ...")

        messages = []
        async for msg in client.iter_messages(chat_id, limit=MSGS_PER_CHAT):
            if not msg.text:
                continue
            from_id = f"user{msg.sender_id}" if msg.sender_id else ""
            messages.append({
                "type": "message",
                "from_id": from_id,
                "text": msg.text,
            })

        if messages:
            messages.reverse()  # chronological order
            all_chats.append({
                "type": "personal_chat",
                "id": chat_id,
                "name": contact_name,
                "messages": messages,
            })
            chat_count += 1

    out_path = os.path.join(config.EXPORT_PATH, "result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"chats": {"list": all_chats}}, f, ensure_ascii=False, indent=2)

    total_msgs = sum(len(c["messages"]) for c in all_chats)
    print(f"\n[export] done — {chat_count} chats, {total_msgs} messages")
    print(f"[export] saved to {out_path}")
    print(f"[export] owner from_id: {owner_from_id}")
    print("\nТеперь перезапусти bot.py — он подхватит стиль автоматически.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
