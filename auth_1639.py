"""
auth_1639.py — авторизация +16399517034, сессия сохраняется в sessions/
Запуск: python3 auth_1639.py
"""
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

PHONE    = '+16399517034'
SESSION  = f'sessions/{PHONE.replace("+", "")}'
API_ID   = 24565698
API_HASH = '5a084b434f8505ace703485b9da85040'


async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH, system_version='4.16.30-vxCUSTOM')
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(PHONE)
        code = input('Код из Telegram: ').strip()
        try:
            await client.sign_in(PHONE, code)
        except SessionPasswordNeededError:
            print('⚠️  2FA включена. Попробуй ввести пароль (или Enter чтобы пропустить):')
            pwd = input('2FA пароль: ').strip()
            if pwd:
                await client.sign_in(password=pwd)
            else:
                print('❌ 2FA пропущена — авторизация невозможна без пароля.')
                await client.disconnect()
                return

    me = await client.get_me()
    print(f'✅ Авторизован: {me.first_name} | +{me.phone}')
    print(f'📁 Сессия: {SESSION}.session')
    await client.disconnect()


asyncio.run(main())
