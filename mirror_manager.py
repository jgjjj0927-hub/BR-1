"""
Brown V2 | mirror_manager.py
Зеркальные боты — полный функционал как основной бот.
Callback делегируется в handle_callback из main.py.
"""

import asyncio
import os
import random
import time as _time
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputFile, ParseMode
from aiogram.utils.exceptions import Unauthorized, TerminatedByOtherGetUpdates

import config
import db
import keyboards
from captcha import generate_captcha_text, generate_captcha_image

_running_mirrors: dict[str, asyncio.Task] = {}
_mirror_captcha_codes: dict[int, str] = {}

MIRROR_LIMIT = 999  # без лимита


class MirrorCaptchaFSM(StatesGroup):
    code = State()

class MirrorCreateFSM(StatesGroup):
    token = State()


def _build_mirror_dispatcher(token: str) -> tuple[Bot, Dispatcher]:
    mirror_bot = Bot(token=token)
    storage = MemoryStorage()
    dp = Dispatcher(mirror_bot, storage=storage)

    # ─── /admin команда ───────────────────────────────────────────────────────
    @dp.message_handler(commands=['admin'])
    async def mirror_admin(message: types.Message):
        if message.chat.id not in config.ADMINS:
            return
        from main import admin
        # Подменяем bot в контексте на mirror_bot для ответа
        import main as main_module
        _orig_bot = main_module.bot
        main_module.bot = mirror_bot
        try:
            await admin(message)
        finally:
            main_module.bot = _orig_bot

    # ─── /start ───────────────────────────────────────────────────────────────
    @dp.message_handler(commands=['start'])
    async def mirror_start(message: types.Message):
        uid = message.chat.id
        if await db.is_blocked(uid):
            return
        is_new = not await db.user_exists(uid)
        await db.add_user(uid)
        if not await db.is_verified(uid):
            code = generate_captcha_text()
            _mirror_captcha_codes[uid] = code
            img = generate_captcha_image(code)
            await mirror_bot.send_photo(
                uid, photo=img,
                caption=f"*Привет, {message.from_user.first_name}!*\n\n*Докажи, что ты не робот 🤖*\n*└─ Введи код с картинки:*",
                parse_mode="Markdown")
            await MirrorCaptchaFSM.code.set()
            if is_new:
                args = message.get_args()
                if args and args.startswith("ref_"):
                    async with dp.current_state(user=uid).proxy() as fsm_data:
                        fsm_data['ref_arg'] = args
            return
        await mirror_bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
        pin_msg = await mirror_bot.send_message(
            uid, "📌 *Сохрани нас чтобы не потерять\!* — brown\.xo\.je",
            parse_mode="MarkdownV2")
        try:
            await mirror_bot.pin_chat_message(uid, pin_msg.message_id, disable_notification=True)
        except Exception:
            pass
        await mirror_bot.send_photo(
            uid, photo=open('material/menu.png', 'rb'),
            caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
            parse_mode="MarkdownV2", reply_markup=keyboards.menu)

    # ─── Капча ────────────────────────────────────────────────────────────────
    @dp.message_handler(state=MirrorCaptchaFSM.code)
    async def mirror_captcha(message: types.Message, state: FSMContext):
        uid = message.from_user.id
        if message.text.strip().lower() == _mirror_captcha_codes.get(uid, "").lower():
            fsm_data = await state.get_data()
            await state.finish()
            _mirror_captcha_codes.pop(uid, None)
            await db.set_verified(uid)
            ref_arg = fsm_data.get('ref_arg')
            if ref_arg and ref_arg.startswith("ref_"):
                try:
                    referrer_id = int(ref_arg[4:])
                    if referrer_id != uid and await db.user_exists(referrer_id):
                        await db.set_referrer(uid, referrer_id)
                        new_count = await db.increment_referral_count(referrer_id)
                        await mirror_bot.send_message(
                            referrer_id,
                            f"👥 *По вашей ссылке зарегистрировался новый пользователь!*\n"
                            f"*└─ Всего рефералов: {new_count}*",
                            parse_mode="Markdown")
                except Exception:
                    pass
            await mirror_bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
            pin_msg = await mirror_bot.send_message(
                uid, "📌 *Сохрани нас чтобы не потерять\!* — brown\.xo\.je",
                parse_mode="MarkdownV2")
            try:
                await mirror_bot.pin_chat_message(uid, pin_msg.message_id, disable_notification=True)
            except Exception:
                pass
            await mirror_bot.send_photo(
                uid, photo=open('material/menu.png', 'rb'),
                caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
                parse_mode="MarkdownV2", reply_markup=keyboards.menu)
        else:
            code = generate_captcha_text()
            _mirror_captcha_codes[uid] = code
            await mirror_bot.send_photo(
                uid, photo=generate_captcha_image(code),
                caption="*❌ Неверно! Попробуй ещё раз:*", parse_mode="Markdown")

    # ─── Оплата sub_ ──────────────────────────────────────────────────────────
    @dp.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'))
    async def mirror_sub(callback_query: types.CallbackQuery):
        try:
            from pyCryptoPayAPI import pyCryptoPayAPI
            crypto = pyCryptoPayAPI(api_token=config.CRYPTO)
            user_id = callback_query.from_user.id
            sub_map = {
                "1": ("1", "1", "на 1 день"),
                "3": ("2", "3", "на 3 дня"),
                "7": (4, "7", "на 7 дней"),
                "30": (8, "30", "на 30 дней"),
                "forever": (6, "999", "навсегда"),
                "premupgrade": (5, "1", "Премиум"),
            }
            st = callback_query.data.split('_')[1]
            if st not in sub_map:
                return
            amount, sub_days, pidor = sub_map[st]
            invoice = await asyncio.to_thread(crypto.create_invoice, asset='USDT', amount=amount)
            pay_check = types.InlineKeyboardMarkup(row_width=2)
            pay_check.add(
                types.InlineKeyboardButton("💸 Оплатить", url=invoice['pay_url']),
                types.InlineKeyboardButton("🔍 Проверить",
                    callback_data=f'check_status_{invoice["invoice_id"]}_{st}_{sub_days}'))
            pay_check.add(keyboards.back)
            await mirror_bot.edit_message_caption(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                caption=f">⚙️ *Покупка*\n*└─ Вы покупаете: {pidor}*\n*└─ Вы платите: {amount}$*",
                parse_mode="MarkdownV2", reply_markup=pay_check)
        except Exception as e:
            print(f"[MIRROR] sub: {e}")

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith('check_status_'))
    async def mirror_check_status(callback_query: types.CallbackQuery):
        try:
            from pyCryptoPayAPI import pyCryptoPayAPI
            crypto = pyCryptoPayAPI(api_token=config.CRYPTO)
            parts = callback_query.data.split('_')
            invoice_id, sub_type, sub_days = parts[2], parts[3], parts[4]
            user_id = callback_query.from_user.id
            old_invoice = await asyncio.to_thread(crypto.get_invoices, invoice_ids=invoice_id)
            if old_invoice['items'][0]['status'] != "paid":
                await mirror_bot.send_message(user_id, "❌ *Оплата не получена!*", parse_mode=ParseMode.MARKDOWN)
                return
            await mirror_bot.edit_message_caption(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                caption=">⚙️ *Спасибо за заказ*", parse_mode="MarkdownV2",
                reply_markup=keyboards.back_markup)
            if sub_type != "premupgrade":
                new_date = (datetime.now() + timedelta(days=int(sub_days))).strftime("%Y-%m-%d %H:%M:%S")
                await db.set_subscribe(user_id, new_date)
                referrer_id = await db.get_referrer_id(user_id)
                if referrer_id:
                    bonus_days = max(1, int(int(sub_days) * 0.1))
                    await db.set_subscribe(referrer_id,
                        (datetime.now() + timedelta(days=bonus_days)).strftime("%Y-%m-%d %H:%M:%S"))
                    await mirror_bot.send_message(referrer_id,
                        f"💰 *Реферальный бонус!*\n*└─ +{bonus_days} день подписки*",
                        parse_mode="Markdown")
            else:
                await db.set_premium(user_id, 1)
        except Exception as e:
            print(f"[MIRROR] check_status: {e}")

    # ─── Главный callback — делегируем в handle_callback из main.py ───────────
    @dp.callback_query_handler(lambda call: True, state='*')
    async def mirror_callback(call: types.CallbackQuery, state: FSMContext):
        from main import handle_callback
        await handle_callback(call, mirror_bot, dp, state)

    # ─── FSM создания зеркала ─────────────────────────────────────────────────
    @dp.message_handler(state=MirrorCreateFSM.token, content_types=types.ContentTypes.TEXT)
    async def mirror_create_token(message: types.Message, state: FSMContext):
        uid = message.from_user.id
        new_token = message.text.strip()

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
                await mirror_bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
                    caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
                    parse_mode="MarkdownV2", reply_markup=keyboards.menu)
            else:
                await mirror_bot.send_message(uid, "❌ *Отменено.*", parse_mode="Markdown")
            return

        if ':' not in new_token or len(new_token) < 30:
            await state.finish()
            await mirror_bot.send_message(uid,
                "❌ *Неверный формат токена!*\n*Пример:* `1234567890:ABCdef...`",
                parse_mode="Markdown")
            return

        await state.finish()
        mirror_count = await db.count_user_mirrors(uid)

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
            await mirror_bot.send_message(uid,
                "❌ *Токен невалидный!* Проверь и попробуй снова.", parse_mode="Markdown")
            return

        await db.add_mirror(uid, new_token, bot_username)
        await start_mirror(new_token)

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
            parse_mode="Markdown")

    # ─── FSM хендлеры — все методы работают через зеркало ────────────────────

    @dp.message_handler(state='*', content_types=types.ContentTypes.TEXT)
    async def mirror_fsm_router(message: types.Message, state: FSMContext):
        """Перенаправляет все текстовые FSM состояния в обработчики main.py"""
        current_state = await state.get_state()
        if current_state is None:
            return

        from main import (
            send_web_reports, get_mail_subject, start_bulk_email,
            botnet_step1_normal, botnet_step1_premium, bot_snos_step1,
            mirror_token_received, enter_promo, stress_step1,
            add_sub_uid, add_sub_days, clear_sub_uid,
            add_prem_uid, clear_prem_uid, sendall,
            admin_block_user, admin_unblock_user,
            admin_add_reports_uid, admin_add_reports_amount,
            admin_remove_reports_uid, admin_remove_reports_amount,
            WaitTextFSM, WaitMailTopicFSM, WaitMailTextFSM,
            WaitLinkFSM, WaitLinkPREMFSM, WaitBotLinkFSM,
            WaitMirrorTokenFSM, WaitPromoFSM, WaitStressFSM,
            AddSubscribeFSM, ClearSubscribeFSM,
            AddPremFSM, ClearPremFSM, WaitTextZFSM,
            BlockUserFSM, UnblockUserFSM,
            AdminAddReportsFSM, AdminRemoveReportsFSM,
        )

        handlers = {
            WaitTextFSM.text.state: send_web_reports,
            WaitMailTopicFSM.topic.state: get_mail_subject,
            WaitMailTextFSM.text.state: start_bulk_email,
            WaitLinkFSM.link.state: botnet_step1_normal,
            WaitLinkPREMFSM.link.state: botnet_step1_premium,
            WaitBotLinkFSM.link.state: bot_snos_step1,
            WaitMirrorTokenFSM.token.state: mirror_token_received,
            WaitPromoFSM.promo.state: enter_promo,
            WaitStressFSM.link.state: stress_step1,
            AddSubscribeFSM.user_id.state: add_sub_uid,
            AddSubscribeFSM.days.state: add_sub_days,
            ClearSubscribeFSM.user_id.state: clear_sub_uid,
            AddPremFSM.user_id.state: add_prem_uid,
            ClearPremFSM.user_id.state: clear_prem_uid,
            WaitTextZFSM.text.state: sendall,
            BlockUserFSM.user_id.state: admin_block_user,
            UnblockUserFSM.user_id.state: admin_unblock_user,
            AdminAddReportsFSM.user_id.state: admin_add_reports_uid,
            AdminAddReportsFSM.amount.state: admin_add_reports_amount,
            AdminRemoveReportsFSM.user_id.state: admin_remove_reports_uid,
            AdminRemoveReportsFSM.amount.state: admin_remove_reports_amount,
        }

        handler = handlers.get(current_state)
        if handler:
            await handler(message, state)

    return mirror_bot, dp


async def _run_mirror(token: str):
    mirror_bot, dp = _build_mirror_dispatcher(token)
    try:
        print(f"[MIRROR] 🚀 Запуск зеркала {token[:20]}...", flush=True)
        # Сначала закрываем все предыдущие соединения — сбрасываем webhook и старые сессии
        await mirror_bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(3)  # ждём 3с чтобы Telegram завершил старые polling соединения
        await dp.start_polling()
    except Unauthorized:
        print(f"[MIRROR] 🚫 Токен невалидный, удаляем: {token[:20]}", flush=True)
        await db.remove_mirror_by_token(token)
    except TerminatedByOtherGetUpdates:
        print(f"[MIRROR] ⚠️ Конфликт для {token[:20]}, повторная попытка через 5с...", flush=True)
        _running_mirrors.pop(token, None)
        await asyncio.sleep(5)
        await start_mirror(token)
        return
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
    if token in _running_mirrors:
        return
    task = asyncio.ensure_future(_run_mirror(token))
    _running_mirrors[token] = task
    await asyncio.sleep(0.1)


async def start_all_mirrors():
    tokens = await db.get_all_mirror_tokens()
    print(f"[MIRROR] 📦 Загружаем {len(tokens)} зеркал из БД...", flush=True)
    for token in tokens:
        await start_mirror(token)


async def validate_token(token: str) -> str | None:
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
