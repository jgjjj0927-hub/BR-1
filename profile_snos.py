# coding: utf-8
"""
Brown V2 | profile_snos.py
[ТЕСТ] Жалоба на профиль/аккаунт через messages.ReportRequest с id=[]
Сессии: sessions/ + prem_sessions/
Распределение: каждая сессия жалуется по уникальной паре (категория, подкатегория)
Только для администраторов.
"""

import os
import asyncio
import random
import logging
from telethon import TelegramClient
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

SESSION_FOLDERS = ['sessions', 'prem_sessions']
LOG_FOLDER = 'logs'
os.makedirs(LOG_FOLDER, exist_ok=True)

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
    """Собирает сессии из sessions/ и prem_sessions/"""
    result = []
    for folder in SESSION_FOLDERS:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith('.session'):
                result.append(os.path.join(folder, f.replace('.session', '')))
    return result


def format_log_line(session, target, status):
    now = now_msk().strftime('%H:%M:%S')
    return f'[{now}] {os.path.basename(session)}.session -> {target} - [{status}]'


async def _get_report_tree(target_username: str) -> list[tuple[bytes, bytes]]:
    """
    Подключается одной сессией-разведчиком и строит плоский список пар:
    [(категория, подкатегория), ...]
    Если у категории нет подкатегорий — добавляем пару (категория, b'')
    """
    sessions = _get_sessions()
    if not sessions:
        return []

    scout_path = sessions[0]
    creds = random.choice(API)
    api_id, api_hash = creds.split(':', 1)

    pairs = []
    client = TelegramClient(scout_path, int(api_id), api_hash,
                            system_version='4.16.30-vxCUSTOM')
    try:
        await asyncio.wait_for(client.connect(), timeout=10)
        if not await client.is_user_authorized():
            await client.disconnect()
            return []

        entity = await client.get_entity(target_username)
        peer = await client.get_input_entity(entity)

        # Шаг 1: получаем все категории
        r1 = await client(ReportRequest(peer=peer, id=[], option=b'', message=''))
        if not hasattr(r1, 'options') or not r1.options:
            await client.disconnect()
            return []

        categories = [opt.option for opt in r1.options]
        print(f'[PROFILE] Разведчик: категорий={len(categories)} {categories}', flush=True)

        # Шаг 2: для каждой категории получаем подкатегории
        for cat in categories:
            try:
                r2 = await client(ReportRequest(peer=peer, id=[], option=cat, message=''))
                if hasattr(r2, 'options') and r2.options:
                    subcats = [opt.option for opt in r2.options]
                    print(f'[PROFILE] Категория {cat}: подкатегорий={len(subcats)} {subcats}', flush=True)
                    for sub in subcats:
                        pairs.append((cat, sub))
                else:
                    # Нет подкатегорий — финальный шаг уже на этом уровне
                    pairs.append((cat, b''))
                    print(f'[PROFILE] Категория {cat}: подкатегорий нет (финальная)', flush=True)
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f'[PROFILE] Разведчик: ошибка категории {cat}: {e}', flush=True)
                pairs.append((cat, b''))

        await client.disconnect()
    except Exception as e:
        print(f'[PROFILE] Разведчик ошибка: {e}', flush=True)
        try:
            await client.disconnect()
        except Exception:
            pass

    return pairs


async def _report_session(session_path: str, target_username: str,
                          cat: bytes, sub: bytes) -> str:
    """
    Одна сессия отправляет жалобу с заданной парой (категория, подкатегория).
    """
    creds = random.choice(API)
    api_id, api_hash = creds.split(':', 1)
    session_name = os.path.basename(session_path)

    client = TelegramClient(session_path, int(api_id), api_hash,
                            system_version='4.16.30-vxCUSTOM')
    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=8)
        except asyncio.TimeoutError:
            return 'TIMEOUT'

        if not await client.is_user_authorized():
            await client.disconnect()
            return 'НЕВАЛИД'

        try:
            entity = await client.get_entity(target_username)
            peer = await client.get_input_entity(entity)
        except (UsernameNotOccupiedError, UsernameInvalidError):
            await client.disconnect()
            return 'НЕ НАЙДЕН'
        except Exception as e:
            await client.disconnect()
            return f'ОШИБКА: {str(e)[:40]}'

        # Шаг 1: выбираем категорию
        try:
            await client(ReportRequest(peer=peer, id=[], option=b'', message=''))
        except Exception as e:
            await client.disconnect()
            return f'ОШИБКА ШАГ1: {str(e)[:40]}'

        # Шаг 2: выбираем категорию
        try:
            await client(ReportRequest(peer=peer, id=[], option=cat, message=''))
        except Exception as e:
            await client.disconnect()
            return f'ОШИБКА ШАГ2: {str(e)[:40]}'

        # Шаг 3: выбираем подкатегорию (если есть) или финальный шаг
        if sub:
            try:
                await client(ReportRequest(peer=peer, id=[], option=sub, message=''))
            except Exception as e:
                await client.disconnect()
                return f'ОШИБКА ШАГ3: {str(e)[:40]}'

        await client.disconnect()
        print(f'[PROFILE] [{session_name}] ✅ cat={cat} sub={sub}', flush=True)
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

    sessions = _get_sessions()
    if not sessions:
        await bot.send_message(
            user, '❌ *Нет сессий!*',
            parse_mode='Markdown', reply_markup=keyboards.main_menu
        )
        return

    # Сообщение о начале
    await bot.send_message(
        user,
        f'👤 *\[ТЕСТ\] Profile Report*\n'
        f'*└─ Цель:* `@{target}`\n'
        f'*└─ Сессий:* `{len(sessions)}`\n\n'
        f'⏳ *Строю дерево категорий...*',
        parse_mode='Markdown'
    )

    # Получаем дерево категорий разведчиком
    pairs = await _get_report_tree(target)
    if not pairs:
        await bot.send_message(
            user,
            '❌ *Не удалось получить категории жалоб!*\n'
            '*Проверь username и попробуй снова.*',
            parse_mode='Markdown', reply_markup=keyboards.main_menu
        )
        return

    total = len(sessions)
    print(f'[PROFILE] 🚀 Старт | @{target} | сессий={total} | пар={len(pairs)}', flush=True)

    # Назначаем каждой сессии пару по индексу (по кругу)
    assignments = [(sessions[i], pairs[i % len(pairs)]) for i in range(total)]

    # Запускаем пачками по 8
    BATCH_SIZE = 8
    results = []
    for i in range(0, total, BATCH_SIZE):
        batch = assignments[i:i + BATCH_SIZE]
        batch_results = await asyncio.gather(
            *[_report_session(s, target, cat, sub) for s, (cat, sub) in batch],
            return_exceptions=True
        )
        for (s, _), r in zip(batch, batch_results):
            results.append((s, r))
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
        f'Пар категорий: {len(pairs)}',
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
        f'👤 *\[ТЕСТ\] Profile Report завершён!*\n\n'
        f'🎯 *Цель:* @{target_esc}\n'
        f'🔢 *Пар категорий:* `{len(pairs)}`\n'
        f'🕐 *Время:* {now_str}\n\n'
        f'🟢 *Успешно: {delivered}*\n'
        f'🔴 *Не удалось: {failed}*'
    )
    caption_log = (
        f'👤 *\[ТЕСТ\] Profile-method*\n\n'
        f'🎯 *Цель:* @{target_esc}\n'
        f'👤 *Пользователь:* `{user}` (@{username})\n'
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
