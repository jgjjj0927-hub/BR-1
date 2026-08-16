from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode, InputFile, Message
from datetime import datetime, timedelta
from pyCryptoPayAPI import pyCryptoPayAPI
import config
import keyboards
import time
import os
import random
import asyncio
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import aiohttp
from web_snos import web, generate_log_filename
from mail_snos import send_bulk_emails, load_mails
from botnet_snos import extract_username_and_message_id, main as botnet_main, set_bot as botnet_set_bot
from botnet_snos_premium import extract_username_and_message_id2, main2 as botnet_main2, set_bot2 as botnet_set_bot2
from bot_snos import main_bot_snos, set_bot_snos
from captcha import generate_captcha_text, generate_captcha_image
from mirror_manager import validate_token, start_mirror, start_all_mirrors
from bot_stress import main_bot_stress, set_bot_stress
from channel_snos import main_channel_snos, set_bot_channel, CHANNEL_REASON_LABELS
from code_snos import main_code_snos, set_bot_code
from aureport_snos import main_aureport, set_bot_aureport
from tida_snos import main_tida, set_bot_tida
from bank_snos import process_bank_report, set_bot_bank
import db

channel_id = config.channel_id
channel2_id = config.channel2_id
admins = config.ADMINS
admins2 = [8120267775]
no_kd = config.NO_KD
bot_logs = config.bot_logs
report_count333 = 200

bot = Bot(token=config.TOKEN)
bot_username = "@Brrown_V2bot"
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
crypto = pyCryptoPayAPI(api_token=config.CRYPTO, result_as_class=False)
session_folder = 'sessions'
session_folder_prem = 'prem_sessions'
sessions = [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]

last_used_web = {}
last_used_mail = {}
last_used_botnet = {}
last_used_botnet2 = {}
last_used_bot_snos = {}
last_used_stress = {}
last_used_channel = {}
last_used_aureport = {}
last_used_tida = {}
last_used_bank = {}
user_requests = {}
REQUEST_LIMIT = 3
TIME_FRAME = 1
_captcha_codes: dict = {}

menu = keyboards.menu
back_markup = keyboards.back_markup
admin_markup = keyboards.admin_markup
shop_markup = keyboards.shop_markup
check_markup = keyboards.check_markup
info_markup = keyboards.info_markup
functions = keyboards.functions
del_message = keyboards.del_message
del_message2 = keyboards.del_message2
main_menu = keyboards.main_menu

# ─── Helpers ──────────────────────────────────────────────────────────────────

async def check_user_in_db(user_id):
	return await db.user_exists(user_id)

async def is_blocked(user_id: int) -> bool:
	return await db.is_blocked(user_id)

async def block_user(user_id: int):
	await db.block_user(user_id)

async def is_verified(user_id: int) -> bool:
	return await db.is_verified(user_id)

async def set_verified(user_id: int):
	await db.set_verified(user_id)

def check_rate_limit(user_id: int) -> bool:
	return False  # авто-блокировка отключена, блокировка только вручную через админ

async def subsribe_channel(user_id, chan):
	try:
		chat_member = await bot.get_chat_member(chan, user_id)
		return chat_member.status != 'left'
	except Exception as e:
		err = str(e).lower()
		# Если бот не авторизован или нет доступа к каналу — блокируем
		if 'unauthorized' in err or 'forbidden' in err or 'chat not found' in err:
			return False
		return True  # другие ошибки (сеть и т.д.) — не блокируем

async def check_subscription(uid: int, bot_instance=None) -> bool:
	"""Проверяет подписку на оба канала. Всегда через основной bot."""
	sub1 = await subsribe_channel(uid, channel_id)
	sub2 = await subsribe_channel(uid, channel2_id)
	return sub1 and sub2

async def send_subscribe_required(uid: int, bot_instance=None):
	"""Отправляет сообщение с требованием подписки."""
	b = bot_instance or bot
	try:
		import time as _time
		expire = int(_time.time()) + 60
		link1 = await bot.create_chat_invite_link(channel_id, expire_date=expire, member_limit=1)
		link2 = await bot.create_chat_invite_link(channel2_id, expire_date=expire, member_limit=1)
		invite1 = link1.invite_link
		invite2 = link2.invite_link
	except Exception:
		invite1 = config.bot_channel_link
		invite2 = config.bot_channel2_link
	markup = types.InlineKeyboardMarkup(row_width=1)
	markup.add(
		types.InlineKeyboardButton("[1️⃣] Подпишись (1 мин)", url=invite1),
		types.InlineKeyboardButton("[2️⃣] Подпишись (1 мин)", url=invite2),
		types.InlineKeyboardButton("[🔎] Проверить", callback_data='start_check_sub')
	)
	await b.send_message(uid,
		"*⚠️ Для использования бота подпишитесь на каналы!*\n*└─ Ссылки действуют 1 минуту*",
		parse_mode="Markdown", reply_markup=markup)

# ─── FSM ──────────────────────────────────────────────────────────────────────

class AddSubscribeFSM(StatesGroup):
	user_id = State()
	days = State()

class ClearSubscribeFSM(StatesGroup):
	user_id = State()

class WaitLinkFSM(StatesGroup):
	link = State()

class WaitMailTextFSM(StatesGroup):
	text = State()

class WaitMailTopicFSM(StatesGroup):
	topic = State()

class WaitTextFSM(StatesGroup):
	text = State()

class WaitTextZFSM(StatesGroup):
	text = State()

class WaitPromoFSM(StatesGroup):
	promo = State()

class ClearPremFSM(StatesGroup):
	user_id = State()

class AddPremFSM(StatesGroup):
	user_id = State()

class WaitLinkPREMFSM(StatesGroup):
	link = State()

class WaitBotLinkFSM(StatesGroup):
	link = State()
	reason = State()

class WaitCaptchaFSM(StatesGroup):
	code = State()

class BlockUserFSM(StatesGroup):
	user_id = State()

class UnblockUserFSM(StatesGroup):
	user_id = State()

class WaitMirrorTokenFSM(StatesGroup):
	token = State()

class WaitStressFSM(StatesGroup):
	link = State()

class WaitChannelFSM(StatesGroup):
	link = State()

class WaitPhoneFSM(StatesGroup):
	phone = State()

class WaitAuReportFSM(StatesGroup):
	link = State()

class WaitTidaFSM(StatesGroup):
	link = State()
	text = State()

class WaitBankFSM(StatesGroup):
	card = State()
	bank_key = State()

class AdminAddReportsFSM(StatesGroup):
	user_id = State()
	amount = State()

class AdminRemoveReportsFSM(StatesGroup):
	user_id = State()
	amount = State()

class DeleteUserFSM(StatesGroup):
	user_id = State()

class CreatePromoFSM(StatesGroup):
	promo_type = State()
	code = State()
	days = State()
	activations = State()

global bot_status
bot_status = 1

# ─── Команды ──────────────────────────────────────────────────────────────────

@dp.message_handler(commands=['on'])
async def on(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		bot_status = 1
		await bot.send_message(message.chat.id, "🟢 *Включен!*", parse_mode=ParseMode.MARKDOWN)
		await bot.send_message(bot_logs, "🟢 *Включен!*", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['off'])
async def off(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		bot_status = 0
		await bot.send_message(message.chat.id, "🔴 *Выключен!*", parse_mode=ParseMode.MARKDOWN)
		await bot.send_message(bot_logs, "🔴 *Выключен!*", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['bot'])
async def status(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		text = "🟢 *Включен!*" if bot_status == 1 else "🔴 *Выключен!*"
		await bot.send_message(message.chat.id, text, parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['admin'])
async def admin(message):
	if message.chat.id in admins:
		users_count = await db.get_users_count()
		sessions_count = len(os.listdir(session_folder)) if os.path.exists(session_folder) else 0
		sessions_count_prem = len(os.listdir(session_folder_prem)) if os.path.exists(session_folder_prem) else 0
		subscribers_count = await db.get_subscribers_count()
		mirrors_count = await db.get_mirrors_count()
		reports_users_count = await db.get_users_with_reports_count()
		try:
			with open("mails.txt", "r", encoding="utf-8") as f:
				mails_count = len([l for l in f if l.strip()])
		except FileNotFoundError:
			mails_count = 0
		text = (
			">🤖 *Админ меню:*\n\n📊 *Статистика:*\n"
			f"*├─👥 Всего пользователей:* `{users_count}`\n"
			f"*├─💳 С подпиской:* `{subscribers_count}`\n"
			f"*├─🎯 С репортами:* `{reports_users_count}`\n"
			f"*├─🪞 Зеркал:* `{mirrors_count}`\n"
			f"*├─🕒 Сессий в ботнете:* `{sessions_count}`\n"
			f"*├─👑 Сессий в премиум ботнете:* `{sessions_count_prem}`\n"
			f"*├─🌐 Web\-Reports:* `{report_count333}`\n"
			f"*└─✉️ Почт добавлено:* `{mails_count}`\n\n"
			"*/promo PROMOCODE DAYS ACTIVATIONS \- создать промокод*\n"
			"*/on \- включить бота*\n*/off \- выключить бота*\n"
			"*/addwl ID \- добавить в вайтлист*\n"
			"*/addtargetwl @username \- добавить цель в WL*\n"
			"*/rmtargetwl @username \- убрать цель из WL*\n"
			"*/listtargetwl \- список целей WL*"
		)
		await bot.send_message(message.chat.id, text, reply_markup=keyboards.admin_markup, parse_mode="MarkdownV2")

@dp.message_handler(commands=['addwl'])
async def addwl(message: types.Message):
	if message.from_user.id not in admins:
		return
	parts = message.text.split()
	if len(parts) != 2:
		await message.answer("❗️ */addwl ID*", parse_mode=ParseMode.MARKDOWN)
		return
	try:
		wl_user = int(parts[1])
	except ValueError:
		await message.answer("❗️ *ID должно быть числом!*", parse_mode=ParseMode.MARKDOWN)
		return
	await db.add_to_whitelist(wl_user)
	await message.answer(f"*📄 {wl_user} добавлен в вайтлист!*", parse_mode=ParseMode.MARKDOWN)
	await bot.send_message(bot_logs, f"*📄 {wl_user} добавлен в вайтлист!*", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['addtargetwl'])
async def addtargetwl(message: types.Message):
	"""Добавить username/channel в белый список целей. /addtargetwl @username"""
	if message.from_user.id not in admins:
		return
	parts = message.text.split()
	if len(parts) != 2:
		await message.answer("❗️ */addtargetwl @username*\n*Пример: /addtargetwl @durov*", parse_mode=ParseMode.MARKDOWN)
		return
	pattern = parts[1].lstrip('@').lower()
	await db.add_target_whitelist(pattern, message.from_user.id)
	await message.answer(f"✅ *`@{pattern}` добавлен в белый список целей!*\n*└─ Жалобы на цели начинающиеся с* `{pattern}` *будут заблокированы.*", parse_mode=ParseMode.MARKDOWN)
	await bot.send_message(bot_logs, f"🛡 *Белый список целей:* `@{pattern}` *добавлен* `{message.from_user.id}`", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['rmtargetwl'])
async def rmtargetwl(message: types.Message):
	"""Удалить username/channel из белого списка целей. /rmtargetwl @username"""
	if message.from_user.id not in admins:
		return
	parts = message.text.split()
	if len(parts) != 2:
		await message.answer("❗️ */rmtargetwl @username*\n*Пример: /rmtargetwl @durov*", parse_mode=ParseMode.MARKDOWN)
		return
	pattern = parts[1].lstrip('@').lower()
	await db.remove_target_whitelist(pattern)
	await message.answer(f"🗑 *`@{pattern}` удалён из белого списка целей!*", parse_mode=ParseMode.MARKDOWN)
	await bot.send_message(bot_logs, f"🗑 *Белый список целей:* `@{pattern}` *удалён* `{message.from_user.id}`", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['listtargetwl'])
async def listtargetwl(message: types.Message):
	"""Показать все записи белого списка целей."""
	if message.from_user.id not in admins:
		return
	patterns = await db.get_target_whitelist()
	if not patterns:
		await message.answer("📋 *Белый список целей пуст.*", parse_mode=ParseMode.MARKDOWN)
		return
	lines = ["📋 *Белый список целей:*\n"]
	for p in patterns:
		lines.append(f"• `@{p}`")
	await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ─── Подписки / оплата ────────────────────────────────────────────────────────

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'), state='*')
async def handle_subscription(callback_query: types.CallbackQuery):
	try:
		user_id = callback_query.from_user.id
		if not await check_user_in_db(user_id):
			return
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
		pay_url = invoice['pay_url']
		invoice_id = invoice['invoice_id']
		pay_check = types.InlineKeyboardMarkup(row_width=2)
		pay_check.add(
			types.InlineKeyboardButton("💸 Оплатить", url=pay_url),
			types.InlineKeyboardButton("🔍 Проверить", callback_data=f'check_status_{invoice_id}_{st}_{sub_days}')
		)
		pay_check.add(keyboards.back)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=f">⚙️ *Покупка*\n*└─ Вы покупаете: {pidor}*\n*└─ Вы платите: {amount}$*",
			parse_mode="MarkdownV2", reply_markup=pay_check
		)
	except Exception as e:
		print(f"handle_subscription: {e}")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('check_status_'), state='*')
async def check_status_callback(callback_query: types.CallbackQuery):
	try:
		parts = callback_query.data.split('_')
		invoice_id, sub_type, sub_days = parts[2], parts[3], parts[4]
		user_id = callback_query.from_user.id
		if not await check_user_in_db(user_id):
			return
		old_invoice = await asyncio.to_thread(crypto.get_invoices, invoice_ids=invoice_id)
		if old_invoice['items'][0]['status'] != "paid":
			await bot.send_message(user_id, "❌ *Оплата не получена!*", parse_mode=ParseMode.MARKDOWN)
			return
		# Защита от повторного начисления
		if await db.is_invoice_used(invoice_id):
			await bot.send_message(user_id, "✅ *Этот платёж уже был обработан!*", parse_mode=ParseMode.MARKDOWN)
			return
		await db.mark_invoice_used(invoice_id, user_id)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=">⚙️ *Спасибо за заказ*", parse_mode="MarkdownV2", reply_markup=back_markup
		)
		if sub_type != "premupgrade":
			new_date = (datetime.now() + timedelta(days=int(sub_days))).strftime("%Y-%m-%d %H:%M:%S")
			await db.set_subscribe(user_id, new_date)
			await bot.send_message(bot_logs, f"💳 *Оплата подписки* `{user_id}` *до* `{new_date}`", parse_mode="Markdown")
			# Реферальный бонус — 10% от дней подписки рефереру
			referrer_id = await db.get_referrer_id(user_id)
			if referrer_id:
				bonus_days = max(1, int(int(sub_days) * 0.1))
				ref_new_date = (datetime.now() + timedelta(days=bonus_days)).strftime("%Y-%m-%d %H:%M:%S")
				await db.set_subscribe(referrer_id, ref_new_date)
				await bot.send_message(
					referrer_id,
					f"💰 *Реферальный бонус!*\n"
					f"*└─ Ваш реферал купил подписку*\n"
					f"*└─ Вам начислено: +{bonus_days} день подписки*",
					parse_mode="Markdown"
				)
		else:
			await db.set_premium(user_id, 1)
			await bot.send_message(bot_logs, f"💳 *Premium* `{user_id}`", parse_mode="Markdown")
	except Exception as e:
		print(f"check_status_callback: {e}")

# ─── Промокоды ────────────────────────────────────────────────────────────────

@dp.message_handler(commands=['promo'])
async def promo_cmd(message: Message):
	if message.from_user.id not in admins:
		return
	parts = message.text.split()
	if len(parts) != 4:
		await message.answer("*/promo PROMOCODE DAYS ACTIVATIONS*", parse_mode="Markdown")
		return
	code, days, activations = parts[1], int(parts[2]), int(parts[3])
	try:
		await db.create_promo(code, days, activations)
		await message.answer(f"💎 Создан промокод `{code}` на {days} дней, {activations} активаций", parse_mode="Markdown")
	except Exception:
		await message.answer(f"❗️ Промокод `{code}` уже существует!", parse_mode="Markdown")

# ─── /start с капчей ──────────────────────────────────────────────────────────

@dp.message_handler(commands=['start'], state='*')
async def welcome(message: types.Message, state: FSMContext):
	# Сбрасываем любое активное FSM состояние при /start
	current = await state.get_state()
	if current is not None:
		await state.finish()
	if await is_blocked(message.from_user.id):
		return
	if check_rate_limit(message.from_user.id):
		await block_user(message.from_user.id)
		await message.reply("Превысили лимит запросов, заблокированы.")
		return
	uid = message.chat.id
	is_new = not await db.user_exists(uid)
	await db.add_user(uid, message.from_user.username or '')

	if not await is_verified(uid):
		try:
			code = generate_captcha_text()
			_captcha_codes[uid] = code
			img = generate_captcha_image(code)
			await bot.send_photo(uid, photo=img,
				caption=f"*Привет, {message.from_user.first_name}!*\n\n*Докажи, что ты не робот 🤖*\n*└─ Введи код с картинки:*",
				parse_mode="Markdown")
		except Exception as e:
			print(f"[CAPTCHA] Ошибка генерации: {e}", flush=True)
			await bot.send_message(uid, "❌ *Ошибка генерации капчи. Попробуйте /start снова.*", parse_mode="Markdown")
			return
		# Сохраняем реф-аргумент в FSM — применим только после прохождения капчи
		await WaitCaptchaFSM.code.set()
		if is_new:
			args = message.get_args()
			if args and args.startswith("ref_"):
				async with dp.current_state(user=uid).proxy() as fsm_data:
					fsm_data['ref_arg'] = args
		return
	await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
	# Проверяем подписку перед показом меню
	if not await check_subscription(uid):
		await send_subscribe_required(uid)
		return
	await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
		caption='>*Добро пожаловать в Brown V2\!*\n\n*Меню:*',
		parse_mode="MarkdownV2", reply_markup=menu)

@dp.message_handler(state=WaitCaptchaFSM.code)
async def check_captcha(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	if message.text.strip().lower() == _captcha_codes.get(uid, "").lower():
		fsm_data = await state.get_data()
		await state.finish()
		_captcha_codes.pop(uid, None)
		await set_verified(uid)

		# Реферальная логика — только после прохождения капчи
		ref_arg = fsm_data.get('ref_arg')
		if ref_arg and ref_arg.startswith("ref_"):
			try:
				referrer_id = int(ref_arg[4:])
				if referrer_id != uid and await db.user_exists(referrer_id):
					await db.set_referrer(uid, referrer_id)
					new_count = await db.increment_referral_count(referrer_id)
					await bot.send_message(
						referrer_id,
						f"👥 *По вашей ссылке зарегистрировался новый пользователь!*\n"
						f"*└─ Всего рефералов: {new_count}*",
						parse_mode="Markdown"
					)
			except (ValueError, Exception):
				pass

		await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
		# Проверяем подписку после капчи
		if not await check_subscription(uid):
			await send_subscribe_required(uid)
			return
		# Закреплённое сообщение после капчи
		await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
			caption='>*Добро пожаловать в Brown V2\!*\n\n*Меню:*',
			parse_mode="MarkdownV2", reply_markup=menu)
	else:
		try:
			code = generate_captcha_text()
			_captcha_codes[uid] = code
			await bot.send_photo(uid, photo=generate_captcha_image(code),
				caption="*❌ Неверно! Попробуй ещё раз:*", parse_mode="Markdown")
		except Exception as e:
			print(f"[CAPTCHA] Ошибка повторной генерации: {e}", flush=True)
			await bot.send_message(uid, "❌ *Ошибка генерации капчи. Попробуйте /start снова.*", parse_mode="Markdown")

# ─── Проверка подписки по кнопке ──────────────────────────────────────────────

@dp.callback_query_handler(lambda c: c.data == 'start_check_sub', state='*')
async def start_check_sub_callback(call: types.CallbackQuery):
	uid = call.from_user.id
	if await check_subscription(uid):
		try:
			await bot.delete_message(uid, call.message.message_id)
		except Exception:
			pass
		await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
		await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
			caption='>*Добро пожаловать в Brown V2\!*\n\n*Меню:*',
			parse_mode="MarkdownV2", reply_markup=menu)
	else:
		await bot.answer_callback_query(call.id, "❌ Вы ещё не подписались!", show_alert=True)

# ─── Главный callback хендлер ─────────────────────────────────────────────────

@dp.callback_query_handler(lambda call: True, state='*')
async def callback_inline(call: types.CallbackQuery, state: FSMContext):
	await handle_callback(call, bot, dp, state)

async def handle_callback(call: types.CallbackQuery, bot_instance, dp_instance, state: FSMContext):
	"""Общая логика callback — используется и основным ботом, и зеркалами."""
	# Получаем токен bot_instance безопасно (aiogram 2 хранит в _token)
	_instance_token = getattr(bot_instance, '_token', None)
	try:
		uid = call.from_user.id
		if await is_blocked(uid):
			return
		if check_rate_limit(uid):
			await block_user(uid)
			await call.message.answer("Превысили лимит, заблокированы.")
			return
		if not await check_user_in_db(uid):
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*Пропишите /start*", parse_mode="Markdown")
			return
		if not await subsribe_channel(uid, channel_id) or not await subsribe_channel(uid, channel2_id):
			# Создаём временные invite links через основной бот (только он — администратор канала)
			try:
				import time as _time
				expire = int(_time.time()) + 60
				link1 = await bot.create_chat_invite_link(channel_id, expire_date=expire, member_limit=1)
				link2 = await bot.create_chat_invite_link(channel2_id, expire_date=expire, member_limit=1)
				invite1 = link1.invite_link
				invite2 = link2.invite_link
			except Exception as e:
				print(f"Ошибка создания invite link: {e}", flush=True)
				invite1 = config.bot_channel_link
				invite2 = config.bot_channel2_link
			temp_check_markup = types.InlineKeyboardMarkup(row_width=1)
			temp_check_markup.add(
				types.InlineKeyboardButton("[1️⃣] Подпишись (1 мин)", url=invite1),
				types.InlineKeyboardButton("[2️⃣] Подпишись (1 мин)", url=invite2),
				types.InlineKeyboardButton("[🔎] Проверить", callback_data='start_check_sub')
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*⚠️ Подпишитесь на каналы!*\n*└─ Ссылки действуют 1 минуту*", parse_mode="Markdown", reply_markup=temp_check_markup)
			return

		user_data = await db.get_user(uid)
		if not user_data:
			await db.add_user(uid)
			user_data = await db.get_user(uid)
		subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
		premium = int(user_data['premium'])
		username = call.from_user.username or "None"
		fullname = call.from_user.first_name

		d = call.data

		# Кнопка проверки подписки — обрабатываем здесь тоже (для зеркал)
		if d == 'start_check_sub':
			if await check_subscription(uid):
				try:
					await bot_instance.delete_message(uid, call.message.message_id)
				except Exception:
					pass
				await bot_instance.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
				await bot_instance.send_photo(uid, photo=open('material/menu.png', 'rb'),
					caption='>*Добро пожаловать в Brown V2\!*\n\n*Меню:*',
					parse_mode="MarkdownV2", reply_markup=menu)
			else:
				await bot_instance.answer_callback_query(call.id, "❌ Вы ещё не подписались!", show_alert=True)
			return

		if d == 'functions':
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*Заказ*\n\n>*Посмотрите Мануал*", parse_mode="MarkdownV2", reply_markup=functions)
		elif d == 'profile':
			sub_text = "Истекла" if subscribe < datetime.now() else f"осталось {(subscribe - datetime.now()).days} дней"
			prem = "Да" if premium == 1 else "Нет"
			free_reports = await db.get_free_reports(uid)
			ref_count = await db.get_referral_count(uid)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=f"*Профиль*\n\n▪️ *Имя: {fullname}*\n▪️ *ID: {uid}*\n▪️ *@{username}*\n▪️ *Премиум: {prem}*\n▪️ *Бесплатных репортов: {free_reports}*\n▪️ *Рефералов: {ref_count}*\n\n⏳ *{sub_text}*",
				parse_mode="Markdown", reply_markup=back_markup)
		elif d == "back":
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption='>*Добро пожаловать в Brown V2\!*\n\n*Меню:*',
				parse_mode="MarkdownV2", reply_markup=menu)
		elif d == "information":
			# Генерируем временную ссылку через основной бот
			try:
				import time as _time
				expire = int(_time.time()) + 60
				link = await bot.create_chat_invite_link(channel_id, expire_date=expire, member_limit=1)
				channel_invite = link.invite_link
			except Exception as e:
				print(f"Ошибка создания invite link для информации: {e}", flush=True)
				channel_invite = config.bot_channel_link
			dyn_info_markup = types.InlineKeyboardMarkup(row_width=2)
			dyn_info_markup.add(
				types.InlineKeyboardButton("мв Канал (1 мин)", url=channel_invite),
				types.InlineKeyboardButton("📄 Мануал", url='https://teletype.in/@brownv2/manual'),
			)
			dyn_info_markup.add(
				types.InlineKeyboardButton("👑 Владелец", url='https://t.me/TariSmit'),
				types.InlineKeyboardButton("🆘 Поддержка", url='https://t.me/BR_V2_support'),
			)
			dyn_info_markup.add(keyboards.back)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=">*Информация*", parse_mode="MarkdownV2", reply_markup=dyn_info_markup)
		elif d == "shop":
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="⚙️ *Ассортимент*\n\n>*└─ 1 день \- 1$ / 100₽*\n>*└─ 3 дня \- 2$ / 175₽*\n>*└─ 7 дней \- 4$ / 350₽*\n>*└─ 30 дней \- 8$ / 700₽*\n>*└─ Навсегда \- 6$ / 500₽ \[\-70%\]*\n\n>*👑 Премиум: 5$ / 400₽ \[\-50%\]*",
				parse_mode="MarkdownV2", reply_markup=shop_markup)
		elif d == "buyforadmins":
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("✍️ Написать @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="💳 *Оплата картой*\n\n*└─ Напишите* @TariSmit *и я скину вам ссылку для оплаты\.*",
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "yoomoney":
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("✍️ Написать @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="💳 *Оплата картой*\n\n*└─ Напишите* @TariSmit *и я скину вам ссылку для оплаты\.*",
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "tinkoff":
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("✍️ Написать @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="💳 *Оплата картой*\n\n*└─ Напишите* @TariSmit *и я скину вам ссылку для оплаты\.*",
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "sberbank":
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("✍️ Написать @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="💳 *Оплата картой*\n\n*└─ Напишите* @TariSmit *и я скину вам ссылку для оплаты\.*",
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "preminfo":
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="👑 *Премиум*\n\n>*└─ почты, веб, прем отправку*\n\n‼️ Покупается как ДОПОЛНЕНИЕ к подписке ‼️",
				parse_mode="MarkdownV2", reply_markup=back_markup)
		elif d == "close":
			await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
		elif d == "go_to_main_menu":
			await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
			await bot_instance.send_photo(call.message.chat.id, photo=open('material/menu.png', 'rb'),
				caption='>*Добро пожаловать в Brown V2\!*\n\n*Меню:*', parse_mode="MarkdownV2", reply_markup=menu)
		elif d == 'add_subsribe' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🎱 *Выдача подписки*\n*└─Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AddSubscribeFSM.user_id.state)
		elif d == 'clear_subscribe' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🎱 *Сброс подписки*\n*└─Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(ClearSubscribeFSM.user_id.state)
		elif d == 'add_prem' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🎱 *Выдача премиума*\n*└─Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AddPremFSM.user_id.state)
		elif d == 'clear_prem' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🎱 *Сброс премиума*\n*└─Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(ClearPremFSM.user_id.state)
		elif d == 'send_all' and uid in admins and uid in admins2:
			await bot_instance.send_message(call.message.chat.id, '🎱 *Рассылка*\n*└─Введите текст:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTextZFSM.text.state)
		elif d == 'block_user_admin' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🚫 *Блокировка*\n*└─Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(BlockUserFSM.user_id.state)
		elif d == 'unblock_user_admin' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '✅ *Разблокировка*\n*└─Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(UnblockUserFSM.user_id.state)
		elif d == 'admin_create_promo' and uid in admins:
			await bot_instance.send_message(
				call.message.chat.id,
				'💎 *Создание промокода*\n\n*└─ Выберите тип:*',
				parse_mode="Markdown",
				reply_markup=keyboards.promo_type_markup
			)

		elif d == 'delete_user_admin' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🗑 *Удаление из базы*\n*└─Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(DeleteUserFSM.user_id.state)

		elif d == 'promo_type_normal' and uid in admins:
			state_proxy = dp_instance.current_state(chat=uid, user=uid)
			await state_proxy.set_state(CreatePromoFSM.code.state)
			async with state_proxy.proxy() as fsm_data:
				fsm_data['promo_type'] = 'normal'
			await bot_instance.send_message(call.message.chat.id, '💎 *Обычный промокод*\n*└─ Введите код:*', parse_mode="Markdown")

		elif d == 'promo_type_premium' and uid in admins:
			state_proxy = dp_instance.current_state(chat=uid, user=uid)
			await state_proxy.set_state(CreatePromoFSM.code.state)
			async with state_proxy.proxy() as fsm_data:
				fsm_data['promo_type'] = 'premium'
			await bot_instance.send_message(call.message.chat.id, '👑 *Премиум промокод*\n*└─ Введите код:*', parse_mode="Markdown")

		elif d == 'promo_type_reports' and uid in admins:
			state_proxy = dp_instance.current_state(chat=uid, user=uid)
			await state_proxy.set_state(CreatePromoFSM.code.state)
			async with state_proxy.proxy() as fsm_data:
				fsm_data['promo_type'] = 'reports'
			await bot_instance.send_message(call.message.chat.id, '🎯 *Промокод на репорты*\n*└─ Введите код:*', parse_mode="Markdown")
		elif d.startswith('users_list_') and uid in admins:
			page = int(d.split('_')[2])
			PAGE_SIZE = 10
			users = await db.get_users_page(offset=page * PAGE_SIZE, limit=PAGE_SIZE)
			total = await db.get_users_count()
			total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

			if not users:
				await bot_instance.answer_callback_query(call.id, "Больше пользователей нет", show_alert=False)
				return

			lines = [f"👥 *Пользователи* (стр. {page+1}/{total_pages})\n"]
			now = datetime.now()
			for u in users:
				uid_u = u['user_id']
				sub = u['subscribe']
				sub_str = "✅ активна" if isinstance(sub, datetime) and sub > now else "❌ нет"
				prem = "👑" if u['premium'] else ""
				free = f"🎯{u['free_reports']}" if u['free_reports'] > 0 else ""
				lines.append(f"`{uid_u}` — {sub_str} {prem}{free}")

			text = "\n".join(lines)

			nav = types.InlineKeyboardMarkup(row_width=2)
			btns = []
			if page > 0:
				btns.append(types.InlineKeyboardButton("◀️ Назад", callback_data=f'users_list_{page-1}'))
			if (page + 1) < total_pages:
				btns.append(types.InlineKeyboardButton("Вперёд ▶️", callback_data=f'users_list_{page+1}'))
			if btns:
				nav.row(*btns)
			nav.add(types.InlineKeyboardButton("🔙 Закрыть", callback_data='close'))

			await bot_instance.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=nav)

		elif d.startswith('admin_mirrors_') and uid in admins:
			page = int(d.split('_')[2])
			PAGE_SIZE = 8
			all_mirrors = await db.get_all_mirrors()
			total = len(all_mirrors)
			total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
			page_mirrors = all_mirrors[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

			if not all_mirrors:
				await bot_instance.answer_callback_query(call.id, "Зеркал нет.", show_alert=False)
				return

			lines = [f"🪞 *Зеркала* (стр. {page+1}/{total_pages}, всего: {total})\n"]
			for m in page_mirrors:
				lines.append(f"`{m['bot_username']}` — `{m['user_id']}`\n`{m['token']}`\n")

			nav = types.InlineKeyboardMarkup(row_width=2)
			btns = []
			if page > 0:
				btns.append(types.InlineKeyboardButton("◀️", callback_data=f'admin_mirrors_{page-1}'))
			if (page + 1) < total_pages:
				btns.append(types.InlineKeyboardButton("▶️", callback_data=f'admin_mirrors_{page+1}'))
			if btns:
				nav.row(*btns)
			nav.add(types.InlineKeyboardButton("🔙 Закрыть", callback_data='close'))

			await bot_instance.send_message(call.message.chat.id, "\n".join(lines), parse_mode="Markdown", reply_markup=nav)

		elif d == 'admin_add_reports' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🎯 *Выдача репортов*\n*└─ Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AdminAddReportsFSM.user_id.state)

		elif d == 'admin_remove_reports' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🎯 *Отзыв репортов*\n*└─ Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AdminRemoveReportsFSM.user_id.state)
		elif d == 'promo':
			await bot_instance.send_message(call.message.chat.id, '🎱 *Активация промокода*\n*└─Введите промокод:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitPromoFSM.promo.state)

		elif d == 'promo_check_name':
			full_name = (call.from_user.first_name or "") + " " + (call.from_user.last_name or "")
			if "Brrown_V2bot" in full_name or "Brrown_V2bot" in (call.from_user.username or ""):
				await bot_instance.answer_callback_query(call.id, "✅ Отлично! Теперь введи промокод.", show_alert=False)
				await bot_instance.send_message(call.message.chat.id, '🎱 *Имя проверено!*\n*└─ Введите промокод:*', parse_mode="Markdown")
				await dp_instance.current_state(chat=uid, user=uid).set_state(WaitPromoFSM.promo.state)
			else:
				await bot_instance.answer_callback_query(call.id, "❌ @Brrown_V2bot не найден в имени. Добавь и попробуй снова.", show_alert=True)

		# ─── Реферальная система ───────────────────────────────────────────────
		elif d == 'referral':
			ref_count = await db.get_referral_count(uid)
			# Получаем username текущего бота для реферальной ссылки
			try:
				me = await bot_instance.get_me()
				bot_uname = me.username
			except Exception:
				bot_uname = bot_username[1:]
			ref_link = f"https://t.me/{bot_uname}?start=ref_{uid}"
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"👥 *Реферальная система*\n\n"
					f"*└─ Ваших рефералов: {ref_count}*\n\n"
					f"📎 *Ваша ссылка:*\n`{ref_link}`\n\n"
					f"*За каждые 10 рефералов — 1 день подписки*\n"
					f"*Также вы получаете 10% от покупки подписки вашим рефералом*"
				),
				parse_mode="Markdown", reply_markup=keyboards.referral_markup
			)

		elif d == 'exchange_refs':
			ref_count = await db.get_referral_count(uid)
			if ref_count < 10:
				await bot_instance.answer_callback_query(call.id, f"❌ Недостаточно рефералов! У вас {ref_count}/10", show_alert=True)
			else:
				# Атомарное снятие — защита от race condition
				success = await db.spend_referrals(uid, 10)
				if not success:
					await bot_instance.answer_callback_query(call.id, "❌ Недостаточно рефералов!", show_alert=True)
				else:
					new_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
					await db.set_subscribe(uid, new_date)
					remaining = ref_count - 10
					await bot_instance.answer_callback_query(call.id, "✅ Обменяно! +1 день подписки", show_alert=True)
					try:
						me = await bot_instance.get_me()
						bot_uname = me.username
					except Exception:
						bot_uname = bot_username[1:]
					await bot_instance.edit_message_caption(
						call.message.chat.id, call.message.message_id,
						caption=(
							f"👥 *Реферальная система*\n\n"
							f"*└─ Ваших рефералов: {remaining}*\n\n"
							f"📎 *Ваша ссылка:*\n`https://t.me/{bot_uname}?start=ref_{uid}`\n\n"
							f"*✅ Успешно обменяно 10 рефералов на 1 день подписки!*"
						),
						parse_mode="Markdown", reply_markup=keyboards.referral_markup
					)
					await bot.send_message(bot_logs, f"🔄 `{uid}` обменял 10 рефералов на 1 день", parse_mode="Markdown")

		# ─── Бесплатно / Зеркала ──────────────────────────────────────────────
		elif d == 'free_menu':
			mirror_count = await db.count_user_mirrors(uid)
			free_reports = await db.get_free_reports(uid)
			bonus_given = await db.get_mirror_bonus_given(uid)
			bonus_status = "✅ Получен" if bonus_given else f"{'🔒 Нужно 2 зеркала' if mirror_count < 2 else '⬆️ Доступен — создай зеркало!'}"
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"🆓 *Бесплатные репорты*\n\n"
					f"▪️ *Бесплатных репортов: {free_reports}*\n"
					f"▪️ *Зеркал создано: {mirror_count}*\n"
					f"▪️ *Бонус за зеркала: {bonus_status}*\n\n"
					f"🪞 *Как получить бонус:*\n"
					f"*└─ Создай бота через @BotFather*\n"
					f"*└─ Скинь нам токен*\n"
					f"*└─ При 2-м зеркале — +1 репорт (1 раз)*\n\n"
					f"*Зеркал можно создавать неограниченно*"
				),
				parse_mode="Markdown", reply_markup=keyboards.free_menu_markup
			)

		elif d == 'mirror_create':
			await bot_instance.send_message(
				call.message.chat.id,
				"🪞 *Создание зеркала*\n\n"
				"*1.* Открой @BotFather\n"
				"*2.* Напиши /newbot\n"
				"*3.* Придумай имя и username боту\n"
				"*4.* Скопируй токен и отправь его сюда:\n\n"
				"*Формат:* `1234567890:ABCdef...`",
				parse_mode="Markdown"
			)
			state_proxy = dp_instance.current_state(chat=uid, user=uid)
			if bot_instance is not bot:
				# Зеркальный бот — используем MirrorCreateFSM который уже отвечает через mirror_bot
				from mirror_manager import MirrorCreateFSM
				await state_proxy.set_state(MirrorCreateFSM.token.state)
			else:
				await state_proxy.set_state(WaitMirrorTokenFSM.token.state)

		elif d == 'mirror_list':
			mirrors = await db.get_user_mirrors(uid)
			if not mirrors:
				await bot_instance.answer_callback_query(call.id, "У вас нет зеркал.", show_alert=True)
				return
			import random as _random
			total_mirrors = len(mirrors)
			shown = _random.sample(mirrors, min(5, total_mirrors))
			lines = [f"🪞 *Ваши зеркала* (показано 5 из {total_mirrors}):\n"]
			for i, m in enumerate(shown, 1):
				lines.append(f"*{i}.* `{m['bot_username']}`")
			refresh_markup = types.InlineKeyboardMarkup(row_width=1)
			refresh_markup.add(
				types.InlineKeyboardButton("🔄 Обновить", callback_data='mirror_list'),
				keyboards.back
			)
			await bot_instance.send_message(
				call.message.chat.id,
				"\n".join(lines),
				parse_mode="Markdown",
				reply_markup=refresh_markup
			)

		# ─── Публичные зеркала ─────────────────────────────────────────────────
		elif d == 'public_mirrors':
			import random as _random
			all_mirrors = await db.get_all_mirrors()
			if not all_mirrors:
				await bot_instance.answer_callback_query(call.id, "Зеркал пока нет.", show_alert=True)
				return
			shown = _random.sample(all_mirrors, min(5, len(all_mirrors)))
			lines = ["🪞 *Зеркала Brown V2*\n\n*└─ 5 случайных рабочих зеркал:*\n"]
			for m in shown:
				lines.append(f"• `{m['bot_username']}`")
			refresh_markup = types.InlineKeyboardMarkup(row_width=1)
			refresh_markup.add(
				types.InlineKeyboardButton("🔄 Обновить", callback_data='public_mirrors'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption="\n".join(lines),
				parse_mode="Markdown",
				reply_markup=refresh_markup
			)

		# ─── Колесо удачи ──────────────────────────────────────────────────────
		elif d == 'wheel':
			last_spin = await db.get_wheel_last_spin(uid)
			now = datetime.now()
			if last_spin and (now - last_spin).total_seconds() < 6 * 3600:
				remaining = timedelta(seconds=6*3600) - (now - last_spin)
				h = int(remaining.total_seconds() // 3600)
				m = int((remaining.total_seconds() % 3600) // 60)
				await bot_instance.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						f"🎡 *Колесо репортов*\n\n"
						f"⏳ *Следующий спин через: {h}ч {m}м*\n\n"
						f"🎰 *Призы:*\n"
						f"▪️ 60% — Ничего\n"
						f"▪️ 19% — 1 репорт\n"
						f"▪️ 10% — 2 репорта\n"
						f"▪️ 5% — 3 репорта\n"
						f"▪️ 1% — 5 репортов 🍀"
					),
					parse_mode="Markdown", reply_markup=keyboards.wheel_markup
				)
			else:
				await bot_instance.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						f"🎡 *Колесо репортов*\n\n"
						f"🎰 *Призы:*\n"
						f"▪️ 60% — Ничего\n"
						f"▪️ 19% — 1 репорт\n"
						f"▪️ 10% — 2 репорта\n"
						f"▪️ 5% — 3 репорта\n"
						f"▪️ 1% — 5 репортов 🍀\n\n"
						f"✅ *Крутить можно!*"
					),
					parse_mode="Markdown", reply_markup=keyboards.wheel_markup
				)

		elif d == 'spin_wheel':
			last_spin = await db.get_wheel_last_spin(uid)
			now = datetime.now()

			# Проверяем — выиграна ли подписка/премиум и она ещё активна
			last_prize = await db.get_wheel_prize(uid)
			if last_prize in ("forever", "sub_1d", "premium"):
				if last_prize == "premium" and premium == 1:
					await bot_instance.answer_callback_query(
						call.id, "❌ Крутить нельзя — у вас активный выигранный премиум!", show_alert=True
					)
					return
				if last_prize in ("forever", "sub_1d") and subscribe > now:
					await bot_instance.answer_callback_query(
						call.id, "❌ Крутить нельзя — у вас активная выигранная подписка!", show_alert=True
					)
					return

			if last_spin and (now - last_spin).total_seconds() < 6 * 3600:
				remaining = timedelta(seconds=6*3600) - (now - last_spin)
				h = int(remaining.total_seconds() // 3600)
				m = int((remaining.total_seconds() % 3600) // 60)
				await bot_instance.answer_callback_query(call.id, f"⏳ Следующий спин через {h}ч {m}м", show_alert=True)
				return

			await db.set_wheel_last_spin(uid, now)

			import random as _random
			roll = _random.random() * 100
			if roll < 1:
				prize = "reports_5"
			elif roll < 6:
				prize = "reports_3"
			elif roll < 16:
				prize = "reports_2"
			elif roll < 35:
				prize = "reports_1"
			else:
				prize = "nothing"

			await db.set_wheel_prize(uid, prize)

			prize_texts = {
				"reports_5": ("🍀 *Невероятно! +5 репортов!*", "🍀 5 репортов"),
				"reports_3": ("🎯 *+3 репорта!*", "🎯 3 репорта"),
				"reports_2": ("🎯 *+2 репорта!*", "🎯 2 репорта"),
				"reports_1": ("🎯 *+1 репорт!*", "🎯 1 репорт"),
				"nothing":   ("😔 *Ничего... Повезёт в следующий раз!*", "😔 Ничего"),
			}
			text, log_text = prize_texts[prize]

			if prize == "reports_5":
				await db.add_free_reports(uid, 5)
			elif prize == "reports_3":
				await db.add_free_reports(uid, 3)
			elif prize == "reports_2":
				await db.add_free_reports(uid, 2)
			elif prize == "reports_1":
				await db.add_free_reports(uid, 1)

			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"🎡 *Колесо репортов*\n\n"
					f"🎰 Результат:\n{text}\n\n"
					f"⏳ *Следующий спин через 6 часов*"
				),
				parse_mode="Markdown", reply_markup=back_markup
			)
			await bot.send_message(bot_logs, f"🎡 `{uid}` крутил колесо — {log_text}", parse_mode="Markdown")
		def sub_expired():
			return subscribe < datetime.now()
		def bot_off():
			return bot_status == 0

		# Список методов требующих подтверждения мануала
		METHODS_REQUIRING_CONFIRM = {
			"web_method", "mail_method", "botnet_method", "prem_botnet_method",
			"bot_method", "channel_method", "code_method", "aureport_method",
			"tida_method", "bank_method",
		}

		# ─── Шаг 1: показываем предупреждение при нажатии на метод ──────────
		if d in METHODS_REQUIRING_CONFIRM:
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"⚠️ *Перед следующим шагом прочтите мануал\!*\n\n"
					"📄 *Ознакомьтесь с правилами использования*\n\n"
					"❌ *За непрочтение \/ неправильные жалобы вам могут обнулить подписку*"
				),
				parse_mode="MarkdownV2",
				reply_markup=keyboards.manual_confirm_step1(d)
			)
			return

		# ─── Шаг 2: "Ознакомлен" → второй экран ─────────────────────────────
		if d.startswith('manual_step2_'):
			method = d[len('manual_step2_'):]
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"📄 *Вы действительно прочитали мануал?*\n\n"
					"*Нажмите кнопку ниже только если прочитали*"
				),
				parse_mode="Markdown",
				reply_markup=keyboards.manual_confirm_step2(method)
			)
			return

		# ─── Шаг 3: "100% прочитал" → запускаем метод ────────────────────────
		if d.startswith('manual_confirm_'):
			d = d[len('manual_confirm_'):]  # подменяем d на реальный метод

		if d == "web_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0: await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужен премиум\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_web and (datetime.now() - last_used_web[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (datetime.now() - last_used_web[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=back_markup); return
			await call.message.answer("✉️ *Введите текст:*", parse_mode="Markdown", reply_markup=back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTextFSM.text.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "mail_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_mail and (datetime.now() - last_used_mail[uid]) < timedelta(minutes=300):
				rem = timedelta(minutes=300) - (datetime.now() - last_used_mail[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {rem.seconds//60} мин*', parse_mode="Markdown", reply_markup=back_markup); return
			await call.message.answer("📌 *Введите тему:*", parse_mode="Markdown", reply_markup=back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitMailTopicFSM.topic.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "botnet_method":
			free_reports = await db.get_free_reports(uid)
			if sub_expired() and free_reports == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати или получи бесплатный репорт\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_botnet and (datetime.now() - last_used_botnet[uid]) < timedelta(minutes=5):
				rem = timedelta(minutes=5) - (datetime.now() - last_used_botnet[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.send_message(call.message.chat.id, '*Ссылка на сообщение:*\n`https://t.me/username/123`', parse_mode="Markdown", reply_markup=back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitLinkFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "prem_botnet_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0: await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужен премиум\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_botnet2 and (datetime.now() - last_used_botnet2[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (datetime.now() - last_used_botnet2[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {rem.seconds//60} мин*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.send_message(call.message.chat.id, '*Ссылка на сообщение:*\n`https://t.me/username/123`', parse_mode="Markdown", reply_markup=back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitLinkPREMFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		# ─── Бот-метод ────────────────────────────────────────────────────────
		elif d == "bot_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужна подписка\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and uid in last_used_bot_snos and (datetime.now() - last_used_bot_snos[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (datetime.now() - last_used_bot_snos[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption="🤖 *Бот-метод*\n\n*└─ Выберите причину жалобы:*",
				parse_mode="Markdown", reply_markup=keyboards.bot_reason_markup
			)

		elif d in ("bot_reason_personal", "bot_reason_drugs", "bot_reason_other"):
			reason_key = d.replace("bot_reason_", "")
			reason_labels = {"personal": "🔐 Персональные данные", "drugs": "💊 Наркотики", "other": "📝 Прочее"}
			reason_label = reason_labels.get(reason_key, reason_key)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitBotLinkFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(bot_reason=reason_key, _bot_token=_instance_token)
			await bot_instance.send_message(
				call.message.chat.id,
				f"🤖 *Бот-метод*\n*Причина: {reason_label}*\n\n*└─ Введите @username бота:*\n`@username_bot`\n\n*⚠️ Username должен оканчиваться на* `bot`",
				parse_mode="Markdown", reply_markup=back_markup
			)

		# ─── Канал-метод ──────────────────────────────────────────────────────
		elif d == "channel_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			free_reports_ch = await db.get_free_reports(uid)
			if sub_expired() and free_reports_ch == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати или получи бесплатный репорт\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption="📢 *Канал-метод*\n\n*└─ Выберите причину жалобы:*",
				parse_mode="Markdown", reply_markup=keyboards.channel_reason_markup
			)

		elif d in ("ch_reason_personal", "ch_reason_spam", "ch_reason_adult", "ch_reason_children", "ch_reason_violence", "ch_reason_other"):
			reason_map = {
				"ch_reason_personal": ("personal", "🔐 Персональные данные"),
				"ch_reason_spam":     ("spam",     "📢 Спам / Мошенничество"),
				"ch_reason_adult":    ("adult",    "🔞 18+ Контент"),
				"ch_reason_children": ("children", "👶 Детский контент"),
				"ch_reason_violence": ("violence", "💥 Насилие / Экстремизм"),
				"ch_reason_other":    ("other",    "📝 Прочее"),
			}
			reason_key, reason_label = reason_map[d]
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitChannelFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(ch_reason=reason_key, _bot_token=_instance_token)
			await bot_instance.send_message(
				call.message.chat.id,
				f"📢 *Причина: {reason_label}*\n\n*Введите @username канала или ссылку:*\n`@channel` или `https://t.me/channel`",
				parse_mode="Markdown", reply_markup=back_markup
			)

		# ─── Ручной метод ─────────────────────────────────────────────────────
		elif d == "manual_method":
			manual_markup = types.InlineKeyboardMarkup(row_width=1)
			manual_markup.add(
				types.InlineKeyboardButton("✍️ Написать @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"👤 *Ручной метод*\n\n"
					"*└─ Это метод ручного сноса через администрацию*\n\n"
					">*Ручной метод — снос вручную нашими специалистами\.*\n"
					">*Напишите @TariSmit, укажите юзернейм цели и узнайте цену\.*\n\n"
					"*⚠️ Работаем только по предоплате\.*"
				),
				parse_mode="MarkdownV2",
				reply_markup=manual_markup
			)

		# ─── AU Report ────────────────────────────────────────────────────────
		elif d == "aureport_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужна подписка\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and uid in last_used_aureport and (datetime.now() - last_used_aureport[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (datetime.now() - last_used_aureport[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitAuReportFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"🇦🇺 *AU Report*\n\n"
					"*└─ Введите @username или ссылку на цель:*\n\n"
					"`@username` или `https://t.me/username`"
				),
				parse_mode="Markdown", reply_markup=back_markup
			)

		# ─── TIDA ─────────────────────────────────────────────────────────────
		elif d == "tida_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужна подписка\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and uid in last_used_tida and (datetime.now() - last_used_tida[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (datetime.now() - last_used_tida[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTidaFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"🟣 *TIDA*\n\n"
					"*└─ Введите @username или ссылку на цель:*\n\n"
					"`@username` или `https://t.me/username`"
				),
				parse_mode="Markdown", reply_markup=back_markup
			)

		# ─── Блокировка карты ─────────────────────────────────────────────────
		elif d == "bank_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужен Premium\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and uid in last_used_bank and (datetime.now() - last_used_bank[uid]) < timedelta(hours=12):
				rem = timedelta(hours=12) - (datetime.now() - last_used_bank[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=f'❌ *Кулдаун: {h}ч {m}м*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"🏦 *Блокировка карты по 115-ФЗ*\n\n"
					"*└─ Выберите банк:*"
				),
				parse_mode="Markdown", reply_markup=keyboards.bank_select_markup
			)

		elif d in ("bank_tbank", "bank_alfa", "bank_sber", "bank_ozon"):
			bank_key = d.replace("bank_", "")
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitBankFSM.card.state)
			await dp_instance.current_state(user=uid).update_data(bank_key=bank_key, _bot_token=_instance_token)
			bank_names = {"tbank": "Т-Банк", "alfa": "Альфа-Банк", "sber": "Сбер Банк", "ozon": "Озон Банк"}
			await bot_instance.send_message(
				call.message.chat.id,
				f"🏦 *{bank_names[bank_key]}*\n\n"
				f"*└─ Введите номер телефона или карты цели:*\n\n"
				f"`+79991234567` или `4276 1234 5678 9012`",
				parse_mode="Markdown", reply_markup=back_markup
			)

		# ─── Код-метод ────────────────────────────────────────────────────────
		elif d == "code_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужна подписка\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitPhoneFSM.phone.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption="📱 *Код-метод*\n\n*└─ Введите номер телефона цели:*\n`+79991234567`",
				parse_mode="Markdown", reply_markup=back_markup
			)

		# ─── Стрессер ─────────────────────────────────────────────────────────
		elif d == "stress_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			# КД 2 часа (кроме админов)
			if uid not in admins and uid in last_used_stress and (datetime.now() - last_used_stress[uid]) < timedelta(hours=2):
				rem = timedelta(hours=2) - (datetime.now() - last_used_stress[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {h}ч {m}м*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.send_message(
				call.message.chat.id,
				"⚡️ *Стрессер*\n\n*└─ Введите @username бота или ссылку:*\n`@username` или `https://t.me/botname`",
				parse_mode="Markdown"
			)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitStressFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

	except Exception as e:
		print(f"callback_inline: {e}")

# ─── FSM хендлеры ─────────────────────────────────────────────────────────────

@dp.message_handler(state=WaitTextFSM.text)
async def send_web_reports(message: types.Message, state: FSMContext):
	fsm_data = await state.get_data()
	await state.finish()
	uid = message.from_user.id
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	username = message.from_user.username or "без username"
	log_path = generate_log_filename()
	async with aiohttp.ClientSession() as session:
		success, error = await web(session=session, message_text=message.text,
			count=report_count333, log_path=log_path, user_id=uid, username=username)
	# КД ставим только после завершения отправки
	last_used_web[uid] = datetime.now()
	try:
		await _bot.send_document(uid, types.InputFile(log_path),
			caption=f"⚙️ *Веб*\n🟢 *Успешно: {success}*\n🔴 *Не удалось: {error}*",
			reply_markup=main_menu, parse_mode="Markdown")
	except Exception: pass
	try:
		await bot.send_document(bot_logs, types.InputFile(log_path),
			caption=f"📈 *Веб*\n🟢 {success}\n🔴 {error}\n👤 {uid} (@{username})", parse_mode="Markdown")
	except Exception: pass
	try: os.remove(log_path)
	except Exception: pass
	if _is_mirror_bot:
		try:
			session = await _bot.get_session()
			await session.close()
		except Exception:
			pass

@dp.message_handler(state=WaitMailTopicFSM.topic)
async def get_mail_subject(message: types.Message, state: FSMContext):
	await state.update_data(subject=message.text)
	# КД ставим только после реальной отправки в start_bulk_email
	await message.answer("✉️ *Введите текст письма:*", parse_mode="Markdown")
	await WaitMailTextFSM.text.set()

@dp.message_handler(state=WaitMailTextFSM.text)
async def start_bulk_email(message: types.Message, state: FSMContext):
	data = await state.get_data()
	subject = data.get("subject")
	_bot_token = data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	await state.finish()
	mails = load_mails()
	if not mails:
		await message.answer("❌ *Нет почт!*", parse_mode="Markdown"); return
	receiver_emails = ["dmca@telegram.org","support@telegram.org","abuse@telegram.org","stopCA@telegram.org"]
	success, error, log_path = await send_bulk_emails(
		subject, message.text, mails, receiver_emails,
		user_id=message.from_user.id, username=message.from_user.username or "None",
		bot=_bot, chat_id=message.from_user.id)
	# КД ставим только после реального завершения отправки
	last_used_mail[message.from_user.id] = datetime.now()
	try:
		await _bot.send_document(message.from_user.id, types.InputFile(log_path),
			caption=f"⚙️ *Почты*\n🟢 {success}\n🔴 {error}", parse_mode="Markdown", reply_markup=main_menu)
		await bot.send_document(bot_logs, types.InputFile(log_path),
			caption=f"📈 *Почты*\n🟢 {success}\n🔴 {error}\n👤 {message.from_user.id}", parse_mode="Markdown")
	except Exception as e: print(e)
	try: os.remove(log_path)
	except Exception: pass
	# Закрываем временную сессию зеркального бота
	if _is_mirror_bot:
		try:
			session = await _bot.get_session()
			await session.close()
		except Exception:
			pass

@dp.message_handler(state=WaitLinkFSM.link)
async def botnet_step1_normal(message: types.Message, state: FSMContext):
	url = message.text
	fsm_data = await state.get_data()
	await state.finish()
	uid = message.from_user.id
	username = message.from_user.username or "None"
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	try:
		chat_username, message_id = await extract_username_and_message_id(url)
		user_data = await db.get_user(uid)
		if not user_data:
			await _bot.send_message(uid, '❌ *Пользователь не найден, напишите /start*', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
			return
		subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
		if subscribe < datetime.now():
			used = await db.use_free_report(uid)
			if not used:
				await _bot.send_message(uid, '❌ *Нет подписки и бесплатных репортов!*', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
				return
			free_left = await db.get_free_reports(uid)
			await _bot.send_message(uid, f'🎯 *Использован бесплатный репорт! Осталось: {free_left}*', parse_mode=ParseMode.MARKDOWN)
		await _bot.send_message(uid, '📤 *Запустил отправку...*', parse_mode=ParseMode.MARKDOWN)
		botnet_set_bot(_bot)
		await botnet_main(chat_username, message_id, uid, username, url)
		# КД только после успешного запуска
		last_used_botnet[uid] = datetime.now()
	except ValueError:
		await _bot.send_message(uid, '*⭕️ Неверная ссылка!*', parse_mode=ParseMode.MARKDOWN)
	except Exception as e:
		print(f"[BOTNET] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка ботнета:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
	finally:
		botnet_set_bot(bot)
		if _is_mirror_bot:
			try:
				session = await _bot.get_session()
				await session.close()
			except Exception:
				pass

@dp.message_handler(state=WaitLinkPREMFSM.link)
async def botnet_step1_premium(message: types.Message, state: FSMContext):
	url = message.text
	fsm_data = await state.get_data()
	await state.finish()
	uid = message.from_user.id
	username = message.from_user.username or "None"
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	try:
		chat_username, message_id = await extract_username_and_message_id2(url)
		await _bot.send_message(uid, '👑 *Запустил отправку...*', parse_mode=ParseMode.MARKDOWN)
		botnet_set_bot2(_bot)
		await botnet_main2(chat_username, message_id, uid, username, url)
		# КД только после успешного запуска
		last_used_botnet2[uid] = datetime.now()
	except ValueError:
		await _bot.send_message(uid, '*⭕️ Неверная ссылка!*', parse_mode=ParseMode.MARKDOWN)
	except Exception as e:
		print(f"[PREM] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка премиум-ботнета:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
	finally:
		botnet_set_bot2(bot)
		if _is_mirror_bot:
			try:
				session = await _bot.get_session()
				await session.close()
			except Exception:
				pass

@dp.message_handler(state=WaitMirrorTokenFSM.token)
async def mirror_token_received(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	token = message.text.strip()

	# Если прислали команду — отменяем FSM
	if token.startswith('/'):
		await state.finish()
		await bot.send_message(uid, "❌ *Ввод токена отменён.*", parse_mode="Markdown", reply_markup=main_menu)
		return

	# Базовая проверка формата токена
	if ':' not in token or len(token) < 30:
		await state.finish()
		await bot.send_message(uid, "❌ *Неверный формат токена!*\n*Пример:* `1234567890:ABCdef...`", parse_mode="Markdown")
		return

	await state.finish()

	# Проверяем не сдан ли токен уже
	if await db.token_exists(token):
		await bot.send_message(uid, "❌ *Этот токен уже зарегистрирован!*", parse_mode="Markdown")
		return

	# Проверяем токен через getMe
	wait_msg = await bot.send_message(uid, "⏳ *Проверяем токен...*", parse_mode="Markdown")
	bot_username_new = await validate_token(token)
	try:
		await bot.delete_message(uid, wait_msg.message_id)
	except Exception:
		pass

	if not bot_username_new:
		await bot.send_message(uid, "❌ *Токен невалидный или бот не существует!*\n*Проверь и попробуй снова.*", parse_mode="Markdown")
		return

	# Сохраняем и запускаем зеркало
	await db.add_mirror(uid, token, bot_username_new)
	await start_mirror(token)

	# Бонус +1 репорт при создании 2-го зеркала — только 1 раз
	mirror_count = await db.count_user_mirrors(uid)
	bonus_msg = ""
	if mirror_count >= 2 and not await db.get_mirror_bonus_given(uid):
		await db.add_free_reports(uid, 1)
		await db.set_mirror_bonus_given(uid)
		bonus_msg = "\n🎯 *Бонус: +1 бесплатный репорт за 2 зеркала!*"

	await bot.send_message(
		uid,
		f"✅ *Зеркало создано!*\n\n"
		f"🤖 *Бот:* `{bot_username_new}`\n"
		f"📊 *Всего зеркал: {mirror_count}*"
		f"{bonus_msg}",
		parse_mode="Markdown", reply_markup=main_menu
	)
	await bot.send_message(
		bot_logs,
		f"🪞 *Новое зеркало*\n"
		f"*└─ Пользователь:* `{uid}`\n"
		f"*└─ Бот:* `{bot_username_new}`\n"
		f"*└─ Всего зеркал:* `{mirror_count}`",
		parse_mode="Markdown"
	)

@dp.message_handler(state=WaitBotLinkFSM.link)
async def bot_snos_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()

	# Сначала читаем fsm_data чтобы _bot был доступен для сообщений об ошибках
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	user_data = await db.get_user(uid)
	if not user_data:
		await state.finish()
		await _bot.send_message(uid, '❌ *Пользователь не найден, напишите /start*', parse_mode="Markdown", reply_markup=main_menu)
		return
	subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")

	if subscribe < datetime.now():
		await state.finish()
		await _bot.send_message(uid, ">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=main_menu)
		return
	if uid in last_used_bot_snos and (datetime.now() - last_used_bot_snos[uid]) < timedelta(minutes=30):
		rem = timedelta(minutes=30) - (datetime.now() - last_used_bot_snos[uid])
		await state.finish()
		await _bot.send_message(uid, f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=main_menu)
		return

	if raw.startswith("https://t.me/"):
		bot_target = "@" + raw.replace("https://t.me/", "").split("/")[0].split("?")[0]
	elif raw.startswith("t.me/"):
		bot_target = "@" + raw.replace("t.me/", "").split("/")[0].split("?")[0]
	elif raw.startswith("@"):
		bot_target = raw.split("/")[0]
	else:
		bot_target = "@" + raw.split("/")[0].split("?")[0]

	# Проверяем что это бот (username должен оканчиваться на 'bot')
	if not bot_target.lower().endswith("bot"):
		await state.finish()
		await _bot.send_message(uid,
			"❌ *Это не бот!*\n\n"
			"*Бот-метод работает только с ботами.*\n"
			"*Username бота должен оканчиваться на* `bot`\n"
			"*Пример:* `@example_bot`",
			parse_mode="Markdown", reply_markup=main_menu)
		return

	reason_key = fsm_data.get('bot_reason', 'other')
	await state.finish()

	last_used_bot_snos[uid] = datetime.now()
	await _bot.send_message(uid, f'🤖 *Запустил жалобы на {bot_target}...*', parse_mode=ParseMode.MARKDOWN)

	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	try:
		set_bot_snos(_bot)
		await main_bot_snos(bot_target, reason_key, uid, username, bot_target)
	except Exception as e:
		print(f"[BOT-SNOS] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка бот-метода:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
	finally:
		set_bot_snos(bot)
		if _is_mirror_bot:
			try:
				session = await _bot.get_session()
				await session.close()
			except Exception:
				pass

@dp.message_handler(state=WaitChannelFSM.link)
async def channel_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	# Нормализуем username канала и извлекаем message_id если есть
	message_id = None
	if raw.startswith("https://t.me/"):
		parts = raw.replace("https://t.me/", "").split("?")[0].split("/")
		ch_target = "@" + parts[0]
		if len(parts) >= 2 and parts[1].isdigit():
			message_id = int(parts[1])
	elif raw.startswith("t.me/"):
		parts = raw.replace("t.me/", "").split("?")[0].split("/")
		ch_target = "@" + parts[0]
		if len(parts) >= 2 and parts[1].isdigit():
			message_id = int(parts[1])
	elif raw.startswith("@"):
		ch_target = raw.split("/")[0]
	else:
		parts = raw.split("?")[0].split("/")
		ch_target = "@" + parts[0]
		if len(parts) >= 2 and parts[1].isdigit():
			message_id = int(parts[1])

	reason_key = fsm_data.get('ch_reason', 'other')
	await state.finish()

	# КД 30 минут
	if uid not in admins and uid in last_used_channel and (datetime.now() - last_used_channel[uid]) < timedelta(minutes=30):
		rem = timedelta(minutes=30) - (datetime.now() - last_used_channel[uid])
		await _bot.send_message(uid, f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	last_used_channel[uid] = datetime.now()
	msg_info = f" (сообщение #{message_id})" if message_id else ""
	await _bot.send_message(uid, f'📢 *Запустил жалобы на канал {ch_target}{msg_info}...*', parse_mode="Markdown")

	try:
		set_bot_channel(_bot)
		await main_channel_snos(ch_target, reason_key, uid, username, message_id=message_id)
	except Exception as e:
		print(f"[CH-SNOS] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка канал-метода:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		from channel_snos import set_bot_channel as _set_ch
		_set_ch(bot)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass

@dp.message_handler(state=WaitPhoneFSM.phone)
async def phone_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	# Валидация номера
	phone = raw if raw.startswith("+") else "+" + raw
	if len(phone) < 8 or not phone[1:].isdigit():
		await _bot.send_message(uid,
			"❌ *Неверный формат номера!*\n*Пример:* `+79991234567`",
			parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	# КД 30 минут
	if uid not in admins and uid in last_used_channel and (datetime.now() - last_used_channel[uid]) < timedelta(minutes=30):
		rem = timedelta(minutes=30) - (datetime.now() - last_used_channel[uid])
		await _bot.send_message(uid, f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	last_used_channel[uid] = datetime.now()
	await _bot.send_message(uid,
		f'📱 *Запускаю код-метод на* `{phone}`*...*\n*└─ Отправляем 25 кодов*',
		parse_mode="Markdown")

	try:
		from code_snos import set_bot_code as _set_code
		_set_code(_bot)
		await main_code_snos(phone, uid, username)
	except Exception as e:
		print(f"[CODE] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка код-метода:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		set_bot_code(bot)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitAuReportFSM.link)
async def aureport_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	# Валидация — должен быть username или ссылка
	if not raw.startswith("@") and not raw.startswith("https://t.me/") and not raw.startswith("t.me/"):
		raw = "@" + raw

	if uid not in admins:
		last_used_aureport[uid] = datetime.now()

	await _bot.send_message(uid,
		f'🇦🇺 *Запускаю AU Report на* `{raw}`*...*\n*└─ Это может занять некоторое время*',
		parse_mode="Markdown")

	try:
		set_bot_aureport(_bot)
		await main_aureport(raw, uid, username)
	except Exception as e:
		print(f"[AUREPORT] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка AU Report:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		set_bot_aureport(bot)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitTidaFSM.link)
async def tida_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	raw = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')

	if not raw.startswith("@") and not raw.startswith("https://t.me/") and not raw.startswith("t.me/"):
		raw = "@" + raw

	await state.update_data(tida_link=raw, _bot_token=_bot_token)
	await WaitTidaFSM.text.set()

	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await _bot.send_message(uid,
		f'🟣 *TIDA*\n\n*Цель:* `{raw}`\n\n*Введите текст жалобы:*\n_(Опишите нарушение на английском языке)_\n\n[📋 Шаблоны текстов](https://t.me/+zTWywoULseYzMWU0)',
		parse_mode="Markdown", reply_markup=back_markup)

	if _is_mirror_bot:
		try:
			s = await _bot.get_session(); await s.close()
		except Exception: pass


@dp.message_handler(state=WaitTidaFSM.text)
async def tida_step2(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	custom_text = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	target_link = fsm_data.get('tida_link', '')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	if len(custom_text) < 10:
		await _bot.send_message(uid, "❌ *Текст слишком короткий! Минимум 10 символов.*", parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	if uid not in admins:
		last_used_tida[uid] = datetime.now()

	await _bot.send_message(uid,
		f'🟣 *Запускаю TIDA на* `{target_link}`*...*\n*└─ Это может занять некоторое время*',
		parse_mode="Markdown")

	try:
		set_bot_tida(_bot)
		await main_tida(target_link, custom_text, uid, username)
	except Exception as e:
		print(f"[TIDA] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка TIDA:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		set_bot_tida(bot)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitBankFSM.card)
async def bank_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	card_data = message.text.strip()
	fsm_data = await state.get_data()
	bank_key = fsm_data.get('bank_key', 'tbank')
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	if len(card_data) < 7:
		await _bot.send_message(uid, "❌ *Введите корректный номер телефона или карты!*", parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	if uid not in admins:
		last_used_bank[uid] = datetime.now()

	try:
		set_bot_bank(_bot)
		await process_bank_report(bank_key, card_data, uid, username)
	except Exception as e:
		print(f"[BANK] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		set_bot_bank(bot)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitStressFSM.link)
async def stress_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	# Нормализуем username
	if raw.startswith("https://t.me/"):
		bot_target = "@" + raw.replace("https://t.me/", "").split("/")[0].split("?")[0]
	elif raw.startswith("t.me/"):
		bot_target = "@" + raw.replace("t.me/", "").split("/")[0].split("?")[0]
	elif raw.startswith("@"):
		bot_target = raw.split("/")[0]
	else:
		bot_target = "@" + raw.split("/")[0].split("?")[0]

	await state.finish()

	is_admin = uid in admins
	free_reports = await db.get_free_reports(uid)
	user_data = await db.get_user(uid)
	if not user_data:
		await _bot.send_message(uid, '❌ *Пользователь не найден, напишите /start*', parse_mode="Markdown", reply_markup=main_menu)
		return
	subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")

	# Проверяем подписку — стрессер только с подпиской, бесплатные репорты не тратим
	if not is_admin and subscribe < datetime.now():
		await _bot.send_message(uid, '❌ *Нужна подписка для использования стрессера!*', parse_mode="Markdown", reply_markup=main_menu)
		return

	await _bot.send_message(uid, f'⚡️ *Запускаем стрессер на {bot_target}...*', parse_mode="Markdown")
	set_bot_stress(_bot)

	try:
		started = await main_bot_stress(bot_target, uid, username, is_admin)
		# КД только если атака успешно запустилась (нашлись кнопки)
		if started and not is_admin:
			last_used_stress[uid] = datetime.now()
	except Exception as e:
		print(f"[STRESS] ОШИБКА: {e}", flush=True)
		import traceback
		traceback.print_exc()
		await _bot.send_message(uid, f'❌ *Ошибка стрессера:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		set_bot_stress(bot)
		if _is_mirror_bot:
			try:
				session = await _bot.get_session()
				await session.close()
			except Exception:
				pass

# ─── Управление подписками (админ) ────────────────────────────────────────────

@dp.message_handler(state=AddSubscribeFSM.user_id)
async def add_sub_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден в базе.", parse_mode="Markdown")
			await state.finish()
			return
		await state.update_data(user_id=target)
		await message.answer(f"🎱 *ID найден:* `{target}`\n*Введите количество дней:*", parse_mode=ParseMode.MARKDOWN)
		await AddSubscribeFSM.days.set()
	except Exception:
		await message.answer("❌ Ошибка."); await state.finish()

@dp.message_handler(state=AddSubscribeFSM.days)
async def add_sub_days(message: types.Message, state: FSMContext):
	try:
		data = await state.get_data()
		target = data['user_id']
		new_date = (datetime.now() + timedelta(days=int(message.text))).strftime("%Y-%m-%d %H:%M:%S")
		await db.set_subscribe(target, new_date)
		await state.finish()
		try:
			await bot.send_message(target, f"🎱 *Подписка обновлена до* `{new_date}`", parse_mode="Markdown", reply_markup=del_message2)
		except Exception:
			pass
		await message.answer(f"🎱 *Готово! Подписка выдана* `{target}` *до* `{new_date}`", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🎱 *Выдана подписка* `{target}` до `{new_date}`", parse_mode="Markdown")
	except ValueError:
		await message.answer("❌ Введите число дней (например: 7).")
	except Exception as e:
		await message.answer(f"❌ Ошибка: `{str(e)[:100]}`", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=ClearSubscribeFSM.user_id)
async def clear_sub_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown"); await state.finish(); return
		await db.set_subscribe(target, "1999-01-01 00:00:00", force=True)
		await state.finish()
		await bot.send_message(target, "*🎱 Подписка сброшена.*", parse_mode="Markdown", reply_markup=del_message2)
		await message.answer(f"*🎱 Сброшено у* `{target}`*!*", parse_mode="Markdown")
	except Exception:
		await message.answer("❌ Ошибка."); await state.finish()

@dp.message_handler(state=AddPremFSM.user_id)
async def add_prem_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown"); await state.finish(); return
		await db.set_premium(target, 1)
		await state.finish()
		try:
			await bot.send_message(target, "*👑 Вам выдан Premium.*", parse_mode="Markdown", reply_markup=del_message2)
		except Exception:
			pass
		await message.answer(f"*🎱 Премиум выдан* `{target}`*!*", parse_mode="Markdown")
	except Exception as e:
		await message.answer(f"❌ Ошибка: `{str(e)[:100]}`", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=ClearPremFSM.user_id)
async def clear_prem_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown"); await state.finish(); return
		await db.set_premium(target, 0)
		await state.finish()
		await bot.send_message(target, "*🎱 Премиум сброшен.*", parse_mode="Markdown", reply_markup=del_message2)
		await message.answer(f"*🎱 Сброшено у* `{target}`*!*", parse_mode="Markdown")
	except Exception:
		await message.answer("❌ Ошибка."); await state.finish()

# ─── Рассылка ─────────────────────────────────────────────────────────────────

@dp.message_handler(state=WaitTextZFSM.text, content_types=types.ContentTypes.ANY)
async def sendall(message: types.Message, state: FSMContext):
	await state.finish()
	users = await db.get_all_user_ids()
	ok, fail = 0, 0

	# Рассылка только через основной бот (не через зеркала)
	for user_id in users:
		try:
			if message.text:
				await bot.send_message(user_id, message.text, parse_mode='Markdown', reply_markup=del_message2)
			elif message.photo:
				await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption, parse_mode='Markdown', reply_markup=del_message2)
			else:
				await bot.send_message(user_id, message.caption or "📢", parse_mode='Markdown', reply_markup=del_message2)
			ok += 1
		except Exception:
			fail += 1
		await asyncio.sleep(0.05)  # ~20 сообщений/сек, не ловим 429

	await message.answer(f'*🎱 Рассылка окончена!*\n*✅ Доставлено:* {ok}\n*❌ Не доставлено:* {fail}',
		parse_mode='Markdown', reply_markup=main_menu)
	await bot.send_message(bot_logs, f"📢 *Рассылка завершена*\n*✅ {ok} / ❌ {fail}*", parse_mode='Markdown')

# ─── Промокоды (активация) ────────────────────────────────────────────────────

@dp.message_handler(state=WaitPromoFSM.promo)
async def enter_promo(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	code = message.text.strip()
	await state.finish()

	# Проверяем что в имени пользователя есть упоминание бота
	full_name = (message.from_user.first_name or "") + " " + (message.from_user.last_name or "")
	if "Brrown_V2bot" not in full_name and "Brrown_V2bot" not in (message.from_user.username or ""):
		markup = types.InlineKeyboardMarkup()
		markup.add(types.InlineKeyboardButton("✅ Проверить", callback_data='promo_check_name'))
		await message.answer(
			"*❌ Для активации промокода добавьте* `@Brrown_V2bot` *в своё имя или фамилию в Telegram!*\n\n"
			"*Как это сделать:*\n"
			"*1. Зайди в настройки Telegram*\n"
			"*2. Изменить профиль → Имя или Фамилия*\n"
			"*3. Добавь* `@Brrown_V2bot` *и сохрани*\n\n"
			"*После изменения нажми кнопку ниже:*",
			parse_mode="Markdown",
			reply_markup=markup
		)
		return

	promo_data = await db.get_promo(code)
	if not promo_data or promo_data['activations'] <= 0:
		await message.answer("*❌ Промокод не найден или исчерпан!*", parse_mode='Markdown'); return
	# Проверяем — не активировал ли этот юзер уже этот промокод
	if await db.is_promo_used_by(code, uid):
		await message.answer("*❌ Вы уже активировали этот промокод!*", parse_mode='Markdown'); return
	promo_type = promo_data.get('promo_type', 'normal')
	days = promo_data['days']
	await db.mark_promo_used(code, uid)
	# Снижаем счётчик активаций
	pool = await db.get_pool()
	async with pool.acquire() as conn:
		await conn.execute("UPDATE promocode SET activations = activations - 1 WHERE code = $1", code)
	if promo_type == 'premium':
		await db.set_premium(uid, 1)
		await message.answer(f"*✅ Промокод активирован!*\n*👑 Вам выдан Premium навсегда!*", parse_mode='Markdown')
		await bot.send_message(bot_logs, f"🎁 `{uid}` активировал промокод `{code}` — 👑 Премиум", parse_mode='Markdown')
	elif promo_type == 'reports':
		reports_count = days  # в поле days хранится кол-во репортов
		await db.add_free_reports(uid, reports_count)
		await message.answer(f"*✅ Промокод активирован!*\n*🎯 Вам начислено: {reports_count} бесплатных репортов!*", parse_mode='Markdown')
		await bot.send_message(bot_logs, f"🎁 `{uid}` активировал промокод `{code}` — 🎯 {reports_count} репортов", parse_mode='Markdown')
	else:
		new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
		await db.set_subscribe(uid, new_date)
		await message.answer(f"*✅ Промокод активирован!*\n*Ваш подарок: {days} дней!*", parse_mode='Markdown')
		await bot.send_message(bot_logs, f"🎁 `{uid}` активировал промокод `{code}` — {days} дней", parse_mode='Markdown')

# ─── Блокировка/разблокировка (админ) ────────────────────────────────────────

@dp.message_handler(state=BlockUserFSM.user_id)
async def admin_block_user(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown"); await state.finish(); return
		await db.block_user(target)
		await state.finish()
		await message.answer(f"🚫 *Пользователь {target} заблокирован.*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🚫 *Заблокирован* `{target}` *админом* `{message.from_user.id}`", parse_mode="Markdown")
	except Exception:
		await message.answer("❌ Ошибка."); await state.finish()

@dp.message_handler(state=UnblockUserFSM.user_id)
async def admin_unblock_user(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown"); await state.finish(); return
		await db.unblock_user(target)
		await state.finish()
		await message.answer(f"✅ *Пользователь {target} разблокирован.*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"✅ *Разблокирован* `{target}` *админом* `{message.from_user.id}`", parse_mode="Markdown")
	except Exception:
		await message.answer("❌ Ошибка."); await state.finish()

@dp.message_handler(state=DeleteUserFSM.user_id)
async def admin_delete_user(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown"); await state.finish(); return
		await db.delete_user(target)
		await state.finish()
		await message.answer(f"🗑 *Пользователь {target} удалён из базы.*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🗑 *Удалён из БД* `{target}` *админом* `{message.from_user.id}`", parse_mode="Markdown")
	except Exception:
		await message.answer("❌ Ошибка."); await state.finish()

@dp.message_handler(state=CreatePromoFSM.code)
async def create_promo_code(message: types.Message, state: FSMContext):
	code = message.text.strip()
	if not code or len(code) < 3:
		await message.answer("❌ *Код должен быть минимум 3 символа. Введите снова:*", parse_mode="Markdown")
		return
	await state.update_data(code=code)
	data = await state.get_data()
	promo_type = data.get('promo_type', 'normal')
	if promo_type == 'premium':
		# Для премиума дни не нужны — сразу к активациям
		await message.answer(f"👑 *Код:* `{code}`\n\n*Введите количество активаций:*", parse_mode="Markdown")
		await CreatePromoFSM.activations.set()
	elif promo_type == 'reports':
		await message.answer(f"🎯 *Код:* `{code}`\n\n*Введите количество бесплатных репортов:*", parse_mode="Markdown")
		await CreatePromoFSM.days.set()
	else:
		await message.answer(f"💎 *Код:* `{code}`\n\n*Введите количество дней подписки:*", parse_mode="Markdown")
		await CreatePromoFSM.days.set()

@dp.message_handler(state=CreatePromoFSM.days)
async def create_promo_days(message: types.Message, state: FSMContext):
	try:
		days = int(message.text.strip())
		if days <= 0:
			raise ValueError
		await state.update_data(days=days)
		await message.answer(f"💎 *Дней:* `{days}`\n\n*Введите количество активаций:*", parse_mode="Markdown")
		await CreatePromoFSM.activations.set()
	except ValueError:
		await message.answer("❌ Введите число больше 0.")

@dp.message_handler(state=CreatePromoFSM.activations)
async def create_promo_activations(message: types.Message, state: FSMContext):
	try:
		activations = int(message.text.strip())
		if activations <= 0:
			raise ValueError
		data = await state.get_data()
		code = data['code']
		promo_type = data.get('promo_type', 'normal')
		days = data.get('days', 999)  # для премиума дни не используются
		await state.finish()
		try:
			await db.create_promo(code, days, activations, promo_type=promo_type)
			if promo_type == 'premium':
				await message.answer(
					f"✅ *Премиум промокод создан!*\n\n"
					f"👑 *Код:* `{code}`\n"
					f"🔢 *Активаций:* `{activations}`\n"
					f"*└─ Выдаёт: Премиум навсегда*",
					parse_mode="Markdown")
			elif promo_type == 'reports':
				reports_count = days  # в поле days хранится кол-во репортов
				await message.answer(
					f"✅ *Промокод на репорты создан!*\n\n"
					f"🎯 *Код:* `{code}`\n"
					f"🎯 *Репортов:* `{reports_count}`\n"
					f"🔢 *Активаций:* `{activations}`",
					parse_mode="Markdown")
			else:
				await message.answer(
					f"✅ *Промокод создан!*\n\n"
					f"💎 *Код:* `{code}`\n"
					f"📅 *Дней:* `{days}`\n"
					f"🔢 *Активаций:* `{activations}`",
					parse_mode="Markdown")
			await bot.send_message(bot_logs,
				f"💎 *Создан промокод* `{code}` ({'👑 Премиум' if promo_type == 'premium' else ('🎯 ' + str(days) + ' репортов') if promo_type == 'reports' else f'📅 {days} дней'}), {activations} акт. *администратором* `{message.from_user.id}`",
				parse_mode="Markdown")
		except Exception:
			await message.answer(f"❗️ *Промокод* `{code}` *уже существует!*", parse_mode="Markdown")
	except ValueError:
		await message.answer("❌ Введите число больше 0.")

@dp.message_handler(state=AdminAddReportsFSM.user_id)
async def admin_add_reports_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown"); await state.finish(); return
		await state.update_data(user_id=target)
		await message.answer(f"🎯 *ID:* `{target}`\n*Сколько репортов выдать?*", parse_mode="Markdown")
		await AdminAddReportsFSM.amount.set()
	except ValueError:
		await message.answer("❌ Ошибка.")
		await state.finish()

@dp.message_handler(state=AdminAddReportsFSM.amount)
async def admin_add_reports_amount(message: types.Message, state: FSMContext):
	try:
		data = await state.get_data()
		target = data['user_id']
		amount = int(message.text.strip())
		await db.add_free_reports(target, amount)
		await state.finish()
		current = await db.get_free_reports(target)
		await message.answer(f"✅ *Выдано {amount} репортов* `{target}`\n*Итого: {current}*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🎯 *+{amount} репортов* `{target}` *от админа*", parse_mode="Markdown")
		try:
			await bot.send_message(target, f"🎯 *Вам выдано {amount} бесплатных репортов!*\n*Итого: {current}*", parse_mode="Markdown")
		except Exception:
			pass
	except ValueError:
		await message.answer("❌ Введите число.")
		await state.finish()
	except Exception as e:
		await message.answer(f"❌ Ошибка: `{str(e)[:100]}`", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=AdminRemoveReportsFSM.user_id)
async def admin_remove_reports_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown"); await state.finish(); return
		await state.update_data(user_id=target)
		await message.answer(f"🎯 *ID:* `{target}`\n*Сколько репортов забрать?*", parse_mode="Markdown")
		await AdminRemoveReportsFSM.amount.set()
	except Exception:
		await message.answer("❌ Ошибка.")
		await state.finish()

@dp.message_handler(state=AdminRemoveReportsFSM.amount)
async def admin_remove_reports_amount(message: types.Message, state: FSMContext):
	try:
		data = await state.get_data()
		target = data['user_id']
		amount = int(message.text.strip())
		current = await db.get_free_reports(target)
		new_amount = max(0, current - amount)
		await db.set_free_reports(target, new_amount)
		await state.finish()
		await message.answer(f"✅ *Забрано {amount} репортов* `{target}`\n*Осталось: {new_amount}*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🎯 *-{amount} репортов* `{target}` *от админа*", parse_mode="Markdown")
	except ValueError:
		await message.answer("❌ Введите число.")
		await state.finish()

# ─── Запуск ───────────────────────────────────────────────────────────────────

async def on_startup(dp):
	try:
		print(f"DATABASE_URL = {os.environ.get('DATABASE_URL', 'НЕ УСТАНОВЛЕНА')[:50]}")
		await db.init_db()
		print("БД инициализирована успешно.")
	except Exception as e:
		print(f"ОШИБКА БД при старте: {e}")
	botnet_set_bot(bot)
	botnet_set_bot2(bot)
	set_bot_snos(bot)
	set_bot_stress(bot)
	set_bot_channel(bot)
	set_bot_code(bot)
	set_bot_aureport(bot)
	set_bot_tida(bot)
	set_bot_bank(bot)
	await start_all_mirrors()
	print("Бот запущен.")

if __name__ == "__main__":
	import sys
	# Отключаем буферизацию вывода — логи сразу видны в Railway/консоли
	sys.stdout.reconfigure(line_buffering=True)
	while True:
		try:
			print("Бот запускается...", flush=True)
			executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
		except KeyboardInterrupt:
			exit()
		except Exception as e:
			print(f"Ошибка: {e}. Перезапуск через 10 сек...", flush=True)
			time.sleep(10)
