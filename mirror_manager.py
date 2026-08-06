"""
Brown V2 | mirror_manager.py
Запускает зеркальные боты на пользовательских токенах.
Каждое зеркало — полноценная копия основного бота в той же БД.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InputFile
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import db
import keyboards
import config
from captcha import generate_captcha_text, generate_captcha_image

_running_mirrors: dict[str, asyncio.Task] = {}  # token → asyncio Task
_mirror_captcha_codes: dict[int, str] = {}

MIRROR_LIMIT = 3


class MirrorCaptchaFSM(StatesGroup):
    code = State()


def _build_mirror_dispatcher(token: str) -> tuple[Bot, Dispatcher]:
    """Создаёт Bot + Dispatcher для зеркала."""
    mirror_bot = Bot(token=token)
    storage = MemoryStorage()
    dp = Dispatcher(mirror_bot, storage=storage)

    # ─── /start ───────────────────────────────────────────────────────────────
    @dp.message_handler(commands=['start'])
    async def mirror_start(message: types.Message):
        uid = message.chat.id
        await db.add_user(uid)
        if not await db.is_verified(uid):
            code = generate_captcha_text()
            _mirror_captcha_codes[uid] = code
            img = generate_captcha_image(code)
            await mirror_bot.send_photo(uid, photo=img,
                caption=f"*Привет, {message.from_user.first_name}!*\n\n*Докажи, что ты не робот 🤖*\n*└─ Введи код с картинки:*",
                parse_mode="Markdown")
            await MirrorCaptchaFSM.code.set()
            return
        await mirror_bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
        pin_msg = await mirror_bot.send_message(uid,
            "📌 *Сохрани нас чтобы не потерять\!* — brown\.xo\.je",
            parse_mode="MarkdownV2")
        try:
            await mirror_bot.pin_chat_message(uid, pin_msg.message_id, disable_notification=True)
        except Exception:
            pass
        await mirror_bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
            caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
            parse_mode="MarkdownV2", reply_markup=keyboards.menu)

    @dp.message_handler(state=MirrorCaptchaFSM.code)
    async def mirror_captcha(message: types.Message, state: FSMContext):
        uid = message.from_user.id
        if message.text.strip().lower() == _mirror_captcha_codes.get(uid, "").lower():
            await state.finish()
            _mirror_captcha_codes.pop(uid, None)
            await db.set_verified(uid)
            await mirror_bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
            pin_msg = await mirror_bot.send_message(uid,
                "📌 *Сохрани нас чтобы не потерять\!* — brown\.xo\.je",
                parse_mode="MarkdownV2")
            try:
                await mirror_bot.pin_chat_message(uid, pin_msg.message_id, disable_notification=True)
            except Exception:
                pass
            await mirror_bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
                caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
                parse_mode="MarkdownV2", reply_markup=keyboards.menu)
        else:
            code = generate_captcha_text()
            _mirror_captcha_codes[uid] = code
            await mirror_bot.send_photo(uid, photo=generate_captcha_image(code),
                caption="*❌ Неверно! Попробуй ещё раз:*", parse_mode="Markdown")

    # ─── Все callback_query перенаправляем в основной бот через redirect ──────
    # Зеркало имеет своё меню, но функции используют общую БД
    @dp.callback_query_handler(lambda call: True, state='*')
    async def mirror_callback(call: types.CallbackQuery, state: FSMContext):
        uid = call.from_user.id
        if await db.is_blocked(uid):
            return
        if not await db.user_exists(uid):
            await mirror_bot.send_message(uid, "*Пропишите /start*", parse_mode="Markdown")
            return

        d = call.data
        if d == 'back':
            await mirror_bot.edit_message_caption(
                call.message.chat.id, call.message.message_id,
                caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
                parse_mode="MarkdownV2", reply_markup=keyboards.menu)
        elif d == 'close':
            await mirror_bot.delete_message(call.message.chat.id, call.message.message_id)
        elif d == 'go_to_main_menu':
            await mirror_bot.delete_message(call.message.chat.id, call.message.message_id)
            await mirror_bot.send_photo(call.message.chat.id, photo=open('material/menu.png', 'rb'),
                caption='>*Добро пожаловать в Brown V2\!*', parse_mode="MarkdownV2", reply_markup=keyboards.menu)
        else:
            # Всё остальное — предлагаем перейти в основной бот
            await mirror_bot.answer_callback_query(
                call.id,
                f"➡️ Для использования функций перейди в основной бот: {config.bot_channel_link}",
                show_alert=True
            )

    return mirror_bot, dp


async def _run_mirror(token: str):
    """Запускает polling для одного зеркала."""
    mirror_bot, dp = _build_mirror_dispatcher(token)
    try:
        print(f"[MIRROR] 🚀 Запуск зеркала {token[:20]}...", flush=True)
        # Сбрасываем webhook и пропускаем накопившиеся апдейты
        await mirror_bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling()
    except Exception as e:
        print(f"[MIRROR] ❌ Ошибка зеркала {token[:20]}: {e}", flush=True)
    finally:
        try:
            await dp.storage.close()
            await dp.storage.wait_closed()
        except Exception:
            pass
        try:
            session = await mirror_bot.get_session()
            await session.close()
        except Exception:
            pass
        _running_mirrors.pop(token, None)
        print(f"[MIRROR] 🔴 Зеркало {token[:20]} остановлено", flush=True)


async def start_mirror(token: str):
    """Запускает зеркало если оно ещё не запущено."""
    if token in _running_mirrors:
        return
    # Используем asyncio.ensure_future чтобы задача запустилась
    # после завершения текущего хендлера, не блокируя его
    task = asyncio.ensure_future(_run_mirror(token))
    _running_mirrors[token] = task
    # Даём event loop шанс переключиться на новую задачу
    await asyncio.sleep(0)


async def start_all_mirrors():
    """При старте основного бота поднимает все зеркала из БД."""
    tokens = await db.get_all_mirror_tokens()
    print(f"[MIRROR] 📦 Загружаем {len(tokens)} зеркал из БД...", flush=True)
    for token in tokens:
        await start_mirror(token)


async def validate_token(token: str) -> str | None:
    """
    Проверяет токен через Bot API getMe.
    Возвращает @username бота или None если токен невалидный.
    """
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return "@" + data["result"]["username"]
                return None
    except Exception:
        return None
