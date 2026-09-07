import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

SESSION = 'user_session'
API_ID = 31467182
API_HASH = '20d357428e67033087cfc123cf954a71'
PHONE = '+33772290110'

async def main():
    if os.path.exists(SESSION + '.session'):
        os.remove(SESSION + '.session')
        print('Старая сессия удалена.')

    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()

    sent = await c.send_code_request(PHONE)
    code = input('Код из Telegram: ').strip()

    try:
        await c.sign_in(PHONE, code, phone_code_hash=sent.phone_code_hash)
    except SessionPasswordNeededError:
        pw = input('2FA пароль: ').strip()
        await c.sign_in(password=pw)

    me = await c.get_me()
    print(f'Успешно! Аккаунт: {me.first_name} (@{me.username})')
    await c.disconnect()

asyncio.run(main())
