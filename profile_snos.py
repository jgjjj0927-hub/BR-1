# coding: utf-8
"""
Brown V2 | profile_snos.py
[ТЕСТ] Жалоба на профиль/аккаунт через messages.ReportRequest с id=[]
Причина: Spam → Defamation/Insult (без текста)
Только для администраторов.
Сессии: sessions/
"""

import os
import asyncio
import random
import logging
from telethon import TelegramClient, functions
from telethon.tl.functions.messages import ReportRequest
from telethon.errors import FloodWaitError, UsernameNotOccupiedError, UsernameInvalidError
from aiogram import types
import config
from config import bot_logs
import keyboards
from utils import now_msk

logger = logging.getLogger(__name__)

bot = None
main_bot = None

session_folder = 'sessions'
os.makedirs(session_folder, exist_ok=True)

LOG_FOLDER = 'logs'
os.makedirs(LOG_FOLDER, exist_ok=True)

# API credentials (те же что в других методах)
API = [
    '24565698:5a084b434f8505ace703485b9da85040',
    '27904162:e7cba879b1c643ba77490bf328df5eab',
    '23037915:50f06f5b2223586fde0d1379ea91ebc7',
    '29512095:0b29a7d42fff002856b9bed64f7ec919',
    '25055016:25edf5b7becebe91a2d61fe8d9d9931b',
    '21156147:90408de329b27f7dd411dff3e601acc6',
    '29840977:e20b6a9fd01cc9055de0a88a183a030b',
    '29412963:3e37e1d05422db9426aa85e617b441ea',
    '23140129:431e5e839aecf4abdce22d7663acffa7',
]


def set_bot_profile(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b


def _get_sessions():
    return [
        os.path.join(session_folder, f.replace('.session', ''))
        for f in os.listdir(session_folder)
        if f.endswith('.session')
    ]


def format_log_line(session, target, status):
    now = now_msk().strftime('%H:%M:%S')
    return f'[{now}] {os.path.basename(session)}.session -> {target} - [{status}]'


async def _report_profile_session(session_path: str, idx: int, target_username: str) -> str:
    """
    Отправляет жалобу на профиль от одной сессии.
    Флоу: messages.report peer=target id=[] option=b'' →
          выбираем Spam → выбираем подкатегорию (Defamation/Insult если есть) →
          отправляем без текста.
    """
    creds = random.choice(API)
    api_id, api_hash = creds.split(':', 1)
    session_name = os.path.basename(session_path)

    try:
        client = TelegramClient(
            session_path, int(api_id), api_hash,
            system_version='4.16.30-vxCUSTOM'
        )
    except Exception as e:
        logger.warning(f'[PROFILE] [{session_name}] open session error: {e}')
        return 'ОШИБКА СЕССИИ'

    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=8)
        except asyncio.TimeoutError:
            return 'TIMEOUT'

        if not await client.is_user_authorized():
            await client.disconnect()
            return 'НЕВАЛИД'

        # Получаем entity цели
        try:
            entity = await client.get_entity(target_username)
        except (UsernameNotOccupiedError, UsernameInvalidError):
            await client.disconnect()
            return 'НЕ НАЙДЕН'
        except Exception as e:
            await client.disconnect()
            return f'ОШИБКА: {str(e)[:40]}'

        peer = await client.get_input_entity(entity)

        # Шаг 1: получаем список категорий
        try:
            r1 = await client(ReportRequest(peer=peer, id=[], option=b'', message=''))
            print(f'[PROFILE] [{session_name}] Шаг1: {type(r1).__name__} options={[o.option for o in r1.options] if hasattr(r1, "options") and r1.options else "нет"}', flush=True)
        except Exception as e:
            logger.warning(f'[PROFILE] [{session_name}] Шаг1 ошибка: {e}')
            await client.disconnect()
            return f'ОШИБКА ШАГ1: {str(e)[:40]}'

        # Выбираем категорию Spam (b'9') или первую доступную
        spam_option = b'9'
        if hasattr(r1, 'options') and r1.options:
            # Ищем Spam
            found = None
            for opt in r1.options:
                text = opt.text.lower() if hasattr(opt, 'text') else ''
                if 'spam' in text:
                    found = opt.option
                    break
            if found:
                spam_option = found
            else:
                spam_option = r1.options[0].option

        # Шаг 2: выбираем категорию Spam
        try:
            r2 = await client(ReportRequest(peer=peer, id=[], option=spam_option, message=''))
            print(f'[PROFILE] [{session_name}] Шаг2: {type(r2).__name__} options={[o.option for o in r2.options] if hasattr(r2, "options") and r2.options else "нет"}', flush=True)
        except Exception as e:
            logger.warning(f'[PROFILE] [{session_name}] Шаг2 ошибка: {e}')
            await client.disconnect()
            return f'ОШИБКА ШАГ2: {str(e)[:40]}'

        # Выбираем подкатегорию: Defamation / Insult / первую доступную
        if hasattr(r2, 'options') and r2.options:
            sub_option = None
            for opt in r2.options:
                text = opt.text.lower() if hasattr(opt, 'text') else ''
                if 'defam' in text or 'insult' in text or 'клевет' in text or 'оскорб' in text:
                    sub_option = opt.option
                    break
            if not sub_option:
                sub_option = r2.options[0].option

            # Шаг 3: подкатегория
            try:
                r3 = await client(ReportRequest(peer=peer, id=[], option=sub_option, message=''))
                print(f'[PROFILE] [{session_name}] Шаг3: {type(r3).__name__}', flush=True)
            except Exception as e:
                logger.warning(f'[PROFILE] [{session_name}] Шаг3 ошибка: {e}')
                await client.disconnect()
                return f'ОШИБКА ШАГ3: {str(e)[:40]}'
        else:
            # Нет подкатегорий — r2 уже финальный результат
            pass

        await client.disconnect()
        logger.info(f'[PROFILE] [{session_name}] ✅ OK')
        print(f'[PROFILE] [{session_name}] ✅ ДОСТАВЛЕНО', flush=True)
        return 'ДОСТАВЛЕНО'

    except FloodWaitError as e:
        print(f'[PROFILE] [{session_name}] 🌊 FLOOD {e.seconds}с', flush=True)
        try:
            await client.disconnect()
        except Exception:
            pass
        return f'FLOOD {e.seconds}s'
    except Exception as e:
        print(f'[PROFILE] [{session_name}] ❌ {str(e)[:80]}', flush=True)
        try:
            await client.disconnect()
        except Exception:
            pass
        return f'ОШИБКА: {str(e)[:50]}'
    finally:
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception:
            pass


async def main_profile_snos(target_link: str, user: int, username: str):
    """Главная функция — жалоба на профиль от всех сессий."""
    sessions = _get_sessions()
    if not sessions:
        await bot.send_message(
            user,
            '❌ *Нет сессий для Profile-метода!*',
            parse_mode='Markdown',
            reply_markup=keyboards.main_menu
        )
        return

    # Нормализуем target
    raw = target_link.strip()
    if raw.startswith('https://t.me/'):
        target = raw.replace('https://t.me/', '').split('/')[0].split('?')[0]
    elif raw.startswith('t.me/'):
        target = raw.replace('t.me/', '').split('/')[0].split('?')[0]
    elif raw.startswith('@'):
        target = raw[1:].split('/')[0]
    else:
        target = raw.split('/')[0].split('?')[0]

    total = len(sessions)
    logger.info(f'[PROFILE] 🚀 Запуск | Цель: @{target} | Сессий: {total}')

    # Пачки по 8
    BATCH_SIZE = 8
    results = []
    for i in range(0, total, BATCH_SIZE):
        batch = sessions[i:i + BATCH_SIZE]
        batch_results = await asyncio.gather(
            *[_report_profile_session(s, i + j, target) for j, s in enumerate(batch)],
            return_exceptions=True
        )
        results.extend(zip(batch, batch_results))
        if i + BATCH_SIZE < total:
            await asyncio.sleep(random.uniform(2, 4))

    # Подсчёт
    delivered = sum(1 for _, r in results if r == 'ДОСТАВЛЕНО')
    failed = total - delivered

    # Лог-файл
    now_str = now_msk().strftime('%d.%m.%Y %H:%M:%S')
    log_lines = [
        'Brown V2 log | profile-method [ТЕСТ]',
        '-' * 42,
        f'Пользователь: {user} (@{username})',
        f'Цель: @{target}',
        f'Время: {now_str}',
        '-' * 42,
    ]
    for session, result in results:
        if isinstance(result, Exception):
            log_lines.append(format_log_line(session, target, f'ИСКЛЮЧЕНИЕ: {str(result)[:50]}'))
        else:
            log_lines.append(format_log_line(session, target, result))
    log_lines += ['-' * 42, f'Успешно: {delivered}', f'Неуспешно: {failed}']

    log_name = f'brown_v2_profile_log_{os.urandom(8).hex()}.txt'
    log_path = os.path.join(LOG_FOLDER, log_name)
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))

    target_esc = target.replace('_', '\\_')
    caption_user = (
        f'👤 *[ТЕСТ] Profile-метод завершён!*\n\n'
        f'🎯 *Цель:* @{target_esc}\n'
        f'🕐 *Время:* {now_str}\n\n'
        f'🟢 *Успешно: {delivered}*\n'
        f'🔴 *Не удалось: {failed}*'
    )
    caption_log = (
        f'👤 *[ТЕСТ] Profile-method*\n\n'
        f'🎯 *Цель:* @{target_esc}\n'
        f'👤 *Пользователь:* {user} (@{username})\n'
        f'🕐 *Время:* {now_str}\n\n'
        f'🟢 *Успешно: {delivered}*\n'
        f'🔴 *Не удалось: {failed}*'
    )

    try:
        await bot.send_document(
            user, types.InputFile(log_path),
            caption=caption_user,
            parse_mode='Markdown',
            reply_markup=keyboards.main_menu
        )
        await main_bot.send_document(
            bot_logs, types.InputFile(log_path),
            caption=caption_log,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f'[PROFILE] Ошибка отправки лога: {e}')

    try:
        os.remove(log_path)
    except Exception:
        pass
