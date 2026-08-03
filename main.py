from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode, InputFile, ContentType, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, Message
import aiosqlite
import datetime
from datetime import datetime, timedelta
from pyCryptoPayAPI import pyCryptoPayAPI
import config
import keyboards
import time
import os
import shutil
import random
import telethon
from telethon.tl.types import PeerUser
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.messages import ReportRequest
import sqlite3
import traceback
import asyncio
from telethon import types as telethon_types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
import aiohttp
from web_snos import web, generate_log_filename 
import os
import aiofiles
from mail_snos import send_bulk_emails, load_mails 
from botnet_snos import extract_username_and_message_id, main as botnet_main
from botnet_snos_premium import extract_username_and_message_id2, main2 as botnet_main2
from captcha import generate_captcha_text, generate_captcha_image

channel_id = config.channel_id
channel2_id = config.channel2_id
admins = config.ADMINS
admins2 = [69717177, 60693380]
no_kd = config.NO_KD
bot_logs = config.bot_logs

report_count333 = 200

bot = Bot(token=config.TOKEN)
bot_username = "@abilityddd_bot"
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

user_requests = {}
REQUEST_LIMIT = 3
TIME_FRAME = 1

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

async def check_user_in_db(user_id):
	async with aiosqlite.connect('users.db') as conn:
		async with conn.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,)) as cursor:
			result = await cursor.fetchone()
	return result is not None

async def is_blocked(user_id: int) -> bool:
	async with aiosqlite.connect("blocked_users.db") as db:
		async with db.execute("SELECT 1 FROM blocked WHERE user_id = ?", (user_id,)) as cursor:
			return await cursor.fetchone() is not None

async def block_user(user_id: int):
	async with aiosqlite.connect("blocked_users.db") as db:
		await db.execute("INSERT OR IGNORE INTO blocked(user_id) VALUES (?)", (user_id,))
		await db.commit()

async def is_verified(user_id: int) -> bool:
	async with aiosqlite.connect("users.db") as db:
		async with db.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,)) as cursor:
			row = await cursor.fetchone()
			if row is None:
				return False
			return bool(row[0])

async def set_verified(user_id: int):
	async with aiosqlite.connect("users.db") as db:
		await db.execute("UPDATE users SET verified = 1 WHERE user_id = ?", (user_id,))
		await db.commit()

def check_rate_limit(user_id: int) -> bool:
	now = datetime.now()
	if user_id not in user_requests:
		user_requests[user_id] = []
	user_requests[user_id] = [t for t in user_requests[user_id] if (now - t).total_seconds() < TIME_FRAME]
	user_requests[user_id].append(now)
	return len(user_requests[user_id]) > REQUEST_LIMIT

async def extract_username_and_message_id(message_url):
    # Убираем query string если есть
    message_url = message_url.split('?')[0].rstrip('/')
    path = message_url[len('https://t.me/'):].split('/')
    if len(path) == 2:
        # Обычный формат: t.me/username/123
        chat_username = path[0]
        message_id = int(path[1])
        return chat_username, message_id
    elif len(path) == 3:
        # Форум/тред: t.me/group/thread_id/message_id
        chat_username = path[0]
        message_id = int(path[2])
        return chat_username, message_id
    raise ValueError("Неверная ссылка!")

async def subsribe_channel(user_id, chan):
	chat_member = await bot.get_chat_member(chan, user_id)
	if chat_member.status != 'left':
		return True
	else:
		return False

class AddSubscribeFSM(StatesGroup): #Добавление подписки
	user_id = State()
	days = State()

class ClearSubscribeFSM(StatesGroup): #Сброс подписки
	user_id = State()

class WaitLinkFSM(StatesGroup): #Botnet
	link = State()

class WaitMailTextFSM(StatesGroup): #Mail
	text = State()

class WaitMailTopicFSM(StatesGroup): 
	topic = State()

class WaitTextFSM(StatesGroup): #Web
	text = State()

class WaitTextZFSM(StatesGroup): #Рассылка
	text = State()

class WaitPromoFSM(StatesGroup): #Промокод
	promo = State()

class ClearPremFSM(StatesGroup): #Сброс премки
	user_id = State()

class AddPremFSM(StatesGroup): #Выдача премки
	user_id = State()

class WaitLinkPREMFSM(StatesGroup): #Botnet premium
	link = State()

class WaitCaptchaFSM(StatesGroup): #Капча при первом входе
	code = State()

# Хранилище активных капча-кодов: {user_id: "CODE"}
_captcha_codes: dict = {}

global bot_status
bot_status = 1

@dp.message_handler(commands=['on'])
async def on(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		bot_status = 1
		await bot.send_message(message.chat.id, "🟢 *Включен!* ", parse_mode=ParseMode.MARKDOWN)
		await bot.send_message(bot_logs, "🟢 *Включен!* ", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['off'])
async def off(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		bot_status = 0
		await bot.send_message(message.chat.id, "🔴 *Выключен!* ", parse_mode=ParseMode.MARKDOWN)
		await bot.send_message(bot_logs, "🔴 *Выключен!* ", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['bot'])
async def status(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		if bot_status == 1:
			await bot.send_message(message.chat.id, "🟢 *Включен!* ", parse_mode=ParseMode.MARKDOWN)
		else:
			await bot.send_message(message.chat.id, "🔴 *Выключен!* ", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['admin'])
async def admin(message):
	if message.chat.id in admins:
		async with aiosqlite.connect("users.db") as db:
			async with db.execute("SELECT COUNT(*) FROM users") as cursor:
				users_count = (await cursor.fetchone())[0]

		sessions_count = len(os.listdir(session_folder)) if os.path.exists(session_folder) else 0
		sessions_count_prem = len(os.listdir(session_folder_prem)) if os.path.exists(session_folder_prem) else 0

		try:
			with open("mails.txt", "r", encoding="utf-8") as f:
				mails_count = len([line for line in f if line.strip()])
		except FileNotFoundError:
			mails_count = 0

		admin_panel_text = (
			">🤖 *Админ меню:*\n\n"
			"📊 *Статистика:*\n"
			f"*├─👥 Всего пользователей:* `{users_count}`\n"
			f"*├─🕒 Сессий в ботнете:* `{sessions_count}`\n"
			f"*├─👑 Сессий в премиум ботнете:* `{sessions_count_prem}`\n"
			f"*├─🌐 Web\-Reports:* `{report_count333}`\n"
			f"*└─✉️ Почт добавлено:* `{mails_count}`\n\n"
			"*/promo PROMOCODE DAYS ACTIVATIONS \- создать промокод*\n"
			"*/on \- включить бота*\n"
			"*/off \- выключить бота*\n"
			"*/info ID \- информация о пользователе*\n"
			"*/addwl ID \- добавить в вайтлист*"
		)

		await bot.send_message(message.chat.id, admin_panel_text, reply_markup=keyboards.admin_markup, parse_mode="MarkdownV2")

@dp.message_handler(commands=['addwl'])
async def addwl(message: types.Message):
	if message.from_user.id in admins:
		parts = message.text.split(' ')
		if len(parts) < 2:
			await bot.send_message(message.chat.id, "❗️ */addwl ID*", parse_mode=ParseMode.MARKDOWN)
			return
		if len(parts) > 2:
			await bot.send_message(message.chat.id, "❗️ */addwl ID*", parse_mode=ParseMode.MARKDOWN)
			return
		try:
			wl_user = int(parts[1])
		except ValueError:
			await bot.send_message(message.chat.id, "❗️ *ID должно быть числом!*.", parse_mode=ParseMode.MARKDOWN)
			return
		
		try:
			async with aiosqlite.connect("users.db") as connect:
				cursor = await connect.execute("INSERT INTO whitelist (user_id) VALUES (?)", (wl_user,))
				await connect.commit()
				await bot.send_message(message.chat.id, f"*📄 {wl_user} добавлен в вайтлист!*", parse_mode=ParseMode.MARKDOWN)
				await bot.send_message(bot_logs, f"*📄 {wl_user} добавлен в вайтлист!*", parse_mode=ParseMode.MARKDOWN)
				await bot.send_message(wl_user, f"*📄 Вы добавлены в вайтлист!*", parse_mode=ParseMode.MARKDOWN)
		except Exception as e:
			print(e)
			await bot.send_message(message.chat.id, "❗️ *Произошла ошибка при добавлении в whitelist.*", parse_mode=ParseMode.MARKDOWN)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'))
async def handle_subscription(callback_query: types.CallbackQuery):
	try:
		user_id = callback_query.from_user.id
		user_first_name = callback_query.from_user.first_name
		user_exists = await check_user_in_db(user_id)
		if user_exists:
			subscription_type = callback_query.data.split('_')[1]
			sub_days = None
			amount = None

			if subscription_type == "1":
				amount = "2"
				sub_days = "1"
				pidor = "на 1 день"
			elif subscription_type == "3":
				amount = "3"
				sub_days = "3"
				pidor = "на 3 дня"
			elif subscription_type == "7":
				amount = 5
				sub_days = "7"
				pidor = "на 7 дней"
			elif subscription_type == "30":
				amount = 9
				sub_days = "30"
				pidor = "на 30 дней"
			elif subscription_type == "forever":
				amount = 6
				sub_days = "999"
				pidor = "навсегда"
			elif subscription_type == "premupgrade":
				amount = 7
				sub_days = "1"
				pidor = "Премиум"

			if amount is not None:
				invoice = await asyncio.to_thread(crypto.create_invoice, asset='USDT', amount=amount)
				pay_url = invoice['pay_url']
				invoice_id = invoice['invoice_id']

				pay_check = types.InlineKeyboardMarkup(row_width=2)
				pay_url_button = types.InlineKeyboardButton("💸 Оплатить", url=pay_url)
				check = types.InlineKeyboardButton("🔍 Проверить", callback_data=f'check_status_{invoice_id}_{subscription_type}_{sub_days}')
				pay_check.add(pay_url_button, check)
				pay_check.add(keyboards.back)

				await bot.edit_message_caption(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, caption=(f">⚙️ *Покупка*\n*└─ Вы покупаете: {pidor}*\n*└─ Вы платите: {amount}$*"), parse_mode="MarkdownV2", reply_markup=pay_check)
	except Exception as e:
		print(f"Ошибка в handle_subscription: {e}")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('check_status_'))
async def check_status_callback(callback_query: types.CallbackQuery):
	try:
		user_id = callback_query.from_user.id
		user_exists = await check_user_in_db(user_id)
		if user_exists:
			parts = callback_query.data.split('_')
			if len(parts) < 3:
				await callback_query.answer("Неверный формат данных. Пожалуйста, попробуйте еще раз.")
				return

			invoice_id = parts[2]
			subscription_type = parts[3]
			sub_days = parts[4]
			await check_status(callback_query, invoice_id, subscription_type, sub_days)
	except Exception as e:
		print(f"Ошибка в check_status_callback: {e}")

async def check_status(callback_query: types.CallbackQuery, invoice_id: str, subscription_type, sub_days):
	try:
		user_id = callback_query.from_user.id
		user_exists = await check_user_in_db(user_id)
		if not user_exists:
			return

		async with aiosqlite.connect('users.db') as db:
			async with db.execute("SELECT subscribe FROM users WHERE user_id = ?", (user_id,)) as cursor:
				subscribe_row = await cursor.fetchone()

		if subscribe_row is None:
			await bot.send_message(callback_query.message.chat.id, "❌ *Не удалось найти данные пользователя.*", parse_mode=ParseMode.MARKDOWN)
			return

		subscribe_str = subscribe_row[0]
		subscribe_date = datetime.strptime(subscribe_str, "%Y-%m-%d %H:%M:%S")

		old_invoice = await asyncio.to_thread(crypto.get_invoices, invoice_ids=invoice_id)
		status_old_invoice = old_invoice['items'][0]['status']

		if status_old_invoice == "paid":
			await bot.edit_message_caption(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, caption=(f">⚙️ *Спасибо за заказ*"), parse_mode="MarkdownV2", reply_markup=back_markup)

			if subscription_type != "premupgrade":
				try:
					days = int(sub_days)
					new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
					async with aiosqlite.connect('users.db') as db:
						await db.execute("UPDATE users SET subscribe = ? WHERE user_id = ?", (new_date, user_id))
						await db.commit()

					subscribe_markup = types.InlineKeyboardMarkup(row_width=1)
					user_button = types.InlineKeyboardButton(f"Пользователь: {user_id}", url=f'tg://openmessage?user_id={user_id}')
					subscribe_markup.add(user_button)

					await bot.send_message(
						bot_logs,
						f">💳 *Деньга пришла в кошелек*\n\n⚡️ *Пользователь* `{user_id}` *оплатил подписку \(теперь действует до* `{new_date}`*\)*",
						parse_mode="MarkdownV2",
						reply_markup=subscribe_markup
					)
				except Exception as e:
					print(f"Ошибка обновления подписки: {e}")
			else:
				try:
					async with aiosqlite.connect('users.db') as db:
						await db.execute("UPDATE users SET premium = ? WHERE user_id = ?", (1, user_id))
						await db.commit()

					subscribe_markup = types.InlineKeyboardMarkup(row_width=1)
					user_button = types.InlineKeyboardButton(f"Пользователь: {user_id}", url=f'tg://openmessage?user_id={user_id}')
					subscribe_markup.add(user_button)

					await bot.send_message(
						bot_logs,
						f">💳 *Деньга пришла в кошелек*\n\n⚡️ *Пользователь* `{user_id}` *обновил подписку до Premium\!*",
						parse_mode="MarkdownV2",
						reply_markup=subscribe_markup
					)
				except Exception as e:
					print(f"Ошибка обновления подписки: {e}")
		else:
			await bot.send_message(callback_query.message.chat.id, "❌ *Оплата не получена!*", parse_mode=ParseMode.MARKDOWN)
	except Exception as e:
		print(f"Ошибка в check_status: {e}")

@dp.message_handler(commands=['promo'])
async def promo(message: Message):
	user_id = message.from_user.id
	user_exists = await check_user_in_db(user_id)
	
	if user_exists:
		if user_id in admins:
			parts = message.text.split(' ')
			if len(parts) != 4:
				await bot.send_message(
					message.chat.id, 
					"*/promo PROMOCODE DAYS ACTIVATIONS*", 
					parse_mode="Markdown"
				)
				return

			code = parts[1]
			try:
				days = int(parts[2])
				activations = int(parts[3])
			except ValueError:
				await bot.send_message(
					message.chat.id, 
					"*Дни и активации должны быть числами.*", 
					parse_mode="Markdown"
				)
				return

			try:
				async with aiosqlite.connect("users.db") as db:
					await db.execute(
						"INSERT INTO promocode (code, days, activations) VALUES (?, ?, ?)", 
						(code, days, activations)
					)
					await db.commit()
				
				await bot.send_message(
					message.chat.id, 
					f"💎 Создан промокод:\n\n>*Код:* `{code}`\n\n🎁 *Приз: {days} дней*\n⚡️ *Активации: {activations}*\n⚙️ *Создал: {message.chat.id}*", 
					parse_mode="MarkdownV2"
				)
			   
				await bot.send_message(
					bot_logs, 
					f"💎 Создан промокод:\n\n>*Код:* `{code}`\n\n🎁 *Приз: {days} дней*\n⚡️ *Активации: {activations}*\n⚙️ *Создал: {message.chat.id}*", 
					parse_mode="MarkdownV2"
				)
			except aiosqlite.IntegrityError:
				await bot.send_message(
					message.chat.id, 
					f"❗️ *Промокод* `{code}` *уже существует!*", 
					parse_mode="Markdown"
				)
			except Exception as e:
				await bot.send_message(
					message.chat.id, 
					f"❗️ *Произошла ошибка при создании промокода: {e}*", 
					parse_mode="Markdown"
				)

@dp.message_handler(commands=['start'])
async def welcome(message):
	if await is_blocked(message.from_user.id):
		return 

	if check_rate_limit(message.from_user.id):
		await block_user(message.from_user.id)
		await message.reply("Вы превысили лимит запросов и заблокированы навсегда.")
		return

	async with aiosqlite.connect("users.db") as connect:
		cursor = await connect.cursor()

		await cursor.execute("""CREATE TABLE IF NOT EXISTS users(
			user_id BIGINT,
			subscribe DATETIME,
			premium INT,
			verified INT DEFAULT 0
		)""")
		await connect.execute("""
			CREATE TABLE IF NOT EXISTS promocode(
				code TEXT UNIQUE,
				days INT,
				activations INT
			)
		""")
		await connect.execute("""
			CREATE TABLE IF NOT EXISTS whitelist(
				user_id BIGINT
			)
		""")

		people_id = message.chat.id

		await cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (people_id,))
		data = await cursor.fetchone()

		if data is None:
			await cursor.execute("INSERT INTO users VALUES(?, ?, ?, ?);", (people_id, "1999-01-01 20:00:00", 0, 0))
			await connect.commit()

		# Добавляем колонку verified если её нет (миграция старых БД)
		try:
			await connect.execute("ALTER TABLE users ADD COLUMN verified INT DEFAULT 0")
			await connect.commit()
		except Exception:
			pass  # Колонка уже существует

		# Проверяем верификацию
		verified = await is_verified(people_id)
		if not verified:
			# Генерируем капчу
			code = generate_captcha_text()
			_captcha_codes[people_id] = code
			img_buf = generate_captcha_image(code)
			await bot.send_photo(
				message.chat.id,
				photo=img_buf,
				caption=f"*Привет, {message.from_user.first_name}!*\n\n*Докажи, что ты не робот 🤖*\n\n*└─ Введи код с картинки:*",
				parse_mode="Markdown"
			)
			await WaitCaptchaFSM.code.set()
			return
		
		await bot.send_sticker(message.chat.id, InputFile("AnimatedSticker.tgs"))
		await bot.send_photo(message.chat.id, photo=open('material/menu.png', 'rb'), caption=f'>*Ты и сам прекрасно знаешь для чего пришел сюда\. Добро пожаловать в Ability\!*\n\n*Данный бот является инструментом для работы с txt\, doc\, docx\, ini\, cfg файлами\. Позволяет редактировать текстовые файлы бесплатно\.*', parse_mode="MarkdownV2", reply_markup=menu)

@dp.message_handler(state=WaitCaptchaFSM.code)
async def check_captcha(message: types.Message, state: FSMContext):
	user_id = message.from_user.id
	entered = message.text.strip()
	correct = _captcha_codes.get(user_id, "")

	if entered.lower() == correct.lower():
		# Верно — снимаем стейт, ставим verified
		await state.finish()
		_captcha_codes.pop(user_id, None)
		await set_verified(user_id)
		# Показываем приветствие
		await bot.send_sticker(message.chat.id, InputFile("AnimatedSticker.tgs"))
		await bot.send_photo(
			message.chat.id,
			photo=open('material/menu.png', 'rb'),
			caption=f'>*Ты и сам прекрасно знаешь для чего пришел сюда\. Добро пожаловать в Ability\!*\n\n*Данный бот является инструментом для работы с txt\, doc\, docx\, ini\, cfg файлами\. Позволяет редактировать текстовые файлы бесплатно\.*',
			parse_mode="MarkdownV2",
			reply_markup=menu
		)
	else:
		# Неверно — генерируем новую капчу
		code = generate_captcha_text()
		_captcha_codes[user_id] = code
		img_buf = generate_captcha_image(code)
		await bot.send_photo(
			message.chat.id,
			photo=img_buf,
			caption=f"*❌ Неверно! Попробуй ещё раз:*",
			parse_mode="Markdown"
		)

@dp.callback_query_handler(lambda call: True)
async def callback_inline(call):
	try:
		user_id = call.from_user.id
		if await is_blocked(user_id):
			return

		if check_rate_limit(user_id):
			await block_user(user_id)
			await call.message.answer("Вы превысили лимит запросов и заблокированы навсегда.")
			return

		user_id = call.from_user.id
		fullname = call.from_user.first_name
		try:
			username = call.from_user.username 
		except:
			username = "None"

		if not await check_user_in_db(user_id):
			await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"*Вы блокировали бота! Пропишите /start*"), parse_mode="Markdown")
			return

		chan = channel_id
		if not await subsribe_channel(user_id, chan):
			await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"*подпишитесь на канал!*"), parse_mode="Markdown", reply_markup=check_markup)
			return

		chan = channel2_id
		if not await subsribe_channel(user_id, chan):
			await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"*подпишитесь на канал!*"), parse_mode="Markdown", reply_markup=check_markup)
			return

		async with aiosqlite.connect('users.db') as connect:
			cursor = await connect.cursor()

			async with aiosqlite.connect('users.db') as connect:
				async with connect.execute("SELECT subscribe FROM users WHERE user_id = ?", (user_id,)) as cursor:
					subscribe_str = await cursor.fetchone()
					if subscribe_str:
						subscribe = datetime.strptime(subscribe_str[0], "%Y-%m-%d %H:%M:%S")

				async with connect.execute("SELECT premium FROM users WHERE user_id = ?", (user_id,)) as cursor:
					premium = await cursor.fetchone()
					premium = int(premium[0])

				async with connect.execute("SELECT user_id FROM whitelist") as cursor:
					whitelist = [code[0] for code in await cursor.fetchall()]

		if call.message:
			if call.data == 'functions':
				await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"*Заказ*\n\n>*Посмотрите Мануал*"), parse_mode="MarkdownV2", reply_markup=functions)
			if call.data == 'profile':
				if subscribe < datetime.now():
					sub_text = f"Истекла"
				else:
					days_left = (subscribe - datetime.now()).days
					sub_text = f"осталось {days_left} дней (до {subscribe})"
				if premium == 1:
					prem = "Да"
				else:
					prem = "Нет" 
				await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"*Профиль*\n\n▪️ *Имя: fullname*\n▪️ *ID: {user_id}*\n▪️ *Username: @{username}*\n▪️ *Премиум: {prem}*\n\n⏳ *Подписка: {sub_text}*"), parse_mode="Markdown", reply_markup=back_markup)
			if call.data == "back":
				await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f">*Ты и сам прекрасно знаешь для чего пришел сюда\. Добро пожаловать в Ability\!*\n\n*Данный бот является инструментом для работы с txt\, doc\, docx\, ini\, cfg файлами\. Позволяет редактировать текстовые файлы бесплатно\.*"), parse_mode="MarkdownV2", reply_markup=menu)
			if call.data == "information":
				await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f">*Информация*"), parse_mode="MarkdownV2", reply_markup=info_markup)
			if call.data == "shop":
				await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"⚙️ *Ассортимент*\n\n>⚙️ *Тариф:*\n>*└─ 1 день \- 2$*\n>*└─ 3 дня \- 3$*\n>*└─ 7 дней \- 5$*\n>*└─ 30 дней \- 9$*\n>*└─ Навсегда \- 6$ \[\-60%\]*\n>\n>👑 *Премиум апгрейд:*\n>*└─  Навсегда \- 7$ \[\-40%\]*"), parse_mode="MarkdownV2", reply_markup=shop_markup)
			if call.data == "buyforadmins":
				await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f">*💳 Выберите способ оплаты\:*"), parse_mode="MarkdownV2", reply_markup=keyboards.pay_method)
			if call.data == "tinkoff":
				await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"⚙️ *Заказ по карте \(ручная проверка\)*\n\n>⚙️ *Тариф:*\n>*└─ 1 день \- 160р*\n>*└─ 3 дня \- 250р*\n>*└─ 7 дней \- 400р*\n>*└─ 30 дней \-800р*\n>*└─ Навсегда \- 500р \[\-60%\]*\n>\n>👑 *Премиум апгрейд:*\n>*└─  Навсегда \- 600р \[\-40%\]*\n\n🟡 *Реквизиты:*  `2200700746639045` *\(тинька\)*\n💬 *Комментарий:* `{user_id}, претензий не имею` \(обязательно\)\n\n🤝 *После оплаты отправьте чек и напишите* `+` *в личные сообщения @LaurisW*"), parse_mode="MarkdownV2", reply_markup=back_markup)
			if call.data == "sberbank":
				 await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"⚙️ *Заказ по карте \(ручная проверка\)*\n\n>⚙️ *Тариф:*\n>*└─ 1 день \- 160р*\n>*└─ 3 дня \- 250р*\n>*└─ 7 дней \- 400р*\n>*└─ 30 дней \-800р*\n>*└─ Навсегда \- 500р \[\-60%\]*\n>\n>👑 *Премиум апгрейд:*\n>*└─  Навсегда \- 600р \[\-40%\]*\n\n🟢 *Реквизиты:*  `2202208196531124` *\(сбер\)*\n💬 *Комментарий:* `{user_id}, претензий не имею` \(обязательно\)\n\n🤝 *После оплаты отправьте чек и напишите* `+` *в личные сообщения @KoTik2k8*"), parse_mode="MarkdownV2", reply_markup=back_markup)
			if call.data == "preminfo":
				await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(f"👑 *Премиум*\n\n>🔓 *Премиум даст:*\n>*└─ почты*\n>*└─ веб*\n>*└─ Прем отправку*\n>*└─ Преф в нашем чате*\n\n‼️*Премиум покупается как ДОПОЛНЕНИЕ к вашей активной пицце* ‼️"), parse_mode="MarkdownV2", reply_markup=back_markup)
			if call.data == "close":
				await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
			if call.data == "go_to_main_menu":
				await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
				await bot.send_photo(call.message.chat.id, photo=open('material/menu.png', 'rb'), caption=f'>*Ты и сам прекрасно знаешь для чего пришел сюда\. Добро пожаловать\!*\n\n*Данный бот является инструментом для работы с txt\, doc\, docx\, ini\, cfg файлами\. Позволяет редактировать текстовые файлы бесплатно\.*', parse_mode="MarkdownV2", reply_markup=menu)
			elif call.data == 'add_subsribe':
				if user_id in admins:
					await bot.send_message(call.message.chat.id, '🎱 *Выдача подписки*\n*└─Введите ID:*', parse_mode="Markdown")
					await AddSubscribeFSM.user_id.set()
			elif call.data == 'clear_subscribe':
				if user_id in admins:
					await bot.send_message(call.message.chat.id, '🎱 *Сброс подписки*\n*└─Введите ID:*', parse_mode="Markdown")
					await ClearSubscribeFSM.user_id.set() 
			elif call.data == 'send_all':
				admins2 = [69717177, 60693380]
				if user_id in admins:
					if user_id in admins2:
						await bot.send_message(call.message.chat.id, '🎱 *Рассылка*\n*└─Введите текст:*', parse_mode="Markdown")
						await WaitTextZFSM.text.set()
					else:
						await bot.send_message(call.message.chat.id, '🎱 *Рассылка*', parse_mode="Markdown")
				else:
					await bot.send_message(call.message.chat.id, '🎱 *Нет, иди нахуй.*', parse_mode="Markdown")
			elif call.data == 'promo':
				await bot.send_message(call.message.chat.id, f'🎱 *Активация промокода*\n*└─Введите промокод:*', parse_mode="Markdown")
				await WaitPromoFSM.promo.set()
			elif call.data == 'add_prem':
				if user_id in admins:
					await bot.send_message(call.message.chat.id, '🎱 *Выдача премиума*\n*└─Введите ID:*', parse_mode="Markdown")
					await AddPremFSM.user_id.set()
			elif call.data == 'clear_prem':
				if user_id in admins:
					await bot.send_message(call.message.chat.id, '🎱 *Сброс премиума*\n*└─Введите ID:*', parse_mode="Markdown")
					await ClearPremFSM.user_id.set() 

			#WebMethod
			if call.data == "web_method":
				if subscribe < datetime.now():
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *оплати\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return
				if premium == 0:
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *Для использования этого метода нужен премиум\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if bot_status == 0:
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *Бот выключен\! Подробности в канале\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if user_id in last_used_web and (datetime.now() - last_used_web[user_id]) < timedelta(minutes=30):
					remaining_time = timedelta(minutes=30) - (datetime.now() - last_used_web[user_id])
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id,
												caption=f'❌ *Жди {remaining_time.seconds // 60} минут и {remaining_time.seconds % 60} секунд до следующей!*',
												parse_mode="Markdown", reply_markup=back_markup)
					return

				last_used_web[user_id] = datetime.now()		
				await call.message.answer("✉️ *Введите текст, который нужно отправить:*", parse_mode="Markdown")
				await WaitTextFSM.text.set()

			#MailMethod
			if call.data == "mail_method":
				if subscribe < datetime.now():
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *оплати\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return
				if premium == 0:
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *Для использования этого метода нужен премиум\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if bot_status == 0:
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *Бот выключен\! Подробности в канале\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if user_id in last_used_mail and (datetime.now() - last_used_mail[user_id]) < timedelta(minutes=300):
					remaining_time = timedelta(minutes=300) - (datetime.now() - last_used_mail[user_id])
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id,
												caption=f'❌ *Жди {remaining_time.seconds // 60} минут и {remaining_time.seconds % 60} секунд до следующей отправки!*',
												parse_mode="Markdown", reply_markup=back_markup)
					return
				last_used_mail[user_id] = datetime.now()	
				await call.message.answer("📌 *Введите тему:*", parse_mode="Markdown")
				await WaitMailTopicFSM.topic.set()
			if call.data == "botnet_method":
				if subscribe < datetime.now():
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *оплати\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if bot_status == 0:
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *Бот выключен\! Подробности в канале\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if user_id in last_used_botnet and (datetime.now() - last_used_botnet[user_id]) < timedelta(minutes=5):
					remaining_time = timedelta(minutes=5) - (datetime.now() - last_used_botnet[user_id])
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id,
												caption=f'❌ *Жди {remaining_time.seconds // 60} минут и {remaining_time.seconds % 60} секунд до следующей отправки!*',
												parse_mode="Markdown", reply_markup=back_markup)
					return
				last_used_botnet[user_id] = datetime.now()	
				await bot.send_message(call.message.chat.id, '*Отправьте ссылку на сообщение в формате:*\n`https://t.me/username/123`', parse_mode="Markdown")
				await WaitLinkFSM.link.set()

			if call.data == "prem_botnet_method":
				if subscribe < datetime.now():
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *оплати\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if premium == 0:
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *Для использования этого метода нужен премиум\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if bot_status == 0:
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=(">❌ *Бот выключен\! Подробности в канале\!*"), parse_mode="MarkdownV2", reply_markup=back_markup)
					return

				if user_id in last_used_botnet2 and (datetime.now() - last_used_botnet2[user_id]) < timedelta(minutes=30):
					remaining_time = timedelta(minutes=30) - (datetime.now() - last_used_botnet2[user_id])
					await bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id,
												caption=f'❌ *Жди {remaining_time.seconds // 60} минут и {remaining_time.seconds % 60} секунд до следующей отправки!*',
												parse_mode="Markdown", reply_markup=back_markup)
					return
				last_used_botnet2[user_id] = datetime.now()	
				await bot.send_message(call.message.chat.id, '*Отправьте ссылку на сообщение в формате:*\n`https://t.me/username/123`', parse_mode="Markdown")
				await WaitLinkPREMFSM.link.set()
	except Exception as e:
		print(e)


@dp.message_handler(state=WaitTextFSM.text)
async def send_web_reports(message: types.Message, state: FSMContext):
	await state.finish()

	await message.answer("🔁 *Скоро будет...*", parse_mode="Markdown")

	user_id = message.from_user.id
	username = message.from_user.username or "без username"

	log_path = generate_log_filename()

	async with aiohttp.ClientSession() as session:
		success, error = await web(
			session=session,
			message_text=message.text,
			count=report_count333,
			log_path=log_path,
			user_id=user_id,
			username=username
		)

	try:
		await message.answer_document(
			types.InputFile(log_path),
			caption=(
				f"⚙️ *Доставлено*\n"
				f"*└─📂 Метод: веб*\n\n"
				f"🟢 *Успешно отправлено: {success}*\n"
				f"🔴 *Не удалось отправить: {error}*"
			),
			reply_markup=main_menu,
			parse_mode="Markdown"
		)
	except Exception as e:
		pass

	await bot.send_document(
		chat_id=bot_logs,
		document=types.InputFile(log_path),
		caption=(
			f"📈 *Бот завершил работу*\n"
			f"*└─📂 Метод: веб*\n\n"
			f"🟢 *Успешно отправлено: {success}*\n"
			f"🔴 *Не удалось отправить: {error}*\n\n"
			f"👤 *Пользователь:* `{user_id}` (@{username})"
		),
		parse_mode="Markdown"
	)

	try:
		os.remove(log_path)
	except Exception as e:
		pass

@dp.message_handler(state=WaitMailTopicFSM.topic)
async def get_mail_subject(message: types.Message, state: FSMContext):
	await state.update_data(subject=message.text)
	await message.answer("✉️ *Теперь введите текст письма:*", parse_mode="Markdown")
	await WaitMailTextFSM.text.set()

@dp.message_handler(state=WaitMailTextFSM.text)
async def start_bulk_email(message: types.Message, state: FSMContext):
	data = await state.get_data()
	subject = data.get("subject")
	text = message.text
	await state.finish()

	mails = load_mails()
	if not mails:
		await bot.send_message(message.from_user.id, "❌ *Не удалось загрузить почты!*", parse_mode="Markdown")
		return

	receiver_emails = [
		"dmca@telegram.org", "support@telegram.org",
		"abuse@telegram.org", "stopCA@telegram.org"
	]

	success, error, log_path = await send_bulk_emails(
		subject, text, mails, receiver_emails,
		user_id=message.from_user.id,
		username=message.from_user.username or "None",
		bot=bot,
		chat_id=message.from_user.id
	)

	caption = (
		f"⚙️ *Доставлено*\n"
		f"*└─📂 Метод: почты*\n\n"
		f"🟢 *Успешно отправлено: {success}*\n"
		f"🔴 *Не удалось отправить: {error}*"
	)
	try:
		await bot.send_document(message.from_user.id, types.InputFile(log_path), caption=caption, parse_mode="Markdown", reply_markup=main_menu)

		await bot.send_document(bot_logs, types.InputFile(log_path),caption=f"{caption}\n\n👤 *Пользователь: {message.from_user.id} (@{message.from_user.username or 'None'})*", parse_mode="Markdown")
	except Exception as e:
		print(e)
	try:
		os.remove(log_path)
	except Exception as e:
		print(f"Не удалось удалить лог: {e}")

@dp.message_handler(state=WaitLinkFSM.link)
async def botnet_step1_normal(message: types.Message, state: FSMContext):
	message_url = message.text
	await state.finish()
	user = message.from_user.id
	try:
		username = message.from_user.username 
	except:
		username = "None"
	try:
		chat_username, message_id = await extract_username_and_message_id(message_url)
		await bot.send_message(user, '📤 *Запустил отправку...*', parse_mode=ParseMode.MARKDOWN)
		await botnet_main(chat_username, message_id, user, username, message_url)
	except ValueError:
		await bot.send_message(user, '*⭕️ Неверная ссылка! Нужна ссылка на сообщение!*', parse_mode=ParseMode.MARKDOWN)
		return
	except Exception as e:
		print(f"Ошибка при обработке ссылки: {e}")
		return

@dp.message_handler(state=WaitLinkPREMFSM.link)
async def botnet_step1_premium(message: types.Message, state: FSMContext):
	message_url = message.text
	await state.finish()
	user = message.from_user.id
	try:
		username = message.from_user.username 
	except:
		username = "None"
	try:
		chat_username, message_id = await extract_username_and_message_id2(message_url)
		await bot.send_message(user, '👑 *Запустил отправку...*', parse_mode=ParseMode.MARKDOWN)
		await botnet_main2(chat_username, message_id, user, username, message_url)
	except ValueError:
		await bot.send_message(user, '*⭕️ Неверная ссылка! Нужна ссылка на сообщение!*', parse_mode=ParseMode.MARKDOWN)
		return
	except Exception as e:
		print(f"Ошибка при обработке ссылки: {e}")
		return

@dp.message_handler(state=AddSubscribeFSM.user_id)
async def handle_add_subscribe_user_id(message: types.Message, state: FSMContext):
	try:
		target_user_id = int(message.text)
		await state.update_data(user_id=target_user_id)  # сначала сохраняем данные
		await message.answer("🎱 *Выдача подписки*\n*└─Введите длительность подписки:*", parse_mode=ParseMode.MARKDOWN)
		await AddSubscribeFSM.days.set()  # переходим в следующий стейт
	except ValueError:
		await message.answer("❌ *Ошибка!* ID должен быть числом.", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(state=AddSubscribeFSM.days)
async def handle_add_subscribe_days(message: types.Message, state: FSMContext):
	try:
		days = int(message.text)
		data = await state.get_data()
		target_user_id = data['user_id']
		new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

		async with aiosqlite.connect('users.db') as db:
			await db.execute("UPDATE users SET subscribe = ? WHERE user_id = ?", (new_date, target_user_id))
			await db.commit()

		await bot.send_message(target_user_id, f"🎱 *Ваша подписка обновлена!* Действует до: `{new_date}`.", parse_mode="Markdown", reply_markup=del_message2)

		subscribe_markup = types.InlineKeyboardMarkup(row_width=1)
		admin_id_button = types.InlineKeyboardButton(f"Админ", url=f'tg://openmessage?user_id={message.chat.id}')
		user_button = types.InlineKeyboardButton(f"Пользователь", url=f'tg://openmessage?user_id={target_user_id}')
		subscribe_markup.add(admin_id_button, user_button)

		await bot.send_message(
			bot_logs,
			f"🎱 *Выдача подписки*\n\n*Подписка пользователя ({target_user_id}) теперь действует до {new_date}*\n\n⚙️ *Выдал: {message.chat.id}*",
			parse_mode="Markdown",
			reply_markup=subscribe_markup
		)
		await state.finish()
		await message.answer("🎱 *Подписка успешно обновлена!*", parse_mode="Markdown")

	except ValueError:
		await message.answer("❌ *Ошибка!* Введите корректное количество дней.", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=ClearSubscribeFSM.user_id)
async def handle_clear_subscribe_user_id(message: types.Message, state: FSMContext):
	try:
		target_user_id = int(message.text)
		await state.update_data(user_id=target_user_id)
		await state.finish()

		async with aiosqlite.connect('users.db') as db:
			async with db.execute("SELECT subscribe FROM users WHERE user_id = ?", (target_user_id,)) as cursor:
				user_data = await cursor.fetchone()

		if user_data is None:
			await message.answer("❌ *Ошибка!* Пользователь с таким ID не найден.", parse_mode="Markdown")
			await state.finish()
		else:
			reset_date = "1999-01-01 00:00:00"
			async with aiosqlite.connect('users.db') as db:
				await db.execute("UPDATE users SET subscribe = ? WHERE user_id = ?", (reset_date, target_user_id))
				await db.commit()

			await bot.send_message(target_user_id, f"*🎱 Ваша подписка сброшена!* Теперь она действует до: `01.01.1999`.", parse_mode="Markdown", reply_markup=del_message2)

			subscribe_markup = types.InlineKeyboardMarkup(row_width=1)
			admin_id_button = types.InlineKeyboardButton(f"Админ", url=f'tg://openmessage?user_id={message.chat.id}')
			user_button = types.InlineKeyboardButton(f"Пользователь", url=f'tg://openmessage?user_id={target_user_id}')
			subscribe_markup.add(admin_id_button, user_button)

			await bot.send_message(
				bot_logs,
				f"🎱 *Сброс подписки*\n\n*Подписка пользователя ({target_user_id}) сброшена*\n\n⚙️ *Сбросил: {message.chat.id}*",
				parse_mode="Markdown",
				reply_markup=subscribe_markup
			)

			await state.finish()
			await message.answer("*🎱 Подписка успешно сброшена!*", parse_mode="Markdown")
	
	except ValueError:
		await message.answer("*❌ Ошибка!* Введите корректный ID пользователя.", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=ClearPremFSM.user_id)
async def handle_clear_prem_user_id(message: types.Message, state: FSMContext):
	try:
		target_user_id = int(message.text)
		await state.update_data(user_id=target_user_id)
		await state.finish()

		async with aiosqlite.connect('users.db') as db:
			async with db.execute("SELECT premium FROM users WHERE user_id = ?", (target_user_id,)) as cursor:
				user_data = await cursor.fetchone()

		if user_data is None:
			await message.answer("❌ *Ошибка!* Пользователь с таким ID не найден.", parse_mode="Markdown")
			await state.finish()
		else:
			async with aiosqlite.connect('users.db') as db:
				await db.execute("UPDATE users SET premium = ? WHERE user_id = ?", (0, target_user_id))
				await db.commit()

			await bot.send_message(target_user_id, f"*🎱 Ваша подписка сброшена.*", parse_mode="Markdown", reply_markup=del_message2)

			subscribe_markup = types.InlineKeyboardMarkup(row_width=1)
			admin_id_button = types.InlineKeyboardButton(f"Админ", url=f'tg://openmessage?user_id={message.chat.id}')
			user_button = types.InlineKeyboardButton(f"Пользователь", url=f'tg://openmessage?user_id={target_user_id}')
			subscribe_markup.add(admin_id_button, user_button)

			await bot.send_message(
				bot_logs,
				f"🎱 *Сброс премиума*\n\n*Премиум пользователя ({target_user_id}) сброшен*\n\n⚙️ *Сбросил: {message.chat.id}*",
				parse_mode="Markdown",
				reply_markup=subscribe_markup
			)

			await state.finish()
			await message.answer("*🎱 Премиум успешно сброшен!*", parse_mode="Markdown")
	
	except ValueError:
		await message.answer("*❌ Ошибка!* Введите корректный ID пользователя.", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=AddPremFSM.user_id)
async def handle_add_prem_user_id(message: types.Message, state: FSMContext):
	try:
		target_user_id = int(message.text)
		await state.update_data(user_id=target_user_id)
		await state.finish()

		async with aiosqlite.connect('users.db') as db:
			async with db.execute("SELECT premium FROM users WHERE user_id = ?", (target_user_id,)) as cursor:
				user_data = await cursor.fetchone()

		if user_data is None:
			await message.answer("❌ *Ошибка!* Пользователь с таким ID не найден.", parse_mode="Markdown")
			await state.finish()
		else:
			async with aiosqlite.connect('users.db') as db:
				await db.execute("UPDATE users SET premium = ? WHERE user_id = ?", (1, target_user_id))
				await db.commit()

			await bot.send_message(target_user_id, f"*👑 Вашa подписка обновлена до Premium.*", parse_mode="Markdown", reply_markup=del_message2)

			subscribe_markup = types.InlineKeyboardMarkup(row_width=1)
			admin_id_button = types.InlineKeyboardButton(f"Админ", url=f'tg://openmessage?user_id={message.chat.id}')
			user_button = types.InlineKeyboardButton(f"Пользователь", url=f'tg://openmessage?user_id={target_user_id}')
			subscribe_markup.add(admin_id_button, user_button)

			await bot.send_message(
				bot_logs,
				f"🎱 *Выдача премиума*\n\n*Выдан премиум пользователю {target_user_id}*\n\n⚙️ *Выдал: {message.chat.id}*",
				parse_mode="Markdown",
				reply_markup=subscribe_markup
			)

			await state.finish()
			await message.answer("*🎱 Премиум успешно выдан!*", parse_mode="Markdown")
	
	except ValueError:
		await message.answer("*❌ Ошибка!* Введите корректный ID пользователя.", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=WaitTextZFSM.text, content_types=types.ContentTypes.ANY)
async def sendall1(message: types.Message, state: FSMContext):
	async with aiosqlite.connect('users.db') as db:
		cursor = await db.execute("SELECT user_id FROM users")
		users = await cursor.fetchall()
		await cursor.close()

	successful = 0
	failed = 0

	await state.finish()
	await bot.send_message(message.chat.id, '*🎱 Рассылка началась!*', parse_mode='Markdown')

	for user_row in users:
		user_id = user_row[0]
		try:
			if message.text:
				await bot.send_message(
					chat_id=user_id,
					text=message.text,
					parse_mode='Markdown',
					reply_markup=del_message
				)

			elif message.photo:
				await bot.send_photo(
					chat_id=user_id,
					photo=message.photo[-1].file_id,
					caption=message.caption,
					parse_mode='Markdown',
					reply_markup=del_message
				)

			elif message.video:
				await bot.send_video(
					chat_id=user_id,
					video=message.video.file_id,
					caption=message.caption,
					parse_mode='Markdown',
					reply_markup=del_message
				)

			elif message.document:
				await bot.send_document(
					chat_id=user_id,
					document=message.document.file_id,
					caption=message.caption,
					parse_mode='Markdown',
					reply_markup=del_message
				)

			elif message.audio:
				await bot.send_audio(
					chat_id=user_id,
					audio=message.audio.file_id,
					caption=message.caption,
					parse_mode='Markdown',
					reply_markup=del_message
				)

			else:
				await message.copy_to(chat_id=user_id)
			successful += 1

		except Exception as e:
			failed += 1

	await bot.send_message(
		message.chat.id,
		f'*🎱 Рассылка окончена!*\n*└─✅ Доставлено:* {successful}\n*└─❌ Заблокировали бота:* {failed}',
		parse_mode='Markdown',
		reply_markup=main_menu
	)

@dp.message_handler(state=WaitPromoFSM.promo)
async def enter_promo(message: types.Message, state: FSMContext):
	user_id = message.from_user.id
	user_first_name = message.from_user.first_name
	promo_text = message.text.strip()
	await state.finish()

	async with aiosqlite.connect('users.db') as db:
		async with db.execute("SELECT code FROM promocode") as cursor:
			codes = [row[0] for row in await cursor.fetchall()]
		
		if bot_username not in user_first_name:
			await bot.send_message(
				message.chat.id,
				f"*❌ {bot_username} в ник, чтобы иметь возможность активировать промокоды!*",
				parse_mode='Markdown'
			)
			return

		if promo_text not in codes:
			await bot.send_message(
				message.chat.id,
				f"*❌ Промокод не найден!*",
				parse_mode='Markdown'
			)
			return

		async with db.execute("SELECT activations, days FROM promocode WHERE code = ?", (promo_text,)) as cursor:
			promo_data = await cursor.fetchone()

		if not promo_data or promo_data[0] <= 0:
			await bot.send_message(
				message.chat.id,
				f"*❌ Данный промокод уже нельзя активировать!*",
				parse_mode='Markdown'
			)
			return

		activations, days = promo_data
		new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
		
		await db.execute("UPDATE promocode SET activations = ? WHERE code = ?", (activations - 1, promo_text))
		await db.execute("UPDATE users SET subscribe = ? WHERE user_id = ?", (new_date, user_id))
		await db.commit()

		await bot.send_message(
			message.chat.id,
			f"*✅ Промокод активирован!*\n\n*Ваш подарок: {days} дней пиццы!*",
			parse_mode='Markdown'
		)

		subscribe_markup = InlineKeyboardMarkup(row_width=1).add(
			InlineKeyboardButton(f"Пользователь: {user_id}", url=f'tg://user?id={user_id}')
		)
		await bot.send_message(
			bot_logs,
			f"🎁 *Пользователь* `{user_id}` *активировал промокод и получил {days} дней подписки!*\n\n💎 *Промокод:* `{promo_text}`",
			parse_mode='Markdown',
			reply_markup=subscribe_markup
		)

if __name__ == "__main__":
	while True:
		try:
			print("Бот запускается...")
			executor.start_polling(dp, skip_updates=True)
		except KeyboardInterrupt:
			print("Получен сигнал остановки (Ctrl+C). Выход...")
			exit()
		except Exception as e:
			print(f"Бот упал с ошибкой: {e}. Перезапуск через 5 секунд...")
			time.sleep(5)