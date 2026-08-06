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
import db

channel_id = config.channel_id
channel2_id = config.channel2_id
admins = config.ADMINS
admins2 = [8904492648]
no_kd = config.NO_KD
bot_logs = config.bot_logs
report_count333 = 200

bot = Bot(token=config.TOKEN)
bot_username = "@Brown_V2_bot"
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
crypto = pyCryptoPayAPI(api_token=config.CRYPTO)
session_folder = 'sessions'
session_folder_prem = 'prem_sessions'
sessions = [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]

last_used_web = {}
last_used_mail = {}
last_used_botnet = {}
last_used_botnet2 = {}
last_used_bot_snos = {}
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
	except Exception:
		return True  # если канал недоступен — не блокируем пользователя

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

class AdminAddReportsFSM(StatesGroup):
	user_id = State()
	amount = State()

class AdminRemoveReportsFSM(StatesGroup):
	user_id = State()
	amount = State()

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
		try:
			with open("mails.txt", "r", encoding="utf-8") as f:
				mails_count = len([l for l in f if l.strip()])
		except FileNotFoundError:
			mails_count = 0
		text = (
			">🤖 *Админ меню:*\n\n📊 *Статистика:*\n"
			f"*├─👥 Всего пользователей:* `{users_count}`\n"
			f"*├─🕒 Сессий в ботнете:* `{sessions_count}`\n"
			f"*├─👑 Сессий в премиум ботнете:* `{sessions_count_prem}`\n"
			f"*├─🌐 Web\-Reports:* `{report_count333}`\n"
			f"*└─✉️ Почт добавлено:* `{mails_count}`\n\n"
			"*/promo PROMOCODE DAYS ACTIVATIONS \- создать промокод*\n"
			"*/on \- включить бота*\n*/off \- выключить бота*\n"
			"*/addwl ID \- добавить в вайтлист*"
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

# ─── Подписки / оплата ────────────────────────────────────────────────────────

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'))
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

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('check_status_'))
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

@dp.message_handler(commands=['start'])
async def welcome(message: types.Message):
	if await is_blocked(message.from_user.id):
		return
	if check_rate_limit(message.from_user.id):
		await block_user(message.from_user.id)
		await message.reply("Превысили лимит запросов, заблокированы.")
		return
	uid = message.chat.id
	is_new = not await db.user_exists(uid)
	await db.add_user(uid)

	if not await is_verified(uid):
		code = generate_captcha_text()
		_captcha_codes[uid] = code
		img = generate_captcha_image(code)
		await bot.send_photo(uid, photo=img,
			caption=f"*Привет, {message.from_user.first_name}!*\n\n*Докажи, что ты не робот 🤖*\n*└─ Введи код с картинки:*",
			parse_mode="Markdown")
		# Сохраняем реф-аргумент в FSM — применим только после прохождения капчи
		await WaitCaptchaFSM.code.set()
		if is_new:
			args = message.get_args()
			if args and args.startswith("ref_"):
				async with dp.current_state(user=uid).proxy() as fsm_data:
					fsm_data['ref_arg'] = args
		return
	await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
	# Закреплённое сообщение при каждом /start
	pin_msg = await bot.send_message(uid, "📌 *Сохрани нас чтобы не потерять\!* — brown\.xo\.je", parse_mode="MarkdownV2")
	try:
		await bot.pin_chat_message(uid, pin_msg.message_id, disable_notification=True)
	except Exception:
		pass
	await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
		caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
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
		# Закреплённое сообщение после капчи
		pin_msg = await bot.send_message(uid, "📌 *Сохрани нас чтобы не потерять\!* — brown\.xo\.je", parse_mode="MarkdownV2")
		try:
			await bot.pin_chat_message(uid, pin_msg.message_id, disable_notification=True)
		except Exception:
			pass
		await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
			caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
			parse_mode="MarkdownV2", reply_markup=menu)
	else:
		code = generate_captcha_text()
		_captcha_codes[uid] = code
		await bot.send_photo(uid, photo=generate_captcha_image(code),
			caption="*❌ Неверно! Попробуй ещё раз:*", parse_mode="Markdown")

# ─── Главный callback хендлер ─────────────────────────────────────────────────

@dp.callback_query_handler(lambda call: True)
async def callback_inline(call: types.CallbackQuery):
	try:
		uid = call.from_user.id
		if await is_blocked(uid):
			return
		if check_rate_limit(uid):
			await block_user(uid)
			await call.message.answer("Превысили лимит, заблокированы.")
			return
		if not await check_user_in_db(uid):
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*Пропишите /start*", parse_mode="Markdown")
			return
		if not await subsribe_channel(uid, channel_id) or not await subsribe_channel(uid, channel2_id):
			# Создаём временные invite links на 1 минуту
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
				types.InlineKeyboardButton("[🔎] Проверить", callback_data='back')
			)
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*⚠️ Подпишитесь на каналы!*\n*└─ Ссылки действуют 1 минуту*", parse_mode="Markdown", reply_markup=temp_check_markup)
			return

		user_data = await db.get_user(uid)
		subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
		premium = int(user_data['premium'])
		username = call.from_user.username or "None"
		fullname = call.from_user.first_name

		d = call.data

		if d == 'functions':
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*Заказ*\n\n>*Посмотрите Мануал*", parse_mode="MarkdownV2", reply_markup=functions)
		elif d == 'profile':
			sub_text = "Истекла" if subscribe < datetime.now() else f"осталось {(subscribe - datetime.now()).days} дней"
			prem = "Да" if premium == 1 else "Нет"
			free_reports = await db.get_free_reports(uid)
			ref_count = await db.get_referral_count(uid)
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=f"*Профиль*\n\n▪️ *Имя: {fullname}*\n▪️ *ID: {uid}*\n▪️ *@{username}*\n▪️ *Премиум: {prem}*\n▪️ *Бесплатных репортов: {free_reports}*\n▪️ *Рефералов: {ref_count}*\n\n⏳ *{sub_text}*",
				parse_mode="Markdown", reply_markup=back_markup)
		elif d == "back":
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption='>*Добро пожаловать в Brown V2\!*\n\n*Инструмент для работы с файлами\.*',
				parse_mode="MarkdownV2", reply_markup=menu)
		elif d == "information":
			# Генерируем временную ссылку на канал на 1 минуту
			try:
				import time as _time
				expire = int(_time.time()) + 60
				link = await bot.create_chat_invite_link(channel_id, expire_date=expire, member_limit=1)
				channel_invite = link.invite_link
			except Exception as e:
				print(f"Ошибка создания invite link для информации: {e}", flush=True)
				channel_invite = config.bot_channel_link
			dyn_info_markup = types.InlineKeyboardMarkup(row_width=1)
			dyn_info_markup.add(
				types.InlineKeyboardButton("🔥 Канал (1 мин)", url=channel_invite),
				types.InlineKeyboardButton("📄 Мануал", url='https://teletype.in/@brownv2/manual'),
				keyboards.back
			)
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=">*Информация*", parse_mode="MarkdownV2", reply_markup=dyn_info_markup)
		elif d == "shop":
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="⚙️ *Ассортимент*\n\n>*└─ 1 день \- 1$ / 100₽*\n>*└─ 3 дня \- 2$ / 175₽*\n>*└─ 7 дней \- 4$ / 350₽*\n>*└─ 30 дней \- 8$ / 700₽*\n>*└─ Навсегда \- 6$ / 500₽ \[\-70%\]*\n\n>*👑 Премиум: 5$ / 400₽ \[\-50%\]*",
				parse_mode="MarkdownV2", reply_markup=shop_markup)
		elif d == "buyforadmins":
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=">*💳 Выберите способ оплаты\:*", parse_mode="MarkdownV2", reply_markup=keyboards.pay_method)
		elif d == "yoomoney":
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=f"🇷🇺 *ЮMoney \(Юмани\)*\n\nРеквизиты: `5599002073240212`\nКомментарий: `{uid}, претензий не имею`\n\nПосле оплаты @TariSmit",
				parse_mode="MarkdownV2", reply_markup=back_markup)
		elif d == "tinkoff":
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=f"🇷🇺 *ЮMoney \(Юмани\)*\n\nРеквизиты: `5599002073240212`\nКомментарий: `{uid}, претензий не имею`\n\nПосле оплаты @TariSmit",
				parse_mode="MarkdownV2", reply_markup=back_markup)
		elif d == "sberbank":
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=f"🇷🇺 *ЮMoney \(Юмани\)*\n\nРеквизиты: `5599002073240212`\nКомментарий: `{uid}, претензий не имею`\n\nПосле оплаты @TariSmit",
				parse_mode="MarkdownV2", reply_markup=back_markup)
		elif d == "preminfo":
			await bot.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="👑 *Премиум*\n\n>*└─ почты, веб, прем отправку*\n\n‼️ Покупается как ДОПОЛНЕНИЕ к подписке ‼️",
				parse_mode="MarkdownV2", reply_markup=back_markup)
		elif d == "close":
			await bot.delete_message(call.message.chat.id, call.message.message_id)
		elif d == "go_to_main_menu":
			await bot.delete_message(call.message.chat.id, call.message.message_id)
			await bot.send_photo(call.message.chat.id, photo=open('material/menu.png', 'rb'),
				caption='>*Добро пожаловать в Brown V2\!*', parse_mode="MarkdownV2", reply_markup=menu)
		elif d == 'add_subsribe' and uid in admins:
			await bot.send_message(call.message.chat.id, '🎱 *Выдача подписки*\n*└─Введите ID:*', parse_mode="Markdown")
			await AddSubscribeFSM.user_id.set()
		elif d == 'clear_subscribe' and uid in admins:
			await bot.send_message(call.message.chat.id, '🎱 *Сброс подписки*\n*└─Введите ID:*', parse_mode="Markdown")
			await ClearSubscribeFSM.user_id.set()
		elif d == 'add_prem' and uid in admins:
			await bot.send_message(call.message.chat.id, '🎱 *Выдача премиума*\n*└─Введите ID:*', parse_mode="Markdown")
			await AddPremFSM.user_id.set()
		elif d == 'clear_prem' and uid in admins:
			await bot.send_message(call.message.chat.id, '🎱 *Сброс премиума*\n*└─Введите ID:*', parse_mode="Markdown")
			await ClearPremFSM.user_id.set()
		elif d == 'send_all' and uid in admins and uid in admins2:
			await bot.send_message(call.message.chat.id, '🎱 *Рассылка*\n*└─Введите текст:*', parse_mode="Markdown")
			await WaitTextZFSM.text.set()
		elif d == 'block_user_admin' and uid in admins:
			await bot.send_message(call.message.chat.id, '🚫 *Блокировка*\n*└─Введите ID пользователя:*', parse_mode="Markdown")
			await BlockUserFSM.user_id.set()
		elif d == 'unblock_user_admin' and uid in admins:
			await bot.send_message(call.message.chat.id, '✅ *Разблокировка*\n*└─Введите ID пользователя:*', parse_mode="Markdown")
			await UnblockUserFSM.user_id.set()
		elif d.startswith('users_list_') and uid in admins:
			page = int(d.split('_')[2])
			PAGE_SIZE = 10
			users = await db.get_users_page(offset=page * PAGE_SIZE, limit=PAGE_SIZE)
			total = await db.get_users_count()
			total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

			if not users:
				await bot.answer_callback_query(call.id, "Больше пользователей нет", show_alert=False)
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

			await bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=nav)

		elif d.startswith('admin_mirrors_') and uid in admins:
			page = int(d.split('_')[2])
			PAGE_SIZE = 8
			all_mirrors = await db.get_all_mirrors()
			total = len(all_mirrors)
			total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
			page_mirrors = all_mirrors[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

			if not all_mirrors:
				await bot.answer_callback_query(call.id, "Зеркал нет.", show_alert=False)
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

			await bot.send_message(call.message.chat.id, "\n".join(lines), parse_mode="Markdown", reply_markup=nav)

		elif d == 'admin_add_reports' and uid in admins:
			await bot.send_message(call.message.chat.id, '🎯 *Выдача репортов*\n*└─ Введите ID пользователя:*', parse_mode="Markdown")
			await AdminAddReportsFSM.user_id.set()

		elif d == 'admin_remove_reports' and uid in admins:
			await bot.send_message(call.message.chat.id, '🎯 *Отзыв репортов*\n*└─ Введите ID пользователя:*', parse_mode="Markdown")
			await AdminRemoveReportsFSM.user_id.set()
		elif d == 'promo':
			await bot.send_message(call.message.chat.id, '🎱 *Активация промокода*\n*└─Введите промокод:*', parse_mode="Markdown")
			await WaitPromoFSM.promo.set()

		# ─── Реферальная система ───────────────────────────────────────────────
		elif d == 'referral':
			ref_count = await db.get_referral_count(uid)
			ref_link = f"https://t.me/{bot_username[1:]}?start=ref_{uid}"
			await bot.edit_message_caption(
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
				await bot.answer_callback_query(call.id, f"❌ Недостаточно рефералов! У вас {ref_count}/10", show_alert=True)
			else:
				await db.spend_referrals(uid, 10)
				new_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
				await db.set_subscribe(uid, new_date)
				remaining = ref_count - 10
				await bot.answer_callback_query(call.id, "✅ Обменяно! +1 день подписки", show_alert=True)
				await bot.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						f"👥 *Реферальная система*\n\n"
						f"*└─ Ваших рефералов: {remaining}*\n\n"
						f"📎 *Ваша ссылка:*\n`https://t.me/{bot_username[1:]}?start=ref_{uid}`\n\n"
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
			await bot.edit_message_caption(
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
			await bot.send_message(
				call.message.chat.id,
				"🪞 *Создание зеркала*\n\n"
				"*1.* Открой @BotFather\n"
				"*2.* Напиши /newbot\n"
				"*3.* Придумай имя и username боту\n"
				"*4.* Скопируй токен и отправь его сюда:\n\n"
				"*Формат:* `1234567890:ABCdef...`",
				parse_mode="Markdown"
			)
			await WaitMirrorTokenFSM.token.set()

		elif d == 'mirror_list':
			mirrors = await db.get_user_mirrors(uid)
			if not mirrors:
				await bot.answer_callback_query(call.id, "У вас нет зеркал.", show_alert=True)
				return
			lines = ["🪞 *Ваши зеркала:*\n"]
			for i, m in enumerate(mirrors, 1):
				lines.append(f"*{i}.* `{m['bot_username']}`")
			await bot.send_message(
				call.message.chat.id,
				"\n".join(lines),
				parse_mode="Markdown",
				reply_markup=keyboards.back_markup
			)

		# ─── Колесо удачи ──────────────────────────────────────────────────────
		elif d == 'wheel':
			last_spin = await db.get_wheel_last_spin(uid)
			now = datetime.now()
			if last_spin and (now - last_spin).total_seconds() < 6 * 3600:
				remaining = timedelta(seconds=6*3600) - (now - last_spin)
				h = int(remaining.total_seconds() // 3600)
				m = int((remaining.total_seconds() % 3600) // 60)
				await bot.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						f"🎡 *Колесо удачи*\n\n"
						f"⏳ *Следующий спин через: {h}ч {m}м*\n\n"
						f"🎰 *Призы:*\n"
						f"▪️ 55% — Ничего\n"
						f"▪️ 20% — 1 бесплатный репорт\n"
						f"▪️ 10% — Подписка на 1 день\n"
						f"▪️ 9% — 3 бесплатных репорта\n"
						f"▪️ 5% — Премиум\n"
						f"▪️ 1% — Подписка навсегда 🍀"
					),
					parse_mode="Markdown", reply_markup=keyboards.wheel_markup
				)
			else:
				await bot.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						f"🎡 *Колесо удачи*\n\n"
						f"🎰 *Призы:*\n"
						f"▪️ 55% — Ничего\n"
						f"▪️ 20% — 1 бесплатный репорт\n"
						f"▪️ 10% — Подписка на 1 день\n"
						f"▪️ 9% — 3 бесплатных репорта\n"
						f"▪️ 5% — Премиум\n"
						f"▪️ 1% — Подписка навсегда 🍀\n\n"
						f"✅ *Можно крутить!*"
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
					await bot.answer_callback_query(
						call.id, "❌ Крутить нельзя — у вас активный выигранный премиум!", show_alert=True
					)
					return
				if last_prize in ("forever", "sub_1d") and subscribe > now:
					await bot.answer_callback_query(
						call.id, "❌ Крутить нельзя — у вас активная выигранная подписка!", show_alert=True
					)
					return

			if last_spin and (now - last_spin).total_seconds() < 6 * 3600:
				remaining = timedelta(seconds=6*3600) - (now - last_spin)
				h = int(remaining.total_seconds() // 3600)
				m = int((remaining.total_seconds() % 3600) // 60)
				await bot.answer_callback_query(call.id, f"⏳ Следующий спин через {h}ч {m}м", show_alert=True)
				return

			await db.set_wheel_last_spin(uid, now)

			import random as _random
			roll = _random.random() * 100
			if roll < 1:
				prize = "forever"
			elif roll < 6:
				prize = "premium"
			elif roll < 15:
				prize = "sub_1d"
			elif roll < 24:
				prize = "reports_3"
			elif roll < 44:
				prize = "reports_1"
			else:
				prize = "nothing"

			await db.set_wheel_prize(uid, prize)

			prize_texts = {
				"forever": ("🍀 *Невероятно! Подписка навсегда!*", "🍀 Подписка навсегда"),
				"premium": ("⭐️ *Вам выдан Премиум!*", "⭐️ Премиум"),
				"sub_1d": ("🎉 *Подписка на 1 день!*", "🎉 Подписка 1 день"),
				"reports_3": ("🎯 *3 бесплатных репорта!*", "🎯 3 репорта"),
				"reports_1": ("🎯 *1 бесплатный репорт!*", "🎯 1 репорт"),
				"nothing": ("😔 *Ничего... Повезёт в следующий раз!*", "😔 Ничего"),
			}
			text, log_text = prize_texts[prize]

			if prize == "forever":
				await db.set_subscribe(uid, "2099-12-31 23:59:59")
			elif prize == "premium":
				await db.set_premium(uid, 1)
			elif prize == "sub_1d":
				new_date = (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
				await db.set_subscribe(uid, new_date)
			elif prize == "reports_3":
				await db.add_free_reports(uid, 3)
			elif prize == "reports_1":
				await db.add_free_reports(uid, 1)

			if prize in ("forever", "premium", "sub_1d"):
				next_spin_note = "🔒 *Следующий спин доступен после истечения выигранной подписки*"
			else:
				next_spin_note = "⏳ *Следующий спин через 6 часов*"

			await bot.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"🎡 *Колесо удачи*\n\n"
					f"🎰 Результат:\n{text}\n\n"
					f"{next_spin_note}"
				),
				parse_mode="Markdown", reply_markup=back_markup
			)
			await bot.send_message(bot_logs, f"🎡 `{uid}` крутил колесо — {log_text}", parse_mode="Markdown")
		
		# Методы
		def sub_expired():
			return subscribe < datetime.now()
		def bot_off():
			return bot_status == 0

		if d == "web_method":
			if sub_expired(): await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0: await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужен премиум\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_web and (datetime.now() - last_used_web[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (datetime.now() - last_used_web[uid])
				await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=back_markup); return
			await call.message.answer("✉️ *Введите текст:*", parse_mode="Markdown")
			await WaitTextFSM.text.set()

		elif d == "mail_method":
			if sub_expired(): await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0: await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужен премиум\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_mail and (datetime.now() - last_used_mail[uid]) < timedelta(minutes=300):
				rem = timedelta(minutes=300) - (datetime.now() - last_used_mail[uid])
				await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {rem.seconds//60} мин*', parse_mode="Markdown", reply_markup=back_markup); return
			await call.message.answer("📌 *Введите тему:*", parse_mode="Markdown")
			await WaitMailTopicFSM.topic.set()

		elif d == "botnet_method":
			free_reports = await db.get_free_reports(uid)
			if sub_expired() and free_reports == 0:
				await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати или получи бесплатный репорт\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_botnet and (datetime.now() - last_used_botnet[uid]) < timedelta(minutes=5):
				rem = timedelta(minutes=5) - (datetime.now() - last_used_botnet[uid])
				await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot.send_message(call.message.chat.id, '*Ссылка на сообщение:*\n`https://t.me/username/123`', parse_mode="Markdown")
			await WaitLinkFSM.link.set()

		elif d == "prem_botnet_method":
			if sub_expired(): await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0: await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Нужен премиум\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_botnet2 and (datetime.now() - last_used_botnet2[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (datetime.now() - last_used_botnet2[uid])
				await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'❌ *Жди {rem.seconds//60} мин*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot.send_message(call.message.chat.id, '*Ссылка на сообщение:*\n`https://t.me/username/123`', parse_mode="Markdown")
			await WaitLinkPREMFSM.link.set()

		# ─── Бот-метод ────────────────────────────────────────────────────────
		elif d == "bot_method":
			if bot_off():
				await bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			await bot.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption="🤖 *Бот-метод*\n\n*└─ Выберите причину жалобы:*",
				parse_mode="Markdown", reply_markup=keyboards.bot_reason_markup
			)

		elif d in ("bot_reason_personal", "bot_reason_adult", "bot_reason_children", "bot_reason_snoser", "bot_reason_other"):
			reason_map = {
				"bot_reason_personal": ("personal", "🔐 Персональные данные"),
				"bot_reason_adult": ("adult", "🔞 18+ контент"),
				"bot_reason_children": ("children", "👶 Детский контент"),
				"bot_reason_snoser": ("snoser", "💥 Сносер"),
				"bot_reason_other": ("other", "📝 Прочее"),
			}
			reason_key, reason_label = reason_map[d]
			async with dp.current_state(user=uid).proxy() as data_fsm:
				data_fsm['bot_reason'] = reason_key
			await WaitBotLinkFSM.link.set()
			await bot.send_message(
				call.message.chat.id,
				f"🤖 *Причина: {reason_label}*\n\n*Введите username бота или ссылку:*\n`@username` или `https://t.me/botname`",
				parse_mode="Markdown"
			)

	except Exception as e:
		print(f"callback_inline: {e}")

# ─── FSM хендлеры ─────────────────────────────────────────────────────────────

@dp.message_handler(state=WaitTextFSM.text)
async def send_web_reports(message: types.Message, state: FSMContext):
	await state.finish()
	uid = message.from_user.id
	last_used_web[uid] = datetime.now()  # КД ставится только после реального запуска
	username = message.from_user.username or "без username"
	log_path = generate_log_filename()
	async with aiohttp.ClientSession() as session:
		success, error = await web(session=session, message_text=message.text,
			count=report_count333, log_path=log_path, user_id=uid, username=username)
	try:
		await message.answer_document(types.InputFile(log_path),
			caption=f"⚙️ *Веб*\n🟢 *Успешно: {success}*\n🔴 *Не удалось: {error}*",
			reply_markup=main_menu, parse_mode="Markdown")
	except Exception: pass
	try:
		await bot.send_document(bot_logs, types.InputFile(log_path),
			caption=f"📈 *Веб*\n🟢 {success}\n🔴 {error}\n👤 {uid} (@{username})", parse_mode="Markdown")
	except Exception: pass
	try: os.remove(log_path)
	except Exception: pass

@dp.message_handler(state=WaitMailTopicFSM.topic)
async def get_mail_subject(message: types.Message, state: FSMContext):
	await state.update_data(subject=message.text)
	last_used_mail[message.from_user.id] = datetime.now()  # КД ставится после ввода темы (реальный старт)
	await message.answer("✉️ *Введите текст письма:*", parse_mode="Markdown")
	await WaitMailTextFSM.text.set()

@dp.message_handler(state=WaitMailTextFSM.text)
async def start_bulk_email(message: types.Message, state: FSMContext):
	data = await state.get_data()
	subject = data.get("subject")
	await state.finish()
	mails = load_mails()
	if not mails:
		await message.answer("❌ *Нет почт!*", parse_mode="Markdown"); return
	receiver_emails = ["dmca@telegram.org","support@telegram.org","abuse@telegram.org","stopCA@telegram.org"]
	success, error, log_path = await send_bulk_emails(
		subject, message.text, mails, receiver_emails,
		user_id=message.from_user.id, username=message.from_user.username or "None",
		bot=bot, chat_id=message.from_user.id)
	try:
		await bot.send_document(message.from_user.id, types.InputFile(log_path),
			caption=f"⚙️ *Почты*\n🟢 {success}\n🔴 {error}", parse_mode="Markdown", reply_markup=main_menu)
		await bot.send_document(bot_logs, types.InputFile(log_path),
			caption=f"📈 *Почты*\n🟢 {success}\n🔴 {error}\n👤 {message.from_user.id}", parse_mode="Markdown")
	except Exception as e: print(e)
	try: os.remove(log_path)
	except Exception: pass

@dp.message_handler(state=WaitLinkFSM.link)
async def botnet_step1_normal(message: types.Message, state: FSMContext):
	url = message.text
	await state.finish()
	uid = message.from_user.id
	username = message.from_user.username or "None"
	try:
		chat_username, message_id = await extract_username_and_message_id(url)
		# Проверяем подписку — если истекла, пробуем использовать бесплатный репорт
		user_data = await db.get_user(uid)
		subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
		if subscribe < datetime.now():
			used = await db.use_free_report(uid)
			if not used:
				await bot.send_message(uid, '❌ *Нет подписки и бесплатных репортов!*', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
				return
			free_left = await db.get_free_reports(uid)
			await bot.send_message(uid, f'🎯 *Использован бесплатный репорт! Осталось: {free_left}*', parse_mode=ParseMode.MARKDOWN)
		last_used_botnet[uid] = datetime.now()
		await bot.send_message(uid, '📤 *Запустил отправку...*', parse_mode=ParseMode.MARKDOWN)
		await botnet_main(chat_username, message_id, uid, username, url)
	except ValueError:
		await bot.send_message(uid, '*⭕️ Неверная ссылка!*', parse_mode=ParseMode.MARKDOWN)
	except Exception as e:
		print(f"[BOTNET] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await bot.send_message(uid, f'❌ *Ошибка ботнета:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)

@dp.message_handler(state=WaitLinkPREMFSM.link)
async def botnet_step1_premium(message: types.Message, state: FSMContext):
	url = message.text
	await state.finish()
	uid = message.from_user.id
	username = message.from_user.username or "None"
	try:
		chat_username, message_id = await extract_username_and_message_id2(url)
		last_used_botnet2[uid] = datetime.now()  # КД ставится только после валидной ссылки
		await bot.send_message(uid, '👑 *Запустил отправку...*', parse_mode=ParseMode.MARKDOWN)
		await botnet_main2(chat_username, message_id, uid, username, url)
	except ValueError:
		await bot.send_message(uid, '*⭕️ Неверная ссылка!*', parse_mode=ParseMode.MARKDOWN)
	except Exception as e:
		print(f"[PREM] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await bot.send_message(uid, f'❌ *Ошибка премиум-ботнета:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)

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

		# Лимит зеркал убран — неограниченно
	await state.finish()

	# Проверяем не сдан ли токен уже
	if await db.token_exists(token):
		await bot.send_message(uid, "❌ *Этот токен уже зарегистрирован!*", parse_mode="Markdown")
		return

	# Проверяем токен через getMe
	wait_msg = await bot.send_message(uid, "⏳ *Проверяем токен...*", parse_mode="Markdown")
	bot_username = await validate_token(token)
	try:
		await bot.delete_message(uid, wait_msg.message_id)
	except Exception:
		pass

	if not bot_username:
		await bot.send_message(uid, "❌ *Токен невалидный или бот не существует!*\n*Проверь и попробуй снова.*", parse_mode="Markdown")
		return

	# Сохраняем и запускаем зеркало
	await db.add_mirror(uid, token, bot_username)
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
		f"🤖 *Бот:* `{bot_username}`\n"
		f"📊 *Всего зеркал: {mirror_count}*"
		f"{bonus_msg}\n\n"
		f"*Зеркало уже работает и принимает пользователей!*",
		parse_mode="Markdown", reply_markup=main_menu
	)
	await bot.send_message(
		bot_logs,
		f"🪞 *Новое зеркало*\n"
		f"*└─ Пользователь:* `{uid}`\n"
		f"*└─ Бот:* `{bot_username}`\n"
		f"*└─ Всего зеркал:* `{mirror_count}`",
		parse_mode="Markdown"
	)

@dp.message_handler(state=WaitBotLinkFSM.link)
async def bot_snos_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()

	# Проверяем подписку и КД здесь — на этапе ввода ссылки
	user_data = await db.get_user(uid)
	subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
	if subscribe < datetime.now():
		await state.finish()
		await bot.send_message(uid, ">❌ *оплати\!*", parse_mode="MarkdownV2", reply_markup=main_menu)
		return
	if uid in last_used_bot_snos and (datetime.now() - last_used_bot_snos[uid]) < timedelta(minutes=30):
		rem = timedelta(minutes=30) - (datetime.now() - last_used_bot_snos[uid])
		await state.finish()
		await bot.send_message(uid, f'❌ *Жди {rem.seconds//60} мин {rem.seconds%60} сек*', parse_mode="Markdown", reply_markup=main_menu)
		return

	# Нормализуем — принимаем @username или t.me/username или полный URL
	if raw.startswith("https://t.me/"):
		bot_target = "@" + raw.replace("https://t.me/", "").split("/")[0].split("?")[0]
	elif raw.startswith("t.me/"):
		bot_target = "@" + raw.replace("t.me/", "").split("/")[0].split("?")[0]
	elif raw.startswith("@"):
		bot_target = raw.split("/")[0]
	else:
		bot_target = "@" + raw.split("/")[0].split("?")[0]

	data_fsm = await state.get_data()
	reason_key = data_fsm.get('bot_reason', 'other')
	await state.finish()

	last_used_bot_snos[uid] = datetime.now()
	await bot.send_message(uid, f'🤖 *Запустил жалобы на {bot_target}...*', parse_mode=ParseMode.MARKDOWN)

	try:
		await main_bot_snos(bot_target, reason_key, uid, username, bot_target)
	except Exception as e:
		print(f"[BOT-SNOS] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await bot.send_message(uid, f'❌ *Ошибка бот-метода:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)

# ─── Управление подписками (админ) ────────────────────────────────────────────

@dp.message_handler(state=AddSubscribeFSM.user_id)
async def add_sub_uid(message: types.Message, state: FSMContext):
	try:
		await state.update_data(user_id=int(message.text))
		await message.answer("🎱 *Введите количество дней:*", parse_mode=ParseMode.MARKDOWN)
		await AddSubscribeFSM.days.set()
	except ValueError:
		await message.answer("❌ ID должен быть числом."); await state.finish()

@dp.message_handler(state=AddSubscribeFSM.days)
async def add_sub_days(message: types.Message, state: FSMContext):
	data = await state.get_data()
	target = data['user_id']
	new_date = (datetime.now() + timedelta(days=int(message.text))).strftime("%Y-%m-%d %H:%M:%S")
	await db.set_subscribe(target, new_date)
	await state.finish()
	await bot.send_message(target, f"🎱 *Подписка обновлена до* `{new_date}`", parse_mode="Markdown", reply_markup=del_message2)
	await message.answer("🎱 *Готово!*", parse_mode="Markdown")
	await bot.send_message(bot_logs, f"🎱 *Выдана подписка* `{target}` до `{new_date}`", parse_mode="Markdown")

@dp.message_handler(state=ClearSubscribeFSM.user_id)
async def clear_sub_uid(message: types.Message, state: FSMContext):
	target = int(message.text)
	await db.set_subscribe(target, "1999-01-01 00:00:00")
	await state.finish()
	await bot.send_message(target, "*🎱 Подписка сброшена.*", parse_mode="Markdown", reply_markup=del_message2)
	await message.answer("*🎱 Сброшено!*", parse_mode="Markdown")

@dp.message_handler(state=AddPremFSM.user_id)
async def add_prem_uid(message: types.Message, state: FSMContext):
	target = int(message.text)
	await db.set_premium(target, 1)
	await state.finish()
	await bot.send_message(target, "*👑 Вам выдан Premium.*", parse_mode="Markdown", reply_markup=del_message2)
	await message.answer("*🎱 Премиум выдан!*", parse_mode="Markdown")

@dp.message_handler(state=ClearPremFSM.user_id)
async def clear_prem_uid(message: types.Message, state: FSMContext):
	target = int(message.text)
	await db.set_premium(target, 0)
	await state.finish()
	await bot.send_message(target, "*🎱 Премиум сброшен.*", parse_mode="Markdown", reply_markup=del_message2)
	await message.answer("*🎱 Сброшено!*", parse_mode="Markdown")

# ─── Рассылка ─────────────────────────────────────────────────────────────────

@dp.message_handler(state=WaitTextZFSM.text, content_types=types.ContentTypes.ANY)
async def sendall(message: types.Message, state: FSMContext):
	await state.finish()
	users = await db.get_all_user_ids()
	ok, fail = 0, 0
	for user_id in users:
		try:
			if message.text:
				await bot.send_message(user_id, message.text, parse_mode='Markdown', reply_markup=del_message)
			elif message.photo:
				await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption, parse_mode='Markdown', reply_markup=del_message)
			else:
				await message.copy_to(user_id)
			ok += 1
		except Exception:
			fail += 1
	await message.answer(f'*🎱 Рассылка окончена!*\n*✅ Доставлено:* {ok}\n*❌ Не доставлено:* {fail}',
		parse_mode='Markdown', reply_markup=main_menu)

# ─── Промокоды (активация) ────────────────────────────────────────────────────

@dp.message_handler(state=WaitPromoFSM.promo)
async def enter_promo(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	code = message.text.strip()
	await state.finish()
	promo_data = await db.get_promo(code)
	if not promo_data or promo_data['activations'] <= 0:
		await message.answer("*❌ Промокод не найден или исчерпан!*", parse_mode='Markdown'); return
	days = promo_data['days']
	new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
	await db.use_promo(code, uid, new_date)
	await message.answer(f"*✅ Промокод активирован!*\n*Ваш подарок: {days} дней!*", parse_mode='Markdown')
	await bot.send_message(bot_logs, f"🎁 `{uid}` активировал промокод `{code}` — {days} дней", parse_mode='Markdown')

# ─── Блокировка/разблокировка (админ) ────────────────────────────────────────

@dp.message_handler(state=BlockUserFSM.user_id)
async def admin_block_user(message: types.Message, state: FSMContext):
	try:
		target = int(message.text.strip())
		await db.block_user(target)
		await state.finish()
		await message.answer(f"🚫 *Пользователь {target} заблокирован.*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🚫 *Заблокирован* `{target}` *админом* `{message.from_user.id}`", parse_mode="Markdown")
	except ValueError:
		await message.answer("❌ ID должен быть числом.")
		await state.finish()

@dp.message_handler(state=UnblockUserFSM.user_id)
async def admin_unblock_user(message: types.Message, state: FSMContext):
	try:
		target = int(message.text.strip())
		await db.unblock_user(target)
		await state.finish()
		await message.answer(f"✅ *Пользователь {target} разблокирован.*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"✅ *Разблокирован* `{target}` *админом* `{message.from_user.id}`", parse_mode="Markdown")
	except ValueError:
		await message.answer("❌ ID должен быть числом.")
		await state.finish()

@dp.message_handler(state=AdminAddReportsFSM.user_id)
async def admin_add_reports_uid(message: types.Message, state: FSMContext):
	try:
		await state.update_data(user_id=int(message.text.strip()))
		await message.answer("🎯 *Сколько репортов выдать?*", parse_mode="Markdown")
		await AdminAddReportsFSM.amount.set()
	except ValueError:
		await message.answer("❌ ID должен быть числом.")
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

@dp.message_handler(state=AdminRemoveReportsFSM.user_id)
async def admin_remove_reports_uid(message: types.Message, state: FSMContext):
	try:
		await state.update_data(user_id=int(message.text.strip()))
		await message.answer("🎯 *Сколько репортов забрать?*", parse_mode="Markdown")
		await AdminRemoveReportsFSM.amount.set()
	except ValueError:
		await message.answer("❌ ID должен быть числом.")
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
