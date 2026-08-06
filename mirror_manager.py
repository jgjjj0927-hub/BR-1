"""
Brown V2 | mirror_manager.py
Запускает зеркальные боты на пользовательских токенах.
Каждое зеркало — полноценная копия основного бота в той же БД.
"""

import asyncio
import logging
from aiogram.utils.exceptions import Unauthorized
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

class MirrorCreateFSM(StatesGroup):
    token = State()


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

    # ─── Callback хендлер зеркала ─────────────────────────────────────────────
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
        elif d == 'free_menu':
            mirror_count = await db.count_user_mirrors(uid)
            free_reports = await db.get_free_reports(uid)
            await mirror_bot.edit_message_caption(
                call.message.chat.id, call.message.message_id,
                caption=(
                    f"🆓 *Бесплатные репорты*\n\n"
                    f"▪️ *Бесплатных репортов: {free_reports}*\n"
                    f"▪️ *Зеркал создано: {mirror_count}/3*\n\n"
                    f"🪞 *Зеркало* — это копия бота на твоём токене\n"
                    f"*└─ Создай бота через @BotFather*\n"
                    f"*└─ Скинь нам токен*\n"
                    f"*└─ Бот запустится и ты получишь +3 репорта*\n\n"
                    f"*Максимум 3 зеркала = 9 бесплатных репортов*"
                ),
                parse_mode="Markdown", reply_markup=keyboards.free_menu_markup
            )
        elif d == 'mirror_create':
            await mirror_bot.send_message(
                call.message.chat.id,
                "🪞 *Создание зеркала*\n\n"
                "*1.* Открой @BotFather\n"
                "*2.* Напиши /newbot\n"
                "*3.* Придумай имя и username боту\n"
                "*4.* Скопируй токен и отправь его сюда:\n\n"
                "*Формат:* `1234567890:ABCdef...`",
                parse_mode="Markdown"
            )
            await MirrorCreateFSM.token.set()
        elif d == 'mirror_list':
            mirrors = await db.get_user_mirrors(uid)
            if not mirrors:
                await mirror_bot.answer_callback_query(call.id, "У вас нет зеркал.", show_alert=True)
                return
            lines = ["🪞 *Ваши зеркала:*\n"]
            for i, m in enumerate(mirrors, 1):
                lines.append(f"*{i}.* `{m['bot_username']}`")
            await mirror_bot.send_message(
                call.message.chat.id,
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=keyboards.back_markup
            )
        else:
            await mirror_bot.answer_callback_query(
                call.id,
                f"➡️ Для использования функций перейди в основной бот: {config.bot_channel_link}",
                show_alert=True
            )

    # ─── FSM создания зеркала внутри зеркала ──────────────────────────────────
    @dp.message_handler(state=MirrorCreateFSM.token, content_types=types.ContentTypes.TEXT)
    async def mirror_create_token(message: types.Message, state: FSMContext):
        uid = message.from_user.id
        new_token = message.text.strip()

        # Если прислали команду — отменяем FSM и обрабатываем как команду
        if new_token.startswith('/'):
            await state.finish()
            if new_token.startswith('/start'):
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
            else:
                await mirror_bot.send_message(uid, "❌ *Отменено.*", parse_mode="Markdown")
            return

        if ':' not in new_token or len(new_token) < 30:
            await state.finish()
            await mirror_bot.send_message(uid, "❌ *Неверный формат токена!*\n*Пример:* `1234567890:ABCdef...`", parse_mode="Markdown")
            return

        await state.finish()
        mirror_count = await db.count_user_mirrors(uid)
        if mirror_count >= MIRROR_LIMIT:
            await mirror_bot.send_message(uid, "❌ *Максимум 3 зеркала!*", parse_mode="Markdown")
            return

        if await db.token_exists(new_token):
            await mirror_bot.send_message(uid, "❌ *Этот токен уже зарегистрирован!*", parse_mode="Markdown")
            return

        wait_msg = await mirror_bot.send_message(uid, "⏳ *Проверяем токен...*", parse_mode="Markdown")
        bot_username = await validate_token(new_token)
        try:
            await mirror_bot.delete_message(uid, wait_msg.message_id)
        except Exception:
            pass

        if not bot_username:
            await mirror_bot.send_message(uid, "❌ *Токен невалидный!* Проверь и попробуй снова.", parse_mode="Markdown")
            return

        await db.add_mirror(uid, new_token, bot_username)
        await start_mirror(new_token)

        # Бонус +1 репорт при 2-м зеркале — только 1 раз
        mirror_count = await db.count_user_mirrors(uid)
        bonus_msg = ""
        if mirror_count >= 2 and not await db.get_mirror_bonus_given(uid):
            await db.add_free_reports(uid, 1)
            await db.set_mirror_bonus_given(uid)
            bonus_msg = "\n🎯 *Бонус: +1 бесплатный репорт за 2 зеркала!*"

        await mirror_bot.send_message(
            uid,
            f"✅ *Зеркало создано!*\n\n"
            f"🤖 *Бот:* `{bot_username}`\n"
            f"📊 *Всего зеркал: {mirror_count}*"
            f"{bonus_msg}\n\n"
            f"*Зеркало уже работает!*",
            parse_mode="Markdown"
        )

    return mirror_bot, dp


async def _run_mirror(token: str):
    """Запускает polling для одного зеркала."""
    mirror_bot, dp = _build_mirror_dispatcher(token)
    try:
        print(f"[MIRROR] 🚀 Запуск зеркала {token[:20]}...", flush=True)
        await mirror_bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling()
    except Unauthorized:
        print(f"[MIRROR] 🚫 Токен невалидный, удаляем из БД: {token[:20]}", flush=True)
        await db.remove_mirror_by_token(token)
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
