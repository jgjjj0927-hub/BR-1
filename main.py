from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode, InputFile, Message
from datetime import datetime, timedelta
from pyCryptoPayAPI import pyCryptoPayAPI
import config
import keyboards
from utils import now_msk
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

# в”Ђв”Ђв”Ђ Helpers в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

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
	return False  # Р°РІС‚Рѕ-Р±Р»РѕРєРёСЂРѕРІРєР° РѕС‚РєР»СЋС‡РµРЅР°, Р±Р»РѕРєРёСЂРѕРІРєР° С‚РѕР»СЊРєРѕ РІСЂСѓС‡РЅСѓСЋ С‡РµСЂРµР· Р°РґРјРёРЅ

async def subsribe_channel(user_id, chan):
	try:
		chat_member = await bot.get_chat_member(chan, user_id)
		return chat_member.status != 'left'
	except Exception as e:
		err = str(e).lower()
		# Р•СЃР»Рё Р±РѕС‚ РЅРµ Р°РІС‚РѕСЂРёР·РѕРІР°РЅ РёР»Рё РЅРµС‚ РґРѕСЃС‚СѓРїР° Рє РєР°РЅР°Р»Сѓ вЂ” Р±Р»РѕРєРёСЂСѓРµРј
		if 'unauthorized' in err or 'forbidden' in err or 'chat not found' in err:
			return False
		return True  # РґСЂСѓРіРёРµ РѕС€РёР±РєРё (СЃРµС‚СЊ Рё С‚.Рґ.) вЂ” РЅРµ Р±Р»РѕРєРёСЂСѓРµРј

async def check_subscription(uid: int, bot_instance=None) -> bool:
	"""РџСЂРѕРІРµСЂСЏРµС‚ РїРѕРґРїРёСЃРєСѓ РЅР° РѕР±Р° РєР°РЅР°Р»Р°. Р’СЃРµРіРґР° С‡РµСЂРµР· РѕСЃРЅРѕРІРЅРѕР№ bot."""
	sub1 = await subsribe_channel(uid, channel_id)
	sub2 = await subsribe_channel(uid, channel2_id)
	return sub1 and sub2

async def send_subscribe_required(uid: int, bot_instance=None):
	"""РћС‚РїСЂР°РІР»СЏРµС‚ СЃРѕРѕР±С‰РµРЅРёРµ СЃ С‚СЂРµР±РѕРІР°РЅРёРµРј РїРѕРґРїРёСЃРєРё."""
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
		types.InlineKeyboardButton("[1пёЏвѓЈ] РџРѕРґРїРёС€РёСЃСЊ (1 РјРёРЅ)", url=invite1),
		types.InlineKeyboardButton("[2пёЏвѓЈ] РџРѕРґРїРёС€РёСЃСЊ (1 РјРёРЅ)", url=invite2),
		types.InlineKeyboardButton("[рџ”Ћ] РџСЂРѕРІРµСЂРёС‚СЊ", callback_data='start_check_sub')
	)
	await b.send_message(uid,
		"*вљ пёЏ Р”Р»СЏ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ Р±РѕС‚Р° РїРѕРґРїРёС€РёС‚РµСЃСЊ РЅР° РєР°РЅР°Р»С‹!*\n*в””в”Ђ РЎСЃС‹Р»РєРё РґРµР№СЃС‚РІСѓСЋС‚ 1 РјРёРЅСѓС‚Сѓ*",
		parse_mode="Markdown", reply_markup=markup)

# в”Ђв”Ђв”Ђ FSM в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

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

# в”Ђв”Ђв”Ђ РљРѕРјР°РЅРґС‹ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.message_handler(commands=['on'])
async def on(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		bot_status = 1
		await bot.send_message(message.chat.id, "рџџў *Р’РєР»СЋС‡РµРЅ!*", parse_mode=ParseMode.MARKDOWN)
		await bot.send_message(bot_logs, "рџџў *Р’РєР»СЋС‡РµРЅ!*", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['off'])
async def off(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		bot_status = 0
		await bot.send_message(message.chat.id, "рџ”ґ *Р’С‹РєР»СЋС‡РµРЅ!*", parse_mode=ParseMode.MARKDOWN)
		await bot.send_message(bot_logs, "рџ”ґ *Р’С‹РєР»СЋС‡РµРЅ!*", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['bot'])
async def status(message: types.Message):
	global bot_status
	if message.chat.id in config.ADMINS:
		text = "рџџў *Р’РєР»СЋС‡РµРЅ!*" if bot_status == 1 else "рџ”ґ *Р’С‹РєР»СЋС‡РµРЅ!*"
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
			">рџ¤– *РђРґРјРёРЅ РјРµРЅСЋ:*\n\nрџ“Љ *РЎС‚Р°С‚РёСЃС‚РёРєР°:*\n"
			f"*в”њв”Ђрџ‘Ґ Р’СЃРµРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№:* `{users_count}`\n"
			f"*в”њв”Ђрџ’і РЎ РїРѕРґРїРёСЃРєРѕР№:* `{subscribers_count}`\n"
			f"*в”њв”ЂрџЋЇ РЎ СЂРµРїРѕСЂС‚Р°РјРё:* `{reports_users_count}`\n"
			f"*в”њв”ЂрџЄћ Р—РµСЂРєР°Р»:* `{mirrors_count}`\n"
			f"*в”њв”Ђрџ•’ РЎРµСЃСЃРёР№ РІ Р±РѕС‚РЅРµС‚Рµ:* `{sessions_count}`\n"
			f"*в”њв”Ђрџ‘‘ РЎРµСЃСЃРёР№ РІ РїСЂРµРјРёСѓРј Р±РѕС‚РЅРµС‚Рµ:* `{sessions_count_prem}`\n"
			f"*в”њв”ЂрџЊђ Web\-Reports:* `{report_count333}`\n"
			f"*в””в”Ђвњ‰пёЏ РџРѕС‡С‚ РґРѕР±Р°РІР»РµРЅРѕ:* `{mails_count}`\n\n"
			"*/promo PROMOCODE DAYS ACTIVATIONS \- СЃРѕР·РґР°С‚СЊ РїСЂРѕРјРѕРєРѕРґ*\n"
			"*/on \- РІРєР»СЋС‡РёС‚СЊ Р±РѕС‚Р°*\n*/off \- РІС‹РєР»СЋС‡РёС‚СЊ Р±РѕС‚Р°*\n"
			"*/addwl ID \- РґРѕР±Р°РІРёС‚СЊ РІ РІР°Р№С‚Р»РёСЃС‚*\n"
			"*/addtargetwl @username \- РґРѕР±Р°РІРёС‚СЊ С†РµР»СЊ РІ WL*\n"
			"*/rmtargetwl @username \- СѓР±СЂР°С‚СЊ С†РµР»СЊ РёР· WL*\n"
			"*/listtargetwl \- СЃРїРёСЃРѕРє С†РµР»РµР№ WL*"
		)
		await bot.send_message(message.chat.id, text, reply_markup=keyboards.admin_markup, parse_mode="MarkdownV2")

@dp.message_handler(commands=['addwl'])
async def addwl(message: types.Message):
	if message.from_user.id not in admins:
		return
	parts = message.text.split()
	if len(parts) != 2:
		await message.answer("вќ—пёЏ */addwl ID*", parse_mode=ParseMode.MARKDOWN)
		return
	try:
		wl_user = int(parts[1])
	except ValueError:
		await message.answer("вќ—пёЏ *ID РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ С‡РёСЃР»РѕРј!*", parse_mode=ParseMode.MARKDOWN)
		return
	await db.add_to_whitelist(wl_user)
	await message.answer(f"*рџ“„ {wl_user} РґРѕР±Р°РІР»РµРЅ РІ РІР°Р№С‚Р»РёСЃС‚!*", parse_mode=ParseMode.MARKDOWN)
	await bot.send_message(bot_logs, f"*рџ“„ {wl_user} РґРѕР±Р°РІР»РµРЅ РІ РІР°Р№С‚Р»РёСЃС‚!*", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['addtargetwl'])
async def addtargetwl(message: types.Message):
	"""Р”РѕР±Р°РІРёС‚СЊ username/channel РІ Р±РµР»С‹Р№ СЃРїРёСЃРѕРє С†РµР»РµР№. /addtargetwl @username"""
	if message.from_user.id not in admins:
		return
	parts = message.text.split()
	if len(parts) != 2:
		await message.answer("вќ—пёЏ */addtargetwl @username*\n*РџСЂРёРјРµСЂ: /addtargetwl @durov*", parse_mode=ParseMode.MARKDOWN)
		return
	pattern = parts[1].lstrip('@').lower()
	await db.add_target_whitelist(pattern, message.from_user.id)
	await message.answer(f"вњ… *`@{pattern}` РґРѕР±Р°РІР»РµРЅ РІ Р±РµР»С‹Р№ СЃРїРёСЃРѕРє С†РµР»РµР№!*\n*в””в”Ђ Р–Р°Р»РѕР±С‹ РЅР° С†РµР»Рё РЅР°С‡РёРЅР°СЋС‰РёРµСЃСЏ СЃ* `{pattern}` *Р±СѓРґСѓС‚ Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅС‹.*", parse_mode=ParseMode.MARKDOWN)
	await bot.send_message(bot_logs, f"рџ›Ў *Р‘РµР»С‹Р№ СЃРїРёСЃРѕРє С†РµР»РµР№:* `@{pattern}` *РґРѕР±Р°РІР»РµРЅ* `{message.from_user.id}`", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['rmtargetwl'])
async def rmtargetwl(message: types.Message):
	"""РЈРґР°Р»РёС‚СЊ username/channel РёР· Р±РµР»РѕРіРѕ СЃРїРёСЃРєР° С†РµР»РµР№. /rmtargetwl @username"""
	if message.from_user.id not in admins:
		return
	parts = message.text.split()
	if len(parts) != 2:
		await message.answer("вќ—пёЏ */rmtargetwl @username*\n*РџСЂРёРјРµСЂ: /rmtargetwl @durov*", parse_mode=ParseMode.MARKDOWN)
		return
	pattern = parts[1].lstrip('@').lower()
	await db.remove_target_whitelist(pattern)
	await message.answer(f"рџ—‘ *`@{pattern}` СѓРґР°Р»С‘РЅ РёР· Р±РµР»РѕРіРѕ СЃРїРёСЃРєР° С†РµР»РµР№!*", parse_mode=ParseMode.MARKDOWN)
	await bot.send_message(bot_logs, f"рџ—‘ *Р‘РµР»С‹Р№ СЃРїРёСЃРѕРє С†РµР»РµР№:* `@{pattern}` *СѓРґР°Р»С‘РЅ* `{message.from_user.id}`", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['listtargetwl'])
async def listtargetwl(message: types.Message):
	"""РџРѕРєР°Р·Р°С‚СЊ РІСЃРµ Р·Р°РїРёСЃРё Р±РµР»РѕРіРѕ СЃРїРёСЃРєР° С†РµР»РµР№."""
	if message.from_user.id not in admins:
		return
	patterns = await db.get_target_whitelist()
	if not patterns:
		await message.answer("рџ“‹ *Р‘РµР»С‹Р№ СЃРїРёСЃРѕРє С†РµР»РµР№ РїСѓСЃС‚.*", parse_mode=ParseMode.MARKDOWN)
		return
	lines = ["рџ“‹ *Р‘РµР»С‹Р№ СЃРїРёСЃРѕРє С†РµР»РµР№:*\n"]
	for p in patterns:
		lines.append(f"вЂў `@{p}`")
	await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# в”Ђв”Ђв”Ђ РџРѕРґРїРёСЃРєРё / РѕРїР»Р°С‚Р° в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'), state='*')
async def handle_subscription(callback_query: types.CallbackQuery):
	try:
		user_id = callback_query.from_user.id
		if not await check_user_in_db(user_id):
			return
		sub_map = {
			"1": ("1", "1", "РЅР° 1 РґРµРЅСЊ"),
			"3": ("2", "3", "РЅР° 3 РґРЅСЏ"),
			"7": (4, "7", "РЅР° 7 РґРЅРµР№"),
			"30": (8, "30", "РЅР° 30 РґРЅРµР№"),
			"forever": (6, "999", "РЅР°РІСЃРµРіРґР°"),
			"premupgrade": (5, "1", "РџСЂРµРјРёСѓРј"),
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
			types.InlineKeyboardButton("рџ’ё РћРїР»Р°С‚РёС‚СЊ", url=pay_url),
			types.InlineKeyboardButton("рџ”Ќ РџСЂРѕРІРµСЂРёС‚СЊ", callback_data=f'check_status_{invoice_id}_{st}_{sub_days}')
		)
		pay_check.add(keyboards.back)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=f">вљ™пёЏ *РџРѕРєСѓРїРєР°*\n*в””в”Ђ Р’С‹ РїРѕРєСѓРїР°РµС‚Рµ: {pidor}*\n*в””в”Ђ Р’С‹ РїР»Р°С‚РёС‚Рµ: {amount}$*",
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
			await bot.send_message(user_id, "вќЊ *РћРїР»Р°С‚Р° РЅРµ РїРѕР»СѓС‡РµРЅР°!*", parse_mode=ParseMode.MARKDOWN)
			return
		# Р—Р°С‰РёС‚Р° РѕС‚ РїРѕРІС‚РѕСЂРЅРѕРіРѕ РЅР°С‡РёСЃР»РµРЅРёСЏ
		if await db.is_invoice_used(invoice_id):
			await bot.send_message(user_id, "вњ… *Р­С‚РѕС‚ РїР»Р°С‚С‘Р¶ СѓР¶Рµ Р±С‹Р» РѕР±СЂР°Р±РѕС‚Р°РЅ!*", parse_mode=ParseMode.MARKDOWN)
			return
		await db.mark_invoice_used(invoice_id, user_id)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=">вљ™пёЏ *РЎРїР°СЃРёР±Рѕ Р·Р° Р·Р°РєР°Р·*", parse_mode="MarkdownV2", reply_markup=back_markup
		)
		if sub_type != "premupgrade":
			new_date = (now_msk() + timedelta(days=int(sub_days))).strftime("%Y-%m-%d %H:%M:%S")
			await db.set_subscribe(user_id, new_date)
			await bot.send_message(bot_logs, f"рџ’і *РћРїР»Р°С‚Р° РїРѕРґРїРёСЃРєРё* `{user_id}` *РґРѕ* `{new_date}`", parse_mode="Markdown")
			# Р РµС„РµСЂР°Р»СЊРЅС‹Р№ Р±РѕРЅСѓСЃ вЂ” 10% РѕС‚ РґРЅРµР№ РїРѕРґРїРёСЃРєРё СЂРµС„РµСЂРµСЂСѓ
			referrer_id = await db.get_referrer_id(user_id)
			if referrer_id:
				bonus_days = max(1, int(int(sub_days) * 0.1))
				ref_new_date = (now_msk() + timedelta(days=bonus_days)).strftime("%Y-%m-%d %H:%M:%S")
				await db.set_subscribe(referrer_id, ref_new_date)
				await bot.send_message(
					referrer_id,
					f"рџ’° *Р РµС„РµСЂР°Р»СЊРЅС‹Р№ Р±РѕРЅСѓСЃ!*\n"
					f"*в””в”Ђ Р’Р°С€ СЂРµС„РµСЂР°Р» РєСѓРїРёР» РїРѕРґРїРёСЃРєСѓ*\n"
					f"*в””в”Ђ Р’Р°Рј РЅР°С‡РёСЃР»РµРЅРѕ: +{bonus_days} РґРµРЅСЊ РїРѕРґРїРёСЃРєРё*",
					parse_mode="Markdown"
				)
		else:
			await db.set_premium(user_id, 1)
			await bot.send_message(bot_logs, f"рџ’і *Premium* `{user_id}`", parse_mode="Markdown")
	except Exception as e:
		print(f"check_status_callback: {e}")

# в”Ђв”Ђв”Ђ РџСЂРѕРјРѕРєРѕРґС‹ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

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
		await message.answer(f"рџ’Ћ РЎРѕР·РґР°РЅ РїСЂРѕРјРѕРєРѕРґ `{code}` РЅР° {days} РґРЅРµР№, {activations} Р°РєС‚РёРІР°С†РёР№", parse_mode="Markdown")
	except Exception:
		await message.answer(f"вќ—пёЏ РџСЂРѕРјРѕРєРѕРґ `{code}` СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚!", parse_mode="Markdown")

# в”Ђв”Ђв”Ђ /start СЃ РєР°РїС‡РµР№ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.message_handler(commands=['start'], state='*')
async def welcome(message: types.Message, state: FSMContext):
	# РЎР±СЂР°СЃС‹РІР°РµРј Р»СЋР±РѕРµ Р°РєС‚РёРІРЅРѕРµ FSM СЃРѕСЃС‚РѕСЏРЅРёРµ РїСЂРё /start
	current = await state.get_state()
	if current is not None:
		await state.finish()
	if await is_blocked(message.from_user.id):
		return
	if check_rate_limit(message.from_user.id):
		await block_user(message.from_user.id)
		await message.reply("РџСЂРµРІС‹СЃРёР»Рё Р»РёРјРёС‚ Р·Р°РїСЂРѕСЃРѕРІ, Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅС‹.")
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
				caption=f"*РџСЂРёРІРµС‚, {message.from_user.first_name}!*\n\n*Р”РѕРєР°Р¶Рё, С‡С‚Рѕ С‚С‹ РЅРµ СЂРѕР±РѕС‚ рџ¤–*\n*в””в”Ђ Р’РІРµРґРё РєРѕРґ СЃ РєР°СЂС‚РёРЅРєРё:*",
				parse_mode="Markdown")
		except Exception as e:
			print(f"[CAPTCHA] РћС€РёР±РєР° РіРµРЅРµСЂР°С†РёРё: {e}", flush=True)
			await bot.send_message(uid, "вќЊ *РћС€РёР±РєР° РіРµРЅРµСЂР°С†РёРё РєР°РїС‡Рё. РџРѕРїСЂРѕР±СѓР№С‚Рµ /start СЃРЅРѕРІР°.*", parse_mode="Markdown")
			return
		# РЎРѕС…СЂР°РЅСЏРµРј СЂРµС„-Р°СЂРіСѓРјРµРЅС‚ РІ FSM вЂ” РїСЂРёРјРµРЅРёРј С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ РїСЂРѕС…РѕР¶РґРµРЅРёСЏ РєР°РїС‡Рё
		await WaitCaptchaFSM.code.set()
		if is_new:
			args = message.get_args()
			if args and args.startswith("ref_"):
				async with dp.current_state(user=uid).proxy() as fsm_data:
					fsm_data['ref_arg'] = args
		return
	await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
	# РџСЂРѕРІРµСЂСЏРµРј РїРѕРґРїРёСЃРєСѓ РїРµСЂРµРґ РїРѕРєР°Р·РѕРј РјРµРЅСЋ
	if not await check_subscription(uid):
		await send_subscribe_required(uid)
		return
	await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
		caption='>*Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ Brown V2\!*\n\n*РњРµРЅСЋ:*',
		parse_mode="MarkdownV2", reply_markup=menu)

@dp.message_handler(state=WaitCaptchaFSM.code)
async def check_captcha(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	if message.text.strip().lower() == _captcha_codes.get(uid, "").lower():
		fsm_data = await state.get_data()
		await state.finish()
		_captcha_codes.pop(uid, None)
		await set_verified(uid)

		# Р РµС„РµСЂР°Р»СЊРЅР°СЏ Р»РѕРіРёРєР° вЂ” С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ РїСЂРѕС…РѕР¶РґРµРЅРёСЏ РєР°РїС‡Рё
		ref_arg = fsm_data.get('ref_arg')
		if ref_arg and ref_arg.startswith("ref_"):
			try:
				referrer_id = int(ref_arg[4:])
				if referrer_id != uid and await db.user_exists(referrer_id):
					await db.set_referrer(uid, referrer_id)
					new_count = await db.increment_referral_count(referrer_id)
					await bot.send_message(
						referrer_id,
						f"рџ‘Ґ *РџРѕ РІР°С€РµР№ СЃСЃС‹Р»РєРµ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°Р»СЃСЏ РЅРѕРІС‹Р№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ!*\n"
						f"*в””в”Ђ Р’СЃРµРіРѕ СЂРµС„РµСЂР°Р»РѕРІ: {new_count}*",
						parse_mode="Markdown"
					)
			except (ValueError, Exception):
				pass

		await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
		# РџСЂРѕРІРµСЂСЏРµРј РїРѕРґРїРёСЃРєСѓ РїРѕСЃР»Рµ РєР°РїС‡Рё
		if not await check_subscription(uid):
			await send_subscribe_required(uid)
			return
		# Р—Р°РєСЂРµРїР»С‘РЅРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ РїРѕСЃР»Рµ РєР°РїС‡Рё
		await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
			caption='>*Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ Brown V2\!*\n\n*РњРµРЅСЋ:*',
			parse_mode="MarkdownV2", reply_markup=menu)
	else:
		try:
			code = generate_captcha_text()
			_captcha_codes[uid] = code
			await bot.send_photo(uid, photo=generate_captcha_image(code),
				caption="*вќЊ РќРµРІРµСЂРЅРѕ! РџРѕРїСЂРѕР±СѓР№ РµС‰С‘ СЂР°Р·:*", parse_mode="Markdown")
		except Exception as e:
			print(f"[CAPTCHA] РћС€РёР±РєР° РїРѕРІС‚РѕСЂРЅРѕР№ РіРµРЅРµСЂР°С†РёРё: {e}", flush=True)
			await bot.send_message(uid, "вќЊ *РћС€РёР±РєР° РіРµРЅРµСЂР°С†РёРё РєР°РїС‡Рё. РџРѕРїСЂРѕР±СѓР№С‚Рµ /start СЃРЅРѕРІР°.*", parse_mode="Markdown")

# в”Ђв”Ђв”Ђ РџСЂРѕРІРµСЂРєР° РїРѕРґРїРёСЃРєРё РїРѕ РєРЅРѕРїРєРµ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

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
			caption='>*Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ Brown V2\!*\n\n*РњРµРЅСЋ:*',
			parse_mode="MarkdownV2", reply_markup=menu)
	else:
		await bot.answer_callback_query(call.id, "вќЊ Р’С‹ РµС‰С‘ РЅРµ РїРѕРґРїРёСЃР°Р»РёСЃСЊ!", show_alert=True)

# в”Ђв”Ђв”Ђ Р“Р»Р°РІРЅС‹Р№ callback С…РµРЅРґР»РµСЂ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.callback_query_handler(lambda call: True, state='*')
async def callback_inline(call: types.CallbackQuery, state: FSMContext):
	await handle_callback(call, bot, dp, state)

async def handle_callback(call: types.CallbackQuery, bot_instance, dp_instance, state: FSMContext):
	"""РћР±С‰Р°СЏ Р»РѕРіРёРєР° callback вЂ” РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ Рё РѕСЃРЅРѕРІРЅС‹Рј Р±РѕС‚РѕРј, Рё Р·РµСЂРєР°Р»Р°РјРё."""
	# РџРѕР»СѓС‡Р°РµРј С‚РѕРєРµРЅ bot_instance Р±РµР·РѕРїР°СЃРЅРѕ (aiogram 2 С…СЂР°РЅРёС‚ РІ _token)
	_instance_token = getattr(bot_instance, '_token', None)
	try:
		uid = call.from_user.id
		if await is_blocked(uid):
			return
		if check_rate_limit(uid):
			await block_user(uid)
			await call.message.answer("РџСЂРµРІС‹СЃРёР»Рё Р»РёРјРёС‚, Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅС‹.")
			return
		if not await check_user_in_db(uid):
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*РџСЂРѕРїРёС€РёС‚Рµ /start*", parse_mode="Markdown")
			return
		if not await subsribe_channel(uid, channel_id) or not await subsribe_channel(uid, channel2_id):
			# РЎРѕР·РґР°С‘Рј РІСЂРµРјРµРЅРЅС‹Рµ invite links С‡РµСЂРµР· РѕСЃРЅРѕРІРЅРѕР№ Р±РѕС‚ (С‚РѕР»СЊРєРѕ РѕРЅ вЂ” Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ РєР°РЅР°Р»Р°)
			try:
				import time as _time
				expire = int(_time.time()) + 60
				link1 = await bot.create_chat_invite_link(channel_id, expire_date=expire, member_limit=1)
				link2 = await bot.create_chat_invite_link(channel2_id, expire_date=expire, member_limit=1)
				invite1 = link1.invite_link
				invite2 = link2.invite_link
			except Exception as e:
				print(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ invite link: {e}", flush=True)
				invite1 = config.bot_channel_link
				invite2 = config.bot_channel2_link
			temp_check_markup = types.InlineKeyboardMarkup(row_width=1)
			temp_check_markup.add(
				types.InlineKeyboardButton("[1пёЏвѓЈ] РџРѕРґРїРёС€РёСЃСЊ (1 РјРёРЅ)", url=invite1),
				types.InlineKeyboardButton("[2пёЏвѓЈ] РџРѕРґРїРёС€РёСЃСЊ (1 РјРёРЅ)", url=invite2),
				types.InlineKeyboardButton("[рџ”Ћ] РџСЂРѕРІРµСЂРёС‚СЊ", callback_data='start_check_sub')
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*вљ пёЏ РџРѕРґРїРёС€РёС‚РµСЃСЊ РЅР° РєР°РЅР°Р»С‹!*\n*в””в”Ђ РЎСЃС‹Р»РєРё РґРµР№СЃС‚РІСѓСЋС‚ 1 РјРёРЅСѓС‚Сѓ*", parse_mode="Markdown", reply_markup=temp_check_markup)
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

		# РљРЅРѕРїРєР° РїСЂРѕРІРµСЂРєРё РїРѕРґРїРёСЃРєРё вЂ” РѕР±СЂР°Р±Р°С‚С‹РІР°РµРј Р·РґРµСЃСЊ С‚РѕР¶Рµ (РґР»СЏ Р·РµСЂРєР°Р»)
		if d == 'start_check_sub':
			if await check_subscription(uid):
				try:
					await bot_instance.delete_message(uid, call.message.message_id)
				except Exception:
					pass
				await bot_instance.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
				await bot_instance.send_photo(uid, photo=open('material/menu.png', 'rb'),
					caption='>*Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ Brown V2\!*\n\n*РњРµРЅСЋ:*',
					parse_mode="MarkdownV2", reply_markup=menu)
			else:
				await bot_instance.answer_callback_query(call.id, "вќЊ Р’С‹ РµС‰С‘ РЅРµ РїРѕРґРїРёСЃР°Р»РёСЃСЊ!", show_alert=True)
			return

		if d == 'functions':
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="*Р—Р°РєР°Р·*\n\n>*РџРѕСЃРјРѕС‚СЂРёС‚Рµ РњР°РЅСѓР°Р»*", parse_mode="MarkdownV2", reply_markup=functions)
		elif d == 'profile':
			sub_text = "РСЃС‚РµРєР»Р°" if subscribe < now_msk() else f"РѕСЃС‚Р°Р»РѕСЃСЊ {(subscribe - now_msk()).days} РґРЅРµР№"
			prem = "Р”Р°" if premium == 1 else "РќРµС‚"
			free_reports = await db.get_free_reports(uid)
			ref_count = await db.get_referral_count(uid)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=f"*РџСЂРѕС„РёР»СЊ*\n\nв–ЄпёЏ *РРјСЏ: {fullname}*\nв–ЄпёЏ *ID: {uid}*\nв–ЄпёЏ *@{username}*\nв–ЄпёЏ *РџСЂРµРјРёСѓРј: {prem}*\nв–ЄпёЏ *Р‘РµСЃРїР»Р°С‚РЅС‹С… СЂРµРїРѕСЂС‚РѕРІ: {free_reports}*\nв–ЄпёЏ *Р РµС„РµСЂР°Р»РѕРІ: {ref_count}*\n\nвЏі *{sub_text}*",
				parse_mode="Markdown", reply_markup=back_markup)
		elif d == "back":
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption='>*Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ Brown V2\!*\n\n*РњРµРЅСЋ:*',
				parse_mode="MarkdownV2", reply_markup=menu)
		elif d == "information":
			# Р“РµРЅРµСЂРёСЂСѓРµРј РІСЂРµРјРµРЅРЅСѓСЋ СЃСЃС‹Р»РєСѓ С‡РµСЂРµР· РѕСЃРЅРѕРІРЅРѕР№ Р±РѕС‚
			try:
				import time as _time
				expire = int(_time.time()) + 60
				link = await bot.create_chat_invite_link(channel_id, expire_date=expire, member_limit=1)
				channel_invite = link.invite_link
			except Exception as e:
				print(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ invite link РґР»СЏ РёРЅС„РѕСЂРјР°С†РёРё: {e}", flush=True)
				channel_invite = config.bot_channel_link
			dyn_info_markup = types.InlineKeyboardMarkup(row_width=2)
			dyn_info_markup.add(
				types.InlineKeyboardButton("РјРІ РљР°РЅР°Р» (1 РјРёРЅ)", url=channel_invite),
				types.InlineKeyboardButton("рџ“„ РњР°РЅСѓР°Р»", url='https://teletype.in/@brownv2/manual'),
			)
			dyn_info_markup.add(
				types.InlineKeyboardButton("рџ‘‘ Р’Р»Р°РґРµР»РµС†", url='https://t.me/TariSmit'),
				types.InlineKeyboardButton("рџ† РџРѕРґРґРµСЂР¶РєР°", url='https://t.me/BR_V2_support'),
			)
			dyn_info_markup.add(keyboards.back)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=">*РРЅС„РѕСЂРјР°С†РёСЏ*", parse_mode="MarkdownV2", reply_markup=dyn_info_markup)
		elif d == "shop":
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="вљ™пёЏ *РђСЃСЃРѕСЂС‚РёРјРµРЅС‚*\n\n>*в””в”Ђ 1 РґРµРЅСЊ \- 1$ / 100в‚Ѕ*\n>*в””в”Ђ 3 РґРЅСЏ \- 2$ / 175в‚Ѕ*\n>*в””в”Ђ 7 РґРЅРµР№ \- 4$ / 350в‚Ѕ*\n>*в””в”Ђ 30 РґРЅРµР№ \- 8$ / 700в‚Ѕ*\n>*в””в”Ђ РќР°РІСЃРµРіРґР° \- 6$ / 500в‚Ѕ \[\-70%\]*\n\n>*рџ‘‘ РџСЂРµРјРёСѓРј: 5$ / 400в‚Ѕ \[\-50%\]*",
				parse_mode="MarkdownV2", reply_markup=shop_markup)
		elif d == "buyforadmins":
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("вњЌпёЏ РќР°РїРёСЃР°С‚СЊ @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="рџ’і *РћРїР»Р°С‚Р° РєР°СЂС‚РѕР№*\n\n*в””в”Ђ РќР°РїРёС€РёС‚Рµ* @TariSmit *Рё СЏ СЃРєРёРЅСѓ РІР°Рј СЃСЃС‹Р»РєСѓ РґР»СЏ РѕРїР»Р°С‚С‹\.*",
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "yoomoney":
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("вњЌпёЏ РќР°РїРёСЃР°С‚СЊ @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="рџ’і *РћРїР»Р°С‚Р° РєР°СЂС‚РѕР№*\n\n*в””в”Ђ РќР°РїРёС€РёС‚Рµ* @TariSmit *Рё СЏ СЃРєРёРЅСѓ РІР°Рј СЃСЃС‹Р»РєСѓ РґР»СЏ РѕРїР»Р°С‚С‹\.*",
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "tinkoff":
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("вњЌпёЏ РќР°РїРёСЃР°С‚СЊ @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="рџ’і *РћРїР»Р°С‚Р° РєР°СЂС‚РѕР№*\n\n*в””в”Ђ РќР°РїРёС€РёС‚Рµ* @TariSmit *Рё СЏ СЃРєРёРЅСѓ РІР°Рј СЃСЃС‹Р»РєСѓ РґР»СЏ РѕРїР»Р°С‚С‹\.*",
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "sberbank":
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("вњЌпёЏ РќР°РїРёСЃР°С‚СЊ @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="рџ’і *РћРїР»Р°С‚Р° РєР°СЂС‚РѕР№*\n\n*в””в”Ђ РќР°РїРёС€РёС‚Рµ* @TariSmit *Рё СЏ СЃРєРёРЅСѓ РІР°Рј СЃСЃС‹Р»РєСѓ РґР»СЏ РѕРїР»Р°С‚С‹\.*",
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "preminfo":
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="рџ‘‘ *РџСЂРµРјРёСѓРј*\n\n>*в””в”Ђ РїРѕС‡С‚С‹, РІРµР±, РїСЂРµРј РѕС‚РїСЂР°РІРєСѓ*\n\nвЂјпёЏ РџРѕРєСѓРїР°РµС‚СЃСЏ РєР°Рє Р”РћРџРћР›РќР•РќРР• Рє РїРѕРґРїРёСЃРєРµ вЂјпёЏ",
				parse_mode="MarkdownV2", reply_markup=back_markup)
		elif d == "close":
			await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
		elif d == "go_to_main_menu":
			await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
			await bot_instance.send_photo(call.message.chat.id, photo=open('material/menu.png', 'rb'),
				caption='>*Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ Brown V2\!*\n\n*РњРµРЅСЋ:*', parse_mode="MarkdownV2", reply_markup=menu)
		elif d == 'add_subsribe' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'рџЋ± *Р’С‹РґР°С‡Р° РїРѕРґРїРёСЃРєРё*\n*в””в”ЂР’РІРµРґРёС‚Рµ ID РёР»Рё @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AddSubscribeFSM.user_id.state)
		elif d == 'clear_subscribe' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'рџЋ± *РЎР±СЂРѕСЃ РїРѕРґРїРёСЃРєРё*\n*в””в”ЂР’РІРµРґРёС‚Рµ ID РёР»Рё @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(ClearSubscribeFSM.user_id.state)
		elif d == 'add_prem' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'рџЋ± *Р’С‹РґР°С‡Р° РїСЂРµРјРёСѓРјР°*\n*в””в”ЂР’РІРµРґРёС‚Рµ ID РёР»Рё @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AddPremFSM.user_id.state)
		elif d == 'clear_prem' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'рџЋ± *РЎР±СЂРѕСЃ РїСЂРµРјРёСѓРјР°*\n*в””в”ЂР’РІРµРґРёС‚Рµ ID РёР»Рё @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(ClearPremFSM.user_id.state)
		elif d == 'send_all' and uid in admins and uid in admins2:
			await bot_instance.send_message(call.message.chat.id, 'рџЋ± *Р Р°СЃСЃС‹Р»РєР°*\n*в””в”ЂР’РІРµРґРёС‚Рµ С‚РµРєСЃС‚:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTextZFSM.text.state)
		elif d == 'block_user_admin' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'рџљ« *Р‘Р»РѕРєРёСЂРѕРІРєР°*\n*в””в”ЂР’РІРµРґРёС‚Рµ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(BlockUserFSM.user_id.state)
		elif d == 'unblock_user_admin' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'вњ… *Р Р°Р·Р±Р»РѕРєРёСЂРѕРІРєР°*\n*в””в”ЂР’РІРµРґРёС‚Рµ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(UnblockUserFSM.user_id.state)
		elif d == 'admin_create_promo' and uid in admins:
			await bot_instance.send_message(
				call.message.chat.id,
				'рџ’Ћ *РЎРѕР·РґР°РЅРёРµ РїСЂРѕРјРѕРєРѕРґР°*\n\n*в””в”Ђ Р’С‹Р±РµСЂРёС‚Рµ С‚РёРї:*',
				parse_mode="Markdown",
				reply_markup=keyboards.promo_type_markup
			)

		elif d == 'delete_user_admin' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'рџ—‘ *РЈРґР°Р»РµРЅРёРµ РёР· Р±Р°Р·С‹*\n*в””в”ЂР’РІРµРґРёС‚Рµ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(DeleteUserFSM.user_id.state)

		elif d == 'promo_type_normal' and uid in admins:
			state_proxy = dp_instance.current_state(chat=uid, user=uid)
			await state_proxy.set_state(CreatePromoFSM.code.state)
			async with state_proxy.proxy() as fsm_data:
				fsm_data['promo_type'] = 'normal'
			await bot_instance.send_message(call.message.chat.id, 'рџ’Ћ *РћР±С‹С‡РЅС‹Р№ РїСЂРѕРјРѕРєРѕРґ*\n*в””в”Ђ Р’РІРµРґРёС‚Рµ РєРѕРґ:*', parse_mode="Markdown")

		elif d == 'promo_type_premium' and uid in admins:
			state_proxy = dp_instance.current_state(chat=uid, user=uid)
			await state_proxy.set_state(CreatePromoFSM.code.state)
			async with state_proxy.proxy() as fsm_data:
				fsm_data['promo_type'] = 'premium'
			await bot_instance.send_message(call.message.chat.id, 'рџ‘‘ *РџСЂРµРјРёСѓРј РїСЂРѕРјРѕРєРѕРґ*\n*в””в”Ђ Р’РІРµРґРёС‚Рµ РєРѕРґ:*', parse_mode="Markdown")

		elif d == 'promo_type_reports' and uid in admins:
			state_proxy = dp_instance.current_state(chat=uid, user=uid)
			await state_proxy.set_state(CreatePromoFSM.code.state)
			async with state_proxy.proxy() as fsm_data:
				fsm_data['promo_type'] = 'reports'
			await bot_instance.send_message(call.message.chat.id, 'рџЋЇ *РџСЂРѕРјРѕРєРѕРґ РЅР° СЂРµРїРѕСЂС‚С‹*\n*в””в”Ђ Р’РІРµРґРёС‚Рµ РєРѕРґ:*', parse_mode="Markdown")
		elif d.startswith('users_list_') and uid in admins:
			page = int(d.split('_')[2])
			PAGE_SIZE = 10
			users = await db.get_users_page(offset=page * PAGE_SIZE, limit=PAGE_SIZE)
			total = await db.get_users_count()
			total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

			if not users:
				await bot_instance.answer_callback_query(call.id, "Р‘РѕР»СЊС€Рµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РЅРµС‚", show_alert=False)
				return

			lines = [f"рџ‘Ґ *РџРѕР»СЊР·РѕРІР°С‚РµР»Рё* (СЃС‚СЂ. {page+1}/{total_pages})\n"]
			now = now_msk()
			for u in users:
				uid_u = u['user_id']
				sub = u['subscribe']
				sub_str = "вњ… Р°РєС‚РёРІРЅР°" if isinstance(sub, datetime) and sub > now else "вќЊ РЅРµС‚"
				prem = "рџ‘‘" if u['premium'] else ""
				free = f"рџЋЇ{u['free_reports']}" if u['free_reports'] > 0 else ""
				lines.append(f"`{uid_u}` вЂ” {sub_str} {prem}{free}")

			text = "\n".join(lines)

			nav = types.InlineKeyboardMarkup(row_width=2)
			btns = []
			if page > 0:
				btns.append(types.InlineKeyboardButton("в—ЂпёЏ РќР°Р·Р°Рґ", callback_data=f'users_list_{page-1}'))
			if (page + 1) < total_pages:
				btns.append(types.InlineKeyboardButton("Р’РїРµСЂС‘Рґ в–¶пёЏ", callback_data=f'users_list_{page+1}'))
			if btns:
				nav.row(*btns)
			nav.add(types.InlineKeyboardButton("рџ”™ Р—Р°РєСЂС‹С‚СЊ", callback_data='close'))

			await bot_instance.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=nav)

		elif d.startswith('admin_mirrors_') and uid in admins:
			page = int(d.split('_')[2])
			PAGE_SIZE = 8
			all_mirrors = await db.get_all_mirrors()
			total = len(all_mirrors)
			total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
			page_mirrors = all_mirrors[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

			if not all_mirrors:
				await bot_instance.answer_callback_query(call.id, "Р—РµСЂРєР°Р» РЅРµС‚.", show_alert=False)
				return

			lines = [f"рџЄћ *Р—РµСЂРєР°Р»Р°* (СЃС‚СЂ. {page+1}/{total_pages}, РІСЃРµРіРѕ: {total})\n"]
			for m in page_mirrors:
				lines.append(f"`{m['bot_username']}` вЂ” `{m['user_id']}`\n`{m['token']}`\n")

			nav = types.InlineKeyboardMarkup(row_width=2)
			btns = []
			if page > 0:
				btns.append(types.InlineKeyboardButton("в—ЂпёЏ", callback_data=f'admin_mirrors_{page-1}'))
			if (page + 1) < total_pages:
				btns.append(types.InlineKeyboardButton("в–¶пёЏ", callback_data=f'admin_mirrors_{page+1}'))
			if btns:
				nav.row(*btns)
			nav.add(types.InlineKeyboardButton("рџ”™ Р—Р°РєСЂС‹С‚СЊ", callback_data='close'))

			await bot_instance.send_message(call.message.chat.id, "\n".join(lines), parse_mode="Markdown", reply_markup=nav)

		elif d == 'admin_add_reports' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'рџЋЇ *Р’С‹РґР°С‡Р° СЂРµРїРѕСЂС‚РѕРІ*\n*в””в”Ђ Р’РІРµРґРёС‚Рµ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AdminAddReportsFSM.user_id.state)

		elif d == 'admin_remove_reports' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, 'рџЋЇ *РћС‚Р·С‹РІ СЂРµРїРѕСЂС‚РѕРІ*\n*в””в”Ђ Р’РІРµРґРёС‚Рµ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AdminRemoveReportsFSM.user_id.state)
		elif d == 'promo':
			await bot_instance.send_message(call.message.chat.id, 'рџЋ± *РђРєС‚РёРІР°С†РёСЏ РїСЂРѕРјРѕРєРѕРґР°*\n*в””в”ЂР’РІРµРґРёС‚Рµ РїСЂРѕРјРѕРєРѕРґ:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitPromoFSM.promo.state)

		elif d == 'promo_check_name':
			full_name = (call.from_user.first_name or "") + " " + (call.from_user.last_name or "")
			if "Brrown_V2bot" in full_name or "Brrown_V2bot" in (call.from_user.username or ""):
				await bot_instance.answer_callback_query(call.id, "вњ… РћС‚Р»РёС‡РЅРѕ! РўРµРїРµСЂСЊ РІРІРµРґРё РїСЂРѕРјРѕРєРѕРґ.", show_alert=False)
				await bot_instance.send_message(call.message.chat.id, 'рџЋ± *РРјСЏ РїСЂРѕРІРµСЂРµРЅРѕ!*\n*в””в”Ђ Р’РІРµРґРёС‚Рµ РїСЂРѕРјРѕРєРѕРґ:*', parse_mode="Markdown")
				await dp_instance.current_state(chat=uid, user=uid).set_state(WaitPromoFSM.promo.state)
			else:
				await bot_instance.answer_callback_query(call.id, "вќЊ @Brrown_V2bot РЅРµ РЅР°Р№РґРµРЅ РІ РёРјРµРЅРё. Р”РѕР±Р°РІСЊ Рё РїРѕРїСЂРѕР±СѓР№ СЃРЅРѕРІР°.", show_alert=True)

		# в”Ђв”Ђв”Ђ Р РµС„РµСЂР°Р»СЊРЅР°СЏ СЃРёСЃС‚РµРјР° в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == 'referral':
			ref_count = await db.get_referral_count(uid)
			# РџРѕР»СѓС‡Р°РµРј username С‚РµРєСѓС‰РµРіРѕ Р±РѕС‚Р° РґР»СЏ СЂРµС„РµСЂР°Р»СЊРЅРѕР№ СЃСЃС‹Р»РєРё
			try:
				me = await bot_instance.get_me()
				bot_uname = me.username
			except Exception:
				bot_uname = bot_username[1:]
			ref_link = f"https://t.me/{bot_uname}?start=ref_{uid}"
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"рџ‘Ґ *Р РµС„РµСЂР°Р»СЊРЅР°СЏ СЃРёСЃС‚РµРјР°*\n\n"
					f"*в””в”Ђ Р’Р°С€РёС… СЂРµС„РµСЂР°Р»РѕРІ: {ref_count}*\n\n"
					f"рџ“Ћ *Р’Р°С€Р° СЃСЃС‹Р»РєР°:*\n`{ref_link}`\n\n"
					f"*Р—Р° РєР°Р¶РґС‹Рµ 10 СЂРµС„РµСЂР°Р»РѕРІ вЂ” 1 РґРµРЅСЊ РїРѕРґРїРёСЃРєРё*\n"
					f"*РўР°РєР¶Рµ РІС‹ РїРѕР»СѓС‡Р°РµС‚Рµ 10% РѕС‚ РїРѕРєСѓРїРєРё РїРѕРґРїРёСЃРєРё РІР°С€РёРј СЂРµС„РµСЂР°Р»РѕРј*"
				),
				parse_mode="Markdown", reply_markup=keyboards.referral_markup
			)

		elif d == 'exchange_refs':
			ref_count = await db.get_referral_count(uid)
			if ref_count < 10:
				await bot_instance.answer_callback_query(call.id, f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЂРµС„РµСЂР°Р»РѕРІ! РЈ РІР°СЃ {ref_count}/10", show_alert=True)
			else:
				# РђС‚РѕРјР°СЂРЅРѕРµ СЃРЅСЏС‚РёРµ вЂ” Р·Р°С‰РёС‚Р° РѕС‚ race condition
				success = await db.spend_referrals(uid, 10)
				if not success:
					await bot_instance.answer_callback_query(call.id, "вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЂРµС„РµСЂР°Р»РѕРІ!", show_alert=True)
				else:
					new_date = (now_msk() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
					await db.set_subscribe(uid, new_date)
					remaining = ref_count - 10
					await bot_instance.answer_callback_query(call.id, "вњ… РћР±РјРµРЅСЏРЅРѕ! +1 РґРµРЅСЊ РїРѕРґРїРёСЃРєРё", show_alert=True)
					try:
						me = await bot_instance.get_me()
						bot_uname = me.username
					except Exception:
						bot_uname = bot_username[1:]
					await bot_instance.edit_message_caption(
						call.message.chat.id, call.message.message_id,
						caption=(
							f"рџ‘Ґ *Р РµС„РµСЂР°Р»СЊРЅР°СЏ СЃРёСЃС‚РµРјР°*\n\n"
							f"*в””в”Ђ Р’Р°С€РёС… СЂРµС„РµСЂР°Р»РѕРІ: {remaining}*\n\n"
							f"рџ“Ћ *Р’Р°С€Р° СЃСЃС‹Р»РєР°:*\n`https://t.me/{bot_uname}?start=ref_{uid}`\n\n"
							f"*вњ… РЈСЃРїРµС€РЅРѕ РѕР±РјРµРЅСЏРЅРѕ 10 СЂРµС„РµСЂР°Р»РѕРІ РЅР° 1 РґРµРЅСЊ РїРѕРґРїРёСЃРєРё!*"
						),
						parse_mode="Markdown", reply_markup=keyboards.referral_markup
					)
					await bot.send_message(bot_logs, f"рџ”„ `{uid}` РѕР±РјРµРЅСЏР» 10 СЂРµС„РµСЂР°Р»РѕРІ РЅР° 1 РґРµРЅСЊ", parse_mode="Markdown")

		# в”Ђв”Ђв”Ђ Р‘РµСЃРїР»Р°С‚РЅРѕ / Р—РµСЂРєР°Р»Р° в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == 'free_menu':
			mirror_count = await db.count_user_mirrors(uid)
			free_reports = await db.get_free_reports(uid)
			bonus_given = await db.get_mirror_bonus_given(uid)
			bonus_status = "вњ… РџРѕР»СѓС‡РµРЅ" if bonus_given else f"{'рџ”’ РќСѓР¶РЅРѕ 2 Р·РµСЂРєР°Р»Р°' if mirror_count < 2 else 'в¬†пёЏ Р”РѕСЃС‚СѓРїРµРЅ вЂ” СЃРѕР·РґР°Р№ Р·РµСЂРєР°Р»Рѕ!'}"
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"рџ†“ *Р‘РµСЃРїР»Р°С‚РЅС‹Рµ СЂРµРїРѕСЂС‚С‹*\n\n"
					f"в–ЄпёЏ *Р‘РµСЃРїР»Р°С‚РЅС‹С… СЂРµРїРѕСЂС‚РѕРІ: {free_reports}*\n"
					f"в–ЄпёЏ *Р—РµСЂРєР°Р» СЃРѕР·РґР°РЅРѕ: {mirror_count}*\n"
					f"в–ЄпёЏ *Р‘РѕРЅСѓСЃ Р·Р° Р·РµСЂРєР°Р»Р°: {bonus_status}*\n\n"
					f"рџЄћ *РљР°Рє РїРѕР»СѓС‡РёС‚СЊ Р±РѕРЅСѓСЃ:*\n"
					f"*в””в”Ђ РЎРѕР·РґР°Р№ Р±РѕС‚Р° С‡РµСЂРµР· @BotFather*\n"
					f"*в””в”Ђ РЎРєРёРЅСЊ РЅР°Рј С‚РѕРєРµРЅ*\n"
					f"*в””в”Ђ РџСЂРё 2-Рј Р·РµСЂРєР°Р»Рµ вЂ” +1 СЂРµРїРѕСЂС‚ (1 СЂР°Р·)*\n\n"
					f"*Р—РµСЂРєР°Р» РјРѕР¶РЅРѕ СЃРѕР·РґР°РІР°С‚СЊ РЅРµРѕРіСЂР°РЅРёС‡РµРЅРЅРѕ*"
				),
				parse_mode="Markdown", reply_markup=keyboards.free_menu_markup
			)

		elif d == 'mirror_create':
			await bot_instance.send_message(
				call.message.chat.id,
				"рџЄћ *РЎРѕР·РґР°РЅРёРµ Р·РµСЂРєР°Р»Р°*\n\n"
				"*1.* РћС‚РєСЂРѕР№ @BotFather\n"
				"*2.* РќР°РїРёС€Рё /newbot\n"
				"*3.* РџСЂРёРґСѓРјР°Р№ РёРјСЏ Рё username Р±РѕС‚Сѓ\n"
				"*4.* РЎРєРѕРїРёСЂСѓР№ С‚РѕРєРµРЅ Рё РѕС‚РїСЂР°РІСЊ РµРіРѕ СЃСЋРґР°:\n\n"
				"*Р¤РѕСЂРјР°С‚:* `1234567890:ABCdef...`",
				parse_mode="Markdown"
			)
			state_proxy = dp_instance.current_state(chat=uid, user=uid)
			if bot_instance is not bot:
				# Р—РµСЂРєР°Р»СЊРЅС‹Р№ Р±РѕС‚ вЂ” РёСЃРїРѕР»СЊР·СѓРµРј MirrorCreateFSM РєРѕС‚РѕСЂС‹Р№ СѓР¶Рµ РѕС‚РІРµС‡Р°РµС‚ С‡РµСЂРµР· mirror_bot
				from mirror_manager import MirrorCreateFSM
				await state_proxy.set_state(MirrorCreateFSM.token.state)
			else:
				await state_proxy.set_state(WaitMirrorTokenFSM.token.state)

		elif d == 'mirror_list':
			mirrors = await db.get_user_mirrors(uid)
			if not mirrors:
				await bot_instance.answer_callback_query(call.id, "РЈ РІР°СЃ РЅРµС‚ Р·РµСЂРєР°Р».", show_alert=True)
				return
			import random as _random
			total_mirrors = len(mirrors)
			shown = _random.sample(mirrors, min(5, total_mirrors))
			lines = [f"рџЄћ *Р’Р°С€Рё Р·РµСЂРєР°Р»Р°* (РїРѕРєР°Р·Р°РЅРѕ 5 РёР· {total_mirrors}):\n"]
			for i, m in enumerate(shown, 1):
				lines.append(f"*{i}.* `{m['bot_username']}`")
			refresh_markup = types.InlineKeyboardMarkup(row_width=1)
			refresh_markup.add(
				types.InlineKeyboardButton("рџ”„ РћР±РЅРѕРІРёС‚СЊ", callback_data='mirror_list'),
				keyboards.back
			)
			await bot_instance.send_message(
				call.message.chat.id,
				"\n".join(lines),
				parse_mode="Markdown",
				reply_markup=refresh_markup
			)

		# в”Ђв”Ђв”Ђ РџСѓР±Р»РёС‡РЅС‹Рµ Р·РµСЂРєР°Р»Р° в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == 'public_mirrors':
			import random as _random
			all_mirrors = await db.get_all_mirrors()
			if not all_mirrors:
				await bot_instance.answer_callback_query(call.id, "Р—РµСЂРєР°Р» РїРѕРєР° РЅРµС‚.", show_alert=True)
				return
			shown = _random.sample(all_mirrors, min(5, len(all_mirrors)))
			lines = ["рџЄћ *Р—РµСЂРєР°Р»Р° Brown V2*\n\n*в””в”Ђ 5 СЃР»СѓС‡Р°Р№РЅС‹С… СЂР°Р±РѕС‡РёС… Р·РµСЂРєР°Р»:*\n"]
			for m in shown:
				lines.append(f"вЂў `{m['bot_username']}`")
			refresh_markup = types.InlineKeyboardMarkup(row_width=1)
			refresh_markup.add(
				types.InlineKeyboardButton("рџ”„ РћР±РЅРѕРІРёС‚СЊ", callback_data='public_mirrors'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption="\n".join(lines),
				parse_mode="Markdown",
				reply_markup=refresh_markup
			)

		# в”Ђв”Ђв”Ђ РљРѕР»РµСЃРѕ СѓРґР°С‡Рё в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == 'wheel':
			last_spin = await db.get_wheel_last_spin(uid)
			now = now_msk()
			if last_spin and (now - last_spin).total_seconds() < 6 * 3600:
				remaining = timedelta(seconds=6*3600) - (now - last_spin)
				h = int(remaining.total_seconds() // 3600)
				m = int((remaining.total_seconds() % 3600) // 60)
				await bot_instance.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						f"рџЋЎ *РљРѕР»РµСЃРѕ СЂРµРїРѕСЂС‚РѕРІ*\n\n"
						f"вЏі *РЎР»РµРґСѓСЋС‰РёР№ СЃРїРёРЅ С‡РµСЂРµР·: {h}С‡ {m}Рј*\n\n"
						f"рџЋ° *РџСЂРёР·С‹:*\n"
						f"в–ЄпёЏ 60% вЂ” РќРёС‡РµРіРѕ\n"
						f"в–ЄпёЏ 19% вЂ” 1 СЂРµРїРѕСЂС‚\n"
						f"в–ЄпёЏ 10% вЂ” 2 СЂРµРїРѕСЂС‚Р°\n"
						f"в–ЄпёЏ 5% вЂ” 3 СЂРµРїРѕСЂС‚Р°\n"
						f"в–ЄпёЏ 1% вЂ” 5 СЂРµРїРѕСЂС‚РѕРІ рџЌЂ"
					),
					parse_mode="Markdown", reply_markup=keyboards.wheel_markup
				)
			else:
				await bot_instance.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						f"рџЋЎ *РљРѕР»РµСЃРѕ СЂРµРїРѕСЂС‚РѕРІ*\n\n"
						f"рџЋ° *РџСЂРёР·С‹:*\n"
						f"в–ЄпёЏ 60% вЂ” РќРёС‡РµРіРѕ\n"
						f"в–ЄпёЏ 19% вЂ” 1 СЂРµРїРѕСЂС‚\n"
						f"в–ЄпёЏ 10% вЂ” 2 СЂРµРїРѕСЂС‚Р°\n"
						f"в–ЄпёЏ 5% вЂ” 3 СЂРµРїРѕСЂС‚Р°\n"
						f"в–ЄпёЏ 1% вЂ” 5 СЂРµРїРѕСЂС‚РѕРІ рџЌЂ\n\n"
						f"вњ… *РљСЂСѓС‚РёС‚СЊ РјРѕР¶РЅРѕ!*"
					),
					parse_mode="Markdown", reply_markup=keyboards.wheel_markup
				)

		elif d == 'spin_wheel':
			last_spin = await db.get_wheel_last_spin(uid)
			now = now_msk()

			# РџСЂРѕРІРµСЂСЏРµРј вЂ” РІС‹РёРіСЂР°РЅР° Р»Рё РїРѕРґРїРёСЃРєР°/РїСЂРµРјРёСѓРј Рё РѕРЅР° РµС‰С‘ Р°РєС‚РёРІРЅР°
			last_prize = await db.get_wheel_prize(uid)
			if last_prize in ("forever", "sub_1d", "premium"):
				if last_prize == "premium" and premium == 1:
					await bot_instance.answer_callback_query(
						call.id, "вќЊ РљСЂСѓС‚РёС‚СЊ РЅРµР»СЊР·СЏ вЂ” Сѓ РІР°СЃ Р°РєС‚РёРІРЅС‹Р№ РІС‹РёРіСЂР°РЅРЅС‹Р№ РїСЂРµРјРёСѓРј!", show_alert=True
					)
					return
				if last_prize in ("forever", "sub_1d") and subscribe > now:
					await bot_instance.answer_callback_query(
						call.id, "вќЊ РљСЂСѓС‚РёС‚СЊ РЅРµР»СЊР·СЏ вЂ” Сѓ РІР°СЃ Р°РєС‚РёРІРЅР°СЏ РІС‹РёРіСЂР°РЅРЅР°СЏ РїРѕРґРїРёСЃРєР°!", show_alert=True
					)
					return

			if last_spin and (now - last_spin).total_seconds() < 6 * 3600:
				remaining = timedelta(seconds=6*3600) - (now - last_spin)
				h = int(remaining.total_seconds() // 3600)
				m = int((remaining.total_seconds() % 3600) // 60)
				await bot_instance.answer_callback_query(call.id, f"вЏі РЎР»РµРґСѓСЋС‰РёР№ СЃРїРёРЅ С‡РµСЂРµР· {h}С‡ {m}Рј", show_alert=True)
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
				"reports_5": ("рџЌЂ *РќРµРІРµСЂРѕСЏС‚РЅРѕ! +5 СЂРµРїРѕСЂС‚РѕРІ!*", "рџЌЂ 5 СЂРµРїРѕСЂС‚РѕРІ"),
				"reports_3": ("рџЋЇ *+3 СЂРµРїРѕСЂС‚Р°!*", "рџЋЇ 3 СЂРµРїРѕСЂС‚Р°"),
				"reports_2": ("рџЋЇ *+2 СЂРµРїРѕСЂС‚Р°!*", "рџЋЇ 2 СЂРµРїРѕСЂС‚Р°"),
				"reports_1": ("рџЋЇ *+1 СЂРµРїРѕСЂС‚!*", "рџЋЇ 1 СЂРµРїРѕСЂС‚"),
				"nothing":   ("рџ” *РќРёС‡РµРіРѕ... РџРѕРІРµР·С‘С‚ РІ СЃР»РµРґСѓСЋС‰РёР№ СЂР°Р·!*", "рџ” РќРёС‡РµРіРѕ"),
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
					f"рџЋЎ *РљРѕР»РµСЃРѕ СЂРµРїРѕСЂС‚РѕРІ*\n\n"
					f"рџЋ° Р РµР·СѓР»СЊС‚Р°С‚:\n{text}\n\n"
					f"вЏі *РЎР»РµРґСѓСЋС‰РёР№ СЃРїРёРЅ С‡РµСЂРµР· 6 С‡Р°СЃРѕРІ*"
				),
				parse_mode="Markdown", reply_markup=back_markup
			)
			await bot.send_message(bot_logs, f"рџЋЎ `{uid}` РєСЂСѓС‚РёР» РєРѕР»РµСЃРѕ вЂ” {log_text}", parse_mode="Markdown")
		def sub_expired():
			return subscribe < now_msk()
		def bot_off():
			return bot_status == 0

		# РЎРїРёСЃРѕРє РјРµС‚РѕРґРѕРІ С‚СЂРµР±СѓСЋС‰РёС… РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РјР°РЅСѓР°Р»Р°
		METHODS_REQUIRING_CONFIRM = {
			"web_method", "mail_method", "botnet_method", "prem_botnet_method",
			"bot_method", "channel_method", "code_method", "aureport_method",
			"tida_method", "bank_method",
		}

		# в”Ђв”Ђв”Ђ РЁР°Рі 1: РїРѕРєР°Р·С‹РІР°РµРј РїСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ РїСЂРё РЅР°Р¶Р°С‚РёРё РЅР° РјРµС‚РѕРґ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		if d in METHODS_REQUIRING_CONFIRM:
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"вљ пёЏ *РџРµСЂРµРґ СЃР»РµРґСѓСЋС‰РёРј С€Р°РіРѕРј РїСЂРѕС‡С‚РёС‚Рµ РјР°РЅСѓР°Р»\!*\n\n"
					"рџ“„ *РћР·РЅР°РєРѕРјСЊС‚РµСЃСЊ СЃ РїСЂР°РІРёР»Р°РјРё РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ*\n\n"
					"вќЊ *Р—Р° РЅРµРїСЂРѕС‡С‚РµРЅРёРµ \/ РЅРµРїСЂР°РІРёР»СЊРЅС‹Рµ Р¶Р°Р»РѕР±С‹ РІР°Рј РјРѕРіСѓС‚ РѕР±РЅСѓР»РёС‚СЊ РїРѕРґРїРёСЃРєСѓ*"
				),
				parse_mode="MarkdownV2",
				reply_markup=keyboards.manual_confirm_step1(d)
			)
			return

		# в”Ђв”Ђв”Ђ РЁР°Рі 2: "РћР·РЅР°РєРѕРјР»РµРЅ" в†’ РІС‚РѕСЂРѕР№ СЌРєСЂР°РЅ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		if d.startswith('manual_step2_'):
			method = d[len('manual_step2_'):]
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"рџ“„ *Р’С‹ РґРµР№СЃС‚РІРёС‚РµР»СЊРЅРѕ РїСЂРѕС‡РёС‚Р°Р»Рё РјР°РЅСѓР°Р»?*\n\n"
					"*РќР°Р¶РјРёС‚Рµ РєРЅРѕРїРєСѓ РЅРёР¶Рµ С‚РѕР»СЊРєРѕ РµСЃР»Рё РїСЂРѕС‡РёС‚Р°Р»Рё*"
				),
				parse_mode="Markdown",
				reply_markup=keyboards.manual_confirm_step2(method)
			)
			return

		# в”Ђв”Ђв”Ђ РЁР°Рі 3: "100% РїСЂРѕС‡РёС‚Р°Р»" в†’ Р·Р°РїСѓСЃРєР°РµРј РјРµС‚РѕРґ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		if d.startswith('manual_confirm_'):
			d = d[len('manual_confirm_'):]  # РїРѕРґРјРµРЅСЏРµРј d РЅР° СЂРµР°Р»СЊРЅС‹Р№ РјРµС‚РѕРґ

		if d == "web_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РѕРїР»Р°С‚Рё\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0: await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РќСѓР¶РµРЅ РїСЂРµРјРёСѓРј\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_web and (now_msk() - last_used_web[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (now_msk() - last_used_web[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'вќЊ *Р–РґРё {rem.seconds//60} РјРёРЅ {rem.seconds%60} СЃРµРє*', parse_mode="Markdown", reply_markup=back_markup); return
			await call.message.answer("вњ‰пёЏ *Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚:*", parse_mode="Markdown", reply_markup=back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTextFSM.text.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "mail_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РѕРїР»Р°С‚Рё\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_mail and (now_msk() - last_used_mail[uid]) < timedelta(minutes=300):
				rem = timedelta(minutes=300) - (now_msk() - last_used_mail[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'вќЊ *Р–РґРё {rem.seconds//60} РјРёРЅ*', parse_mode="Markdown", reply_markup=back_markup); return
			await call.message.answer("рџ“Њ *Р’РІРµРґРёС‚Рµ С‚РµРјСѓ:*", parse_mode="Markdown", reply_markup=back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitMailTopicFSM.topic.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "botnet_method":
			free_reports = await db.get_free_reports(uid)
			if sub_expired() and free_reports == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РѕРїР»Р°С‚Рё РёР»Рё РїРѕР»СѓС‡Рё Р±РµСЃРїР»Р°С‚РЅС‹Р№ СЂРµРїРѕСЂС‚\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_botnet and (now_msk() - last_used_botnet[uid]) < timedelta(minutes=5):
				rem = timedelta(minutes=5) - (now_msk() - last_used_botnet[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'вќЊ *Р–РґРё {rem.seconds//60} РјРёРЅ {rem.seconds%60} СЃРµРє*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.send_message(call.message.chat.id, '*РЎСЃС‹Р»РєР° РЅР° СЃРѕРѕР±С‰РµРЅРёРµ:*\n`https://t.me/username/123`', parse_mode="Markdown", reply_markup=back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitLinkFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "prem_botnet_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РѕРїР»Р°С‚Рё\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0: await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РќСѓР¶РµРЅ РїСЂРµРјРёСѓРј\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid in last_used_botnet2 and (now_msk() - last_used_botnet2[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (now_msk() - last_used_botnet2[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'вќЊ *Р–РґРё {rem.seconds//60} РјРёРЅ*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.send_message(call.message.chat.id, '*РЎСЃС‹Р»РєР° РЅР° СЃРѕРѕР±С‰РµРЅРёРµ:*\n`https://t.me/username/123`', parse_mode="Markdown", reply_markup=back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitLinkPREMFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		# в”Ђв”Ђв”Ђ Р‘РѕС‚-РјРµС‚РѕРґ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == "bot_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РќСѓР¶РЅР° РїРѕРґРїРёСЃРєР°\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and uid in last_used_bot_snos and (now_msk() - last_used_bot_snos[uid]) < timedelta(hours=1):
				rem = timedelta(hours=1) - (now_msk() - last_used_bot_snos[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=f'вќЊ *Р–РґРё {h}С‡ {m}Рј*', parse_mode="Markdown", reply_markup=back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitBotLinkFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(bot_reason='personal', _bot_token=_instance_token)
			await bot_instance.send_message(
				call.message.chat.id,
				"рџ¤– *Р‘РѕС‚-РјРµС‚РѕРґ*\n\n*в””в”Ђ Р’РІРµРґРёС‚Рµ @username Р±РѕС‚Р°:*\n`@username_bot`\n\n*вљ пёЏ Username РґРѕР»Р¶РµРЅ РѕРєР°РЅС‡РёРІР°С‚СЊСЃСЏ РЅР°* `bot`",
				parse_mode="Markdown", reply_markup=back_markup
			)

		# в”Ђв”Ђв”Ђ РљР°РЅР°Р»-РјРµС‚РѕРґ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == "channel_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			free_reports_ch = await db.get_free_reports(uid)
			if sub_expired() and free_reports_ch == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РѕРїР»Р°С‚Рё РёР»Рё РїРѕР»СѓС‡Рё Р±РµСЃРїР»Р°С‚РЅС‹Р№ СЂРµРїРѕСЂС‚\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption="рџ“ў *РљР°РЅР°Р»-РјРµС‚РѕРґ*\n\n*в””в”Ђ Р’С‹Р±РµСЂРёС‚Рµ РїСЂРёС‡РёРЅСѓ Р¶Р°Р»РѕР±С‹:*",
				parse_mode="Markdown", reply_markup=keyboards.channel_reason_markup
			)

		elif d in ("ch_reason_personal", "ch_reason_spam", "ch_reason_adult", "ch_reason_children", "ch_reason_violence", "ch_reason_other"):
			reason_map = {
				"ch_reason_personal": ("personal", "рџ”ђ РџРµСЂСЃРѕРЅР°Р»СЊРЅС‹Рµ РґР°РЅРЅС‹Рµ"),
				"ch_reason_spam":     ("spam",     "рџ“ў РЎРїР°Рј / РњРѕС€РµРЅРЅРёС‡РµСЃС‚РІРѕ"),
				"ch_reason_adult":    ("adult",    "рџ”ћ 18+ РљРѕРЅС‚РµРЅС‚"),
				"ch_reason_children": ("children", "рџ‘¶ Р”РµС‚СЃРєРёР№ РєРѕРЅС‚РµРЅС‚"),
				"ch_reason_violence": ("violence", "рџ’Ґ РќР°СЃРёР»РёРµ / Р­РєСЃС‚СЂРµРјРёР·Рј"),
				"ch_reason_other":    ("other",    "рџ“ќ РџСЂРѕС‡РµРµ"),
			}
			reason_key, reason_label = reason_map[d]
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitChannelFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(ch_reason=reason_key, _bot_token=_instance_token)
			await bot_instance.send_message(
				call.message.chat.id,
				f"рџ“ў *РџСЂРёС‡РёРЅР°: {reason_label}*\n\n*Р’РІРµРґРёС‚Рµ @username РєР°РЅР°Р»Р° РёР»Рё СЃСЃС‹Р»РєСѓ:*\n`@channel` РёР»Рё `https://t.me/channel`",
				parse_mode="Markdown", reply_markup=back_markup
			)

		# в”Ђв”Ђв”Ђ Р СѓС‡РЅРѕР№ РјРµС‚РѕРґ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == "manual_method":
			manual_markup = types.InlineKeyboardMarkup(row_width=1)
			manual_markup.add(
				types.InlineKeyboardButton("вњЌпёЏ РќР°РїРёСЃР°С‚СЊ @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"рџ‘¤ *Р СѓС‡РЅРѕР№ РјРµС‚РѕРґ*\n\n"
					"*в””в”Ђ Р­С‚Рѕ РјРµС‚РѕРґ СЂСѓС‡РЅРѕРіРѕ СЃРЅРѕСЃР° С‡РµСЂРµР· Р°РґРјРёРЅРёСЃС‚СЂР°С†РёСЋ*\n\n"
					">*Р СѓС‡РЅРѕР№ РјРµС‚РѕРґ вЂ” СЃРЅРѕСЃ РІСЂСѓС‡РЅСѓСЋ РЅР°С€РёРјРё СЃРїРµС†РёР°Р»РёСЃС‚Р°РјРё\.*\n"
					">*РќР°РїРёС€РёС‚Рµ @TariSmit, СѓРєР°Р¶РёС‚Рµ СЋР·РµСЂРЅРµР№Рј С†РµР»Рё Рё СѓР·РЅР°Р№С‚Рµ С†РµРЅСѓ\.*\n\n"
					"*вљ пёЏ Р Р°Р±РѕС‚Р°РµРј С‚РѕР»СЊРєРѕ РїРѕ РїСЂРµРґРѕРїР»Р°С‚Рµ\.*"
				),
				parse_mode="MarkdownV2",
				reply_markup=manual_markup
			)

		# в”Ђв”Ђв”Ђ AU Report в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == "aureport_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РќСѓР¶РЅР° РїРѕРґРїРёСЃРєР°\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and uid in last_used_aureport and (now_msk() - last_used_aureport[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (now_msk() - last_used_aureport[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=f'вќЊ *Р–РґРё {rem.seconds//60} РјРёРЅ {rem.seconds%60} СЃРµРє*', parse_mode="Markdown", reply_markup=back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitAuReportFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"рџ‡¦рџ‡є *AU Report*\n\n"
					"*в””в”Ђ Р’РІРµРґРёС‚Рµ @username РёР»Рё СЃСЃС‹Р»РєСѓ РЅР° С†РµР»СЊ:*\n\n"
					"`@username` РёР»Рё `https://t.me/username`"
				),
				parse_mode="Markdown", reply_markup=back_markup
			)

		# в”Ђв”Ђв”Ђ TIDA в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == "tida_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РќСѓР¶РЅР° РїРѕРґРїРёСЃРєР°\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and uid in last_used_tida and (now_msk() - last_used_tida[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (now_msk() - last_used_tida[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=f'вќЊ *Р–РґРё {rem.seconds//60} РјРёРЅ {rem.seconds%60} СЃРµРє*', parse_mode="Markdown", reply_markup=back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTidaFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"рџџЈ *TIDA*\n\n"
					"*в””в”Ђ Р’РІРµРґРёС‚Рµ @username РёР»Рё СЃСЃС‹Р»РєСѓ РЅР° С†РµР»СЊ:*\n\n"
					"`@username` РёР»Рё `https://t.me/username`"
				),
				parse_mode="Markdown", reply_markup=back_markup
			)

		# в”Ђв”Ђв”Ђ Р‘Р»РѕРєРёСЂРѕРІРєР° РєР°СЂС‚С‹ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == "bank_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if premium == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РќСѓР¶РµРЅ Premium\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if uid not in admins and uid in last_used_bank and (now_msk() - last_used_bank[uid]) < timedelta(hours=12):
				rem = timedelta(hours=12) - (now_msk() - last_used_bank[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=f'вќЊ *РљСѓР»РґР°СѓРЅ: {h}С‡ {m}Рј*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"рџЏ¦ *Р‘Р»РѕРєРёСЂРѕРІРєР° РєР°СЂС‚С‹ РїРѕ 115-Р¤Р—*\n\n"
					"*в””в”Ђ Р’С‹Р±РµСЂРёС‚Рµ Р±Р°РЅРє:*"
				),
				parse_mode="Markdown", reply_markup=keyboards.bank_select_markup
			)

		elif d in ("bank_tbank", "bank_alfa", "bank_sber", "bank_ozon"):
			bank_key = d.replace("bank_", "")
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitBankFSM.card.state)
			await dp_instance.current_state(user=uid).update_data(bank_key=bank_key, _bot_token=_instance_token)
			bank_names = {"tbank": "Рў-Р‘Р°РЅРє", "alfa": "РђР»СЊС„Р°-Р‘Р°РЅРє", "sber": "РЎР±РµСЂ Р‘Р°РЅРє", "ozon": "РћР·РѕРЅ Р‘Р°РЅРє"}
			await bot_instance.send_message(
				call.message.chat.id,
				f"рџЏ¦ *{bank_names[bank_key]}*\n\n"
				f"*в””в”Ђ Р’РІРµРґРёС‚Рµ РЅРѕРјРµСЂ С‚РµР»РµС„РѕРЅР° РёР»Рё РєР°СЂС‚С‹ С†РµР»Рё:*\n\n"
				f"`+79991234567` РёР»Рё `4276 1234 5678 9012`",
				parse_mode="Markdown", reply_markup=back_markup
			)

		# в”Ђв”Ђв”Ђ РљРѕРґ-РјРµС‚РѕРґ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == "code_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РќСѓР¶РЅР° РїРѕРґРїРёСЃРєР°\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitPhoneFSM.phone.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption="рџ“± *РљРѕРґ-РјРµС‚РѕРґ*\n\n*в””в”Ђ Р’РІРµРґРёС‚Рµ РЅРѕРјРµСЂ С‚РµР»РµС„РѕРЅР° С†РµР»Рё:*\n`+79991234567`",
				parse_mode="Markdown", reply_markup=back_markup
			)

		# в”Ђв”Ђв”Ђ РЎС‚СЂРµСЃСЃРµСЂ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
		elif d == "stress_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *Р‘РѕС‚ РІС‹РєР»СЋС‡РµРЅ\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">вќЊ *РѕРїР»Р°С‚Рё\!*", parse_mode="MarkdownV2", reply_markup=back_markup); return
			# РљР” 2 С‡Р°СЃР° (РєСЂРѕРјРµ Р°РґРјРёРЅРѕРІ)
			if uid not in admins and uid in last_used_stress and (now_msk() - last_used_stress[uid]) < timedelta(hours=2):
				rem = timedelta(hours=2) - (now_msk() - last_used_stress[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=f'вќЊ *Р–РґРё {h}С‡ {m}Рј*', parse_mode="Markdown", reply_markup=back_markup); return
			await bot_instance.send_message(
				call.message.chat.id,
				"вљЎпёЏ *РЎС‚СЂРµСЃСЃРµСЂ*\n\n*в””в”Ђ Р’РІРµРґРёС‚Рµ @username Р±РѕС‚Р° РёР»Рё СЃСЃС‹Р»РєСѓ:*\n`@username` РёР»Рё `https://t.me/botname`",
				parse_mode="Markdown"
			)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitStressFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

	except Exception as e:
		print(f"callback_inline: {e}")

# в”Ђв”Ђв”Ђ FSM С…РµРЅРґР»РµСЂС‹ в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.message_handler(state=WaitTextFSM.text)
async def send_web_reports(message: types.Message, state: FSMContext):
	fsm_data = await state.get_data()
	await state.finish()
	uid = message.from_user.id
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	username = message.from_user.username or "Р±РµР· username"
	log_path = generate_log_filename()
	async with aiohttp.ClientSession() as session:
		success, error = await web(session=session, message_text=message.text,
			count=report_count333, log_path=log_path, user_id=uid, username=username)
	# РљР” СЃС‚Р°РІРёРј С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ Р·Р°РІРµСЂС€РµРЅРёСЏ РѕС‚РїСЂР°РІРєРё
	last_used_web[uid] = now_msk()
	try:
		await _bot.send_document(uid, types.InputFile(log_path),
			caption=f"вљ™пёЏ *Р’РµР±*\nрџџў *РЈСЃРїРµС€РЅРѕ: {success}*\nрџ”ґ *РќРµ СѓРґР°Р»РѕСЃСЊ: {error}*",
			reply_markup=main_menu, parse_mode="Markdown")
	except Exception: pass
	try:
		await bot.send_document(bot_logs, types.InputFile(log_path),
			caption=f"рџ“€ *Р’РµР±*\nрџџў {success}\nрџ”ґ {error}\nрџ‘¤ {uid} (@{username})", parse_mode="Markdown")
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
	# РљР” СЃС‚Р°РІРёРј С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ СЂРµР°Р»СЊРЅРѕР№ РѕС‚РїСЂР°РІРєРё РІ start_bulk_email
	await message.answer("вњ‰пёЏ *Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚ РїРёСЃСЊРјР°:*", parse_mode="Markdown")
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
		await message.answer("вќЊ *РќРµС‚ РїРѕС‡С‚!*", parse_mode="Markdown"); return
	receiver_emails = ["dmca@telegram.org","support@telegram.org","abuse@telegram.org","stopCA@telegram.org"]
	success, error, log_path = await send_bulk_emails(
		subject, message.text, mails, receiver_emails,
		user_id=message.from_user.id, username=message.from_user.username or "None",
		bot=_bot, chat_id=message.from_user.id)
	# РљР” СЃС‚Р°РІРёРј С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ СЂРµР°Р»СЊРЅРѕРіРѕ Р·Р°РІРµСЂС€РµРЅРёСЏ РѕС‚РїСЂР°РІРєРё
	last_used_mail[message.from_user.id] = now_msk()
	try:
		await _bot.send_document(message.from_user.id, types.InputFile(log_path),
			caption=f"вљ™пёЏ *РџРѕС‡С‚С‹*\nрџџў {success}\nрџ”ґ {error}", parse_mode="Markdown", reply_markup=main_menu)
		await bot.send_document(bot_logs, types.InputFile(log_path),
			caption=f"рџ“€ *РџРѕС‡С‚С‹*\nрџџў {success}\nрџ”ґ {error}\nрџ‘¤ {message.from_user.id}", parse_mode="Markdown")
	except Exception as e: print(e)
	try: os.remove(log_path)
	except Exception: pass
	# Р—Р°РєСЂС‹РІР°РµРј РІСЂРµРјРµРЅРЅСѓСЋ СЃРµСЃСЃРёСЋ Р·РµСЂРєР°Р»СЊРЅРѕРіРѕ Р±РѕС‚Р°
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
			await _bot.send_message(uid, 'вќЊ *РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ, РЅР°РїРёС€РёС‚Рµ /start*', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
			return
		subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
		if subscribe < now_msk():
			used = await db.use_free_report(uid)
			if not used:
				await _bot.send_message(uid, 'вќЊ *РќРµС‚ РїРѕРґРїРёСЃРєРё Рё Р±РµСЃРїР»Р°С‚РЅС‹С… СЂРµРїРѕСЂС‚РѕРІ!*', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
				return
			free_left = await db.get_free_reports(uid)
			await _bot.send_message(uid, f'рџЋЇ *РСЃРїРѕР»СЊР·РѕРІР°РЅ Р±РµСЃРїР»Р°С‚РЅС‹Р№ СЂРµРїРѕСЂС‚! РћСЃС‚Р°Р»РѕСЃСЊ: {free_left}*', parse_mode=ParseMode.MARKDOWN)
		await _bot.send_message(uid, 'рџ“¤ *Р—Р°РїСѓСЃС‚РёР» РѕС‚РїСЂР°РІРєСѓ...*', parse_mode=ParseMode.MARKDOWN)
		botnet_set_bot(_bot)
		await botnet_main(chat_username, message_id, uid, username, url)
		# РљР” С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕРіРѕ Р·Р°РїСѓСЃРєР°
		last_used_botnet[uid] = now_msk()
	except ValueError:
		await _bot.send_message(uid, '*в­•пёЏ РќРµРІРµСЂРЅР°СЏ СЃСЃС‹Р»РєР°!*', parse_mode=ParseMode.MARKDOWN)
	except Exception as e:
		print(f"[BOTNET] РљР РРўРР§Р•РЎРљРђРЇ РћРЁРР‘РљРђ: {e}", flush=True)
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР° Р±РѕС‚РЅРµС‚Р°:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
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
		await _bot.send_message(uid, 'рџ‘‘ *Р—Р°РїСѓСЃС‚РёР» РѕС‚РїСЂР°РІРєСѓ...*', parse_mode=ParseMode.MARKDOWN)
		botnet_set_bot2(_bot)
		await botnet_main2(chat_username, message_id, uid, username, url)
		# РљР” С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕРіРѕ Р·Р°РїСѓСЃРєР°
		last_used_botnet2[uid] = now_msk()
	except ValueError:
		await _bot.send_message(uid, '*в­•пёЏ РќРµРІРµСЂРЅР°СЏ СЃСЃС‹Р»РєР°!*', parse_mode=ParseMode.MARKDOWN)
	except Exception as e:
		print(f"[PREM] РљР РРўРР§Р•РЎРљРђРЇ РћРЁРР‘РљРђ: {e}", flush=True)
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР° РїСЂРµРјРёСѓРј-Р±РѕС‚РЅРµС‚Р°:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
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

	# Р•СЃР»Рё РїСЂРёСЃР»Р°Р»Рё РєРѕРјР°РЅРґСѓ вЂ” РѕС‚РјРµРЅСЏРµРј FSM
	if token.startswith('/'):
		await state.finish()
		await bot.send_message(uid, "вќЊ *Р’РІРѕРґ С‚РѕРєРµРЅР° РѕС‚РјРµРЅС‘РЅ.*", parse_mode="Markdown", reply_markup=main_menu)
		return

	# Р‘Р°Р·РѕРІР°СЏ РїСЂРѕРІРµСЂРєР° С„РѕСЂРјР°С‚Р° С‚РѕРєРµРЅР°
	if ':' not in token or len(token) < 30:
		await state.finish()
		await bot.send_message(uid, "вќЊ *РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ С‚РѕРєРµРЅР°!*\n*РџСЂРёРјРµСЂ:* `1234567890:ABCdef...`", parse_mode="Markdown")
		return

	await state.finish()

	# РџСЂРѕРІРµСЂСЏРµРј РЅРµ СЃРґР°РЅ Р»Рё С‚РѕРєРµРЅ СѓР¶Рµ
	if await db.token_exists(token):
		await bot.send_message(uid, "вќЊ *Р­С‚РѕС‚ С‚РѕРєРµРЅ СѓР¶Рµ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ!*", parse_mode="Markdown")
		return

	# РџСЂРѕРІРµСЂСЏРµРј С‚РѕРєРµРЅ С‡РµСЂРµР· getMe
	wait_msg = await bot.send_message(uid, "вЏі *РџСЂРѕРІРµСЂСЏРµРј С‚РѕРєРµРЅ...*", parse_mode="Markdown")
	bot_username_new = await validate_token(token)
	try:
		await bot.delete_message(uid, wait_msg.message_id)
	except Exception:
		pass

	if not bot_username_new:
		await bot.send_message(uid, "вќЊ *РўРѕРєРµРЅ РЅРµРІР°Р»РёРґРЅС‹Р№ РёР»Рё Р±РѕС‚ РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚!*\n*РџСЂРѕРІРµСЂСЊ Рё РїРѕРїСЂРѕР±СѓР№ СЃРЅРѕРІР°.*", parse_mode="Markdown")
		return

	# РЎРѕС…СЂР°РЅСЏРµРј Рё Р·Р°РїСѓСЃРєР°РµРј Р·РµСЂРєР°Р»Рѕ
	await db.add_mirror(uid, token, bot_username_new)
	await start_mirror(token)

	# Р‘РѕРЅСѓСЃ +1 СЂРµРїРѕСЂС‚ РїСЂРё СЃРѕР·РґР°РЅРёРё 2-РіРѕ Р·РµСЂРєР°Р»Р° вЂ” С‚РѕР»СЊРєРѕ 1 СЂР°Р·
	mirror_count = await db.count_user_mirrors(uid)
	bonus_msg = ""
	if mirror_count >= 2 and not await db.get_mirror_bonus_given(uid):
		await db.add_free_reports(uid, 1)
		await db.set_mirror_bonus_given(uid)
		bonus_msg = "\nрџЋЇ *Р‘РѕРЅСѓСЃ: +1 Р±РµСЃРїР»Р°С‚РЅС‹Р№ СЂРµРїРѕСЂС‚ Р·Р° 2 Р·РµСЂРєР°Р»Р°!*"

	await bot.send_message(
		uid,
		f"вњ… *Р—РµСЂРєР°Р»Рѕ СЃРѕР·РґР°РЅРѕ!*\n\n"
		f"рџ¤– *Р‘РѕС‚:* `{bot_username_new}`\n"
		f"рџ“Љ *Р’СЃРµРіРѕ Р·РµСЂРєР°Р»: {mirror_count}*"
		f"{bonus_msg}",
		parse_mode="Markdown", reply_markup=main_menu
	)
	await bot.send_message(
		bot_logs,
		f"рџЄћ *РќРѕРІРѕРµ Р·РµСЂРєР°Р»Рѕ*\n"
		f"*в””в”Ђ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ:* `{uid}`\n"
		f"*в””в”Ђ Р‘РѕС‚:* `{bot_username_new}`\n"
		f"*в””в”Ђ Р’СЃРµРіРѕ Р·РµСЂРєР°Р»:* `{mirror_count}`",
		parse_mode="Markdown"
	)

@dp.message_handler(state=WaitBotLinkFSM.link)
async def bot_snos_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()

	# РЎРЅР°С‡Р°Р»Р° С‡РёС‚Р°РµРј fsm_data С‡С‚РѕР±С‹ _bot Р±С‹Р» РґРѕСЃС‚СѓРїРµРЅ РґР»СЏ СЃРѕРѕР±С‰РµРЅРёР№ РѕР± РѕС€РёР±РєР°С…
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	user_data = await db.get_user(uid)
	if not user_data:
		await state.finish()
		await _bot.send_message(uid, 'вќЊ *РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ, РЅР°РїРёС€РёС‚Рµ /start*', parse_mode="Markdown", reply_markup=main_menu)
		return
	subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")

	if uid not in admins and subscribe < now_msk():
		await state.finish()
		await _bot.send_message(uid, ">вќЊ *РѕРїР»Р°С‚Рё\!*", parse_mode="MarkdownV2", reply_markup=main_menu)
		return
	if uid not in admins and uid in last_used_bot_snos and (now_msk() - last_used_bot_snos[uid]) < timedelta(hours=1):
		rem = timedelta(hours=1) - (now_msk() - last_used_bot_snos[uid])
		h = rem.seconds // 3600
		m = (rem.seconds % 3600) // 60
		await state.finish()
		await _bot.send_message(uid, f'вќЊ *Р–РґРё {h}С‡ {m}Рј*', parse_mode="Markdown", reply_markup=main_menu)
		return

	if raw.startswith("https://t.me/"):
		bot_target = "@" + raw.replace("https://t.me/", "").split("/")[0].split("?")[0]
	elif raw.startswith("t.me/"):
		bot_target = "@" + raw.replace("t.me/", "").split("/")[0].split("?")[0]
	elif raw.startswith("@"):
		bot_target = raw.split("/")[0]
	else:
		bot_target = "@" + raw.split("/")[0].split("?")[0]

	# РџСЂРѕРІРµСЂСЏРµРј С‡С‚Рѕ СЌС‚Рѕ Р±РѕС‚ (username РґРѕР»Р¶РµРЅ РѕРєР°РЅС‡РёРІР°С‚СЊСЃСЏ РЅР° 'bot')
	if not bot_target.lower().endswith("bot"):
		await state.finish()
		await _bot.send_message(uid,
			"вќЊ *Р­С‚Рѕ РЅРµ Р±РѕС‚!*\n\n"
			"*Р‘РѕС‚-РјРµС‚РѕРґ СЂР°Р±РѕС‚Р°РµС‚ С‚РѕР»СЊРєРѕ СЃ Р±РѕС‚Р°РјРё.*\n"
			"*Username Р±РѕС‚Р° РґРѕР»Р¶РµРЅ РѕРєР°РЅС‡РёРІР°С‚СЊСЃСЏ РЅР°* `bot`\n"
			"*РџСЂРёРјРµСЂ:* `@example_bot`",
			parse_mode="Markdown", reply_markup=main_menu)
		return

	reason_key = fsm_data.get('bot_reason', 'other')
	await state.finish()

	last_used_bot_snos[uid] = now_msk()
	await _bot.send_message(uid, f'рџ¤– *Р—Р°РїСѓСЃС‚РёР» Р¶Р°Р»РѕР±С‹ РЅР° {bot_target}...*', parse_mode=ParseMode.MARKDOWN)

	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	try:
		set_bot_snos(_bot)
		await main_bot_snos(bot_target, reason_key, uid, username, bot_target)
	except Exception as e:
		import traceback
		print(f"[BOT-SNOS] РљР РРўРР§Р•РЎРљРђРЇ РћРЁРР‘РљРђ: {e}", flush=True)
		traceback.print_exc()
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР° Р±РѕС‚-РјРµС‚РѕРґР°:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
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

	# РќРѕСЂРјР°Р»РёР·СѓРµРј username РєР°РЅР°Р»Р° Рё РёР·РІР»РµРєР°РµРј message_id РµСЃР»Рё РµСЃС‚СЊ
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

	# РљР” 30 РјРёРЅСѓС‚
	if uid not in admins and uid in last_used_channel and (now_msk() - last_used_channel[uid]) < timedelta(minutes=30):
		rem = timedelta(minutes=30) - (now_msk() - last_used_channel[uid])
		await _bot.send_message(uid, f'вќЊ *Р–РґРё {rem.seconds//60} РјРёРЅ {rem.seconds%60} СЃРµРє*', parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	last_used_channel[uid] = now_msk()
	msg_info = f" (СЃРѕРѕР±С‰РµРЅРёРµ #{message_id})" if message_id else ""
	await _bot.send_message(uid, f'рџ“ў *Р—Р°РїСѓСЃС‚РёР» Р¶Р°Р»РѕР±С‹ РЅР° РєР°РЅР°Р» {ch_target}{msg_info}...*', parse_mode="Markdown")

	try:
		set_bot_channel(_bot)
		await main_channel_snos(ch_target, reason_key, uid, username, message_id=message_id)
	except Exception as e:
		print(f"[CH-SNOS] РљР РРўРР§Р•РЎРљРђРЇ РћРЁРР‘РљРђ: {e}", flush=True)
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР° РєР°РЅР°Р»-РјРµС‚РѕРґР°:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
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

	# Р’Р°Р»РёРґР°С†РёСЏ РЅРѕРјРµСЂР°
	phone = raw if raw.startswith("+") else "+" + raw
	if len(phone) < 8 or not phone[1:].isdigit():
		await _bot.send_message(uid,
			"вќЊ *РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ РЅРѕРјРµСЂР°!*\n*РџСЂРёРјРµСЂ:* `+79991234567`",
			parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	# РљР” 30 РјРёРЅСѓС‚
	if uid not in admins and uid in last_used_channel and (now_msk() - last_used_channel[uid]) < timedelta(minutes=30):
		rem = timedelta(minutes=30) - (now_msk() - last_used_channel[uid])
		await _bot.send_message(uid, f'вќЊ *Р–РґРё {rem.seconds//60} РјРёРЅ {rem.seconds%60} СЃРµРє*', parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	last_used_channel[uid] = now_msk()
	await _bot.send_message(uid,
		f'рџ“± *Р—Р°РїСѓСЃРєР°СЋ РєРѕРґ-РјРµС‚РѕРґ РЅР°* `{phone}`*...*\n*в””в”Ђ РћС‚РїСЂР°РІР»СЏРµРј 25 РєРѕРґРѕРІ*',
		parse_mode="Markdown")

	try:
		from code_snos import set_bot_code as _set_code
		_set_code(_bot)
		await main_code_snos(phone, uid, username)
	except Exception as e:
		print(f"[CODE] РљР РРўРР§Р•РЎРљРђРЇ РћРЁРР‘РљРђ: {e}", flush=True)
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР° РєРѕРґ-РјРµС‚РѕРґР°:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
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

	# Р’Р°Р»РёРґР°С†РёСЏ вЂ” РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ username РёР»Рё СЃСЃС‹Р»РєР°
	if not raw.startswith("@") and not raw.startswith("https://t.me/") and not raw.startswith("t.me/"):
		raw = "@" + raw

	if uid not in admins:
		last_used_aureport[uid] = now_msk()

	await _bot.send_message(uid,
		f'рџ‡¦рџ‡є *Р—Р°РїСѓСЃРєР°СЋ AU Report РЅР°* `{raw}`*...*\n*в””в”Ђ Р­С‚Рѕ РјРѕР¶РµС‚ Р·Р°РЅСЏС‚СЊ РЅРµРєРѕС‚РѕСЂРѕРµ РІСЂРµРјСЏ*',
		parse_mode="Markdown")

	try:
		set_bot_aureport(_bot)
		await main_aureport(raw, uid, username)
	except Exception as e:
		print(f"[AUREPORT] РљР РРўРР§Р•РЎРљРђРЇ РћРЁРР‘РљРђ: {e}", flush=True)
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР° AU Report:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
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
		f'рџџЈ *TIDA*\n\n*Р¦РµР»СЊ:* `{raw}`\n\n*Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚ Р¶Р°Р»РѕР±С‹:*\n_(РћРїРёС€РёС‚Рµ РЅР°СЂСѓС€РµРЅРёРµ РЅР° Р°РЅРіР»РёР№СЃРєРѕРј СЏР·С‹РєРµ)_\n\n[рџ“‹ РЁР°Р±Р»РѕРЅС‹ С‚РµРєСЃС‚РѕРІ](https://t.me/+zTWywoULseYzMWU0)',
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
		await _bot.send_message(uid, "вќЊ *РўРµРєСЃС‚ СЃР»РёС€РєРѕРј РєРѕСЂРѕС‚РєРёР№! РњРёРЅРёРјСѓРј 10 СЃРёРјРІРѕР»РѕРІ.*", parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	if uid not in admins:
		last_used_tida[uid] = now_msk()

	await _bot.send_message(uid,
		f'рџџЈ *Р—Р°РїСѓСЃРєР°СЋ TIDA РЅР°* `{target_link}`*...*\n*в””в”Ђ Р­С‚Рѕ РјРѕР¶РµС‚ Р·Р°РЅСЏС‚СЊ РЅРµРєРѕС‚РѕСЂРѕРµ РІСЂРµРјСЏ*',
		parse_mode="Markdown")

	try:
		set_bot_tida(_bot)
		await main_tida(target_link, custom_text, uid, username)
	except Exception as e:
		print(f"[TIDA] РљР РРўРР§Р•РЎРљРђРЇ РћРЁРР‘РљРђ: {e}", flush=True)
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР° TIDA:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
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
		await _bot.send_message(uid, "вќЊ *Р’РІРµРґРёС‚Рµ РєРѕСЂСЂРµРєС‚РЅС‹Р№ РЅРѕРјРµСЂ С‚РµР»РµС„РѕРЅР° РёР»Рё РєР°СЂС‚С‹!*", parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	if uid not in admins:
		last_used_bank[uid] = now_msk()

	try:
		set_bot_bank(_bot)
		await process_bank_report(bank_key, card_data, uid, username)
	except Exception as e:
		print(f"[BANK] РљР РРўРР§Р•РЎРљРђРЇ РћРЁРР‘РљРђ: {e}", flush=True)
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР°:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
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

	# РќРѕСЂРјР°Р»РёР·СѓРµРј username
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
		await _bot.send_message(uid, 'вќЊ *РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ, РЅР°РїРёС€РёС‚Рµ /start*', parse_mode="Markdown", reply_markup=main_menu)
		return
	subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")

	# РџСЂРѕРІРµСЂСЏРµРј РїРѕРґРїРёСЃРєСѓ вЂ” СЃС‚СЂРµСЃСЃРµСЂ С‚РѕР»СЊРєРѕ СЃ РїРѕРґРїРёСЃРєРѕР№, Р±РµСЃРїР»Р°С‚РЅС‹Рµ СЂРµРїРѕСЂС‚С‹ РЅРµ С‚СЂР°С‚РёРј
	if not is_admin and subscribe < now_msk():
		await _bot.send_message(uid, 'вќЊ *РќСѓР¶РЅР° РїРѕРґРїРёСЃРєР° РґР»СЏ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ СЃС‚СЂРµСЃСЃРµСЂР°!*', parse_mode="Markdown", reply_markup=main_menu)
		return

	await _bot.send_message(uid, f'вљЎпёЏ *Р—Р°РїСѓСЃРєР°РµРј СЃС‚СЂРµСЃСЃРµСЂ РЅР° {bot_target}...*', parse_mode="Markdown")
	set_bot_stress(_bot)

	try:
		started = await main_bot_stress(bot_target, uid, username, is_admin)
		# РљР” С‚РѕР»СЊРєРѕ РµСЃР»Рё Р°С‚Р°РєР° СѓСЃРїРµС€РЅРѕ Р·Р°РїСѓСЃС‚РёР»Р°СЃСЊ (РЅР°С€Р»РёСЃСЊ РєРЅРѕРїРєРё)
		if started and not is_admin:
			last_used_stress[uid] = now_msk()
	except Exception as e:
		print(f"[STRESS] РћРЁРР‘РљРђ: {e}", flush=True)
		import traceback
		traceback.print_exc()
		await _bot.send_message(uid, f'вќЊ *РћС€РёР±РєР° СЃС‚СЂРµСЃСЃРµСЂР°:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		set_bot_stress(bot)
		if _is_mirror_bot:
			try:
				session = await _bot.get_session()
				await session.close()
			except Exception:
				pass

# в”Ђв”Ђв”Ђ РЈРїСЂР°РІР»РµРЅРёРµ РїРѕРґРїРёСЃРєР°РјРё (Р°РґРјРёРЅ) в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.message_handler(state=AddSubscribeFSM.user_id)
async def add_sub_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ РІ Р±Р°Р·Рµ.", parse_mode="Markdown")
			await state.finish()
			return
		await state.update_data(user_id=target)
		await message.answer(f"рџЋ± *ID РЅР°Р№РґРµРЅ:* `{target}`\n*Р’РІРµРґРёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№:*", parse_mode=ParseMode.MARKDOWN)
		await AddSubscribeFSM.days.set()
	except Exception:
		await message.answer("вќЊ РћС€РёР±РєР°."); await state.finish()

@dp.message_handler(state=AddSubscribeFSM.days)
async def add_sub_days(message: types.Message, state: FSMContext):
	try:
		data = await state.get_data()
		target = data['user_id']
		new_date = (now_msk() + timedelta(days=int(message.text))).strftime("%Y-%m-%d %H:%M:%S")
		await db.set_subscribe(target, new_date)
		await state.finish()
		try:
			await bot.send_message(target, f"рџЋ± *РџРѕРґРїРёСЃРєР° РѕР±РЅРѕРІР»РµРЅР° РґРѕ* `{new_date}`", parse_mode="Markdown", reply_markup=del_message2)
		except Exception:
			pass
		await message.answer(f"рџЋ± *Р“РѕС‚РѕРІРѕ! РџРѕРґРїРёСЃРєР° РІС‹РґР°РЅР°* `{target}` *РґРѕ* `{new_date}`", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"рџЋ± *Р’С‹РґР°РЅР° РїРѕРґРїРёСЃРєР°* `{target}` РґРѕ `{new_date}`", parse_mode="Markdown")
	except ValueError:
		await message.answer("вќЊ Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ РґРЅРµР№ (РЅР°РїСЂРёРјРµСЂ: 7).")
	except Exception as e:
		await message.answer(f"вќЊ РћС€РёР±РєР°: `{str(e)[:100]}`", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=ClearSubscribeFSM.user_id)
async def clear_sub_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ.", parse_mode="Markdown"); await state.finish(); return
		await db.set_subscribe(target, "1999-01-01 00:00:00", force=True)
		await state.finish()
		await bot.send_message(target, "*рџЋ± РџРѕРґРїРёСЃРєР° СЃР±СЂРѕС€РµРЅР°.*", parse_mode="Markdown", reply_markup=del_message2)
		await message.answer(f"*рџЋ± РЎР±СЂРѕС€РµРЅРѕ Сѓ* `{target}`*!*", parse_mode="Markdown")
	except Exception:
		await message.answer("вќЊ РћС€РёР±РєР°."); await state.finish()

@dp.message_handler(state=AddPremFSM.user_id)
async def add_prem_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ.", parse_mode="Markdown"); await state.finish(); return
		await db.set_premium(target, 1)
		await state.finish()
		try:
			await bot.send_message(target, "*рџ‘‘ Р’Р°Рј РІС‹РґР°РЅ Premium.*", parse_mode="Markdown", reply_markup=del_message2)
		except Exception:
			pass
		await message.answer(f"*рџЋ± РџСЂРµРјРёСѓРј РІС‹РґР°РЅ* `{target}`*!*", parse_mode="Markdown")
	except Exception as e:
		await message.answer(f"вќЊ РћС€РёР±РєР°: `{str(e)[:100]}`", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=ClearPremFSM.user_id)
async def clear_prem_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ.", parse_mode="Markdown"); await state.finish(); return
		await db.set_premium(target, 0)
		await state.finish()
		await bot.send_message(target, "*рџЋ± РџСЂРµРјРёСѓРј СЃР±СЂРѕС€РµРЅ.*", parse_mode="Markdown", reply_markup=del_message2)
		await message.answer(f"*рџЋ± РЎР±СЂРѕС€РµРЅРѕ Сѓ* `{target}`*!*", parse_mode="Markdown")
	except Exception:
		await message.answer("вќЊ РћС€РёР±РєР°."); await state.finish()

# в”Ђв”Ђв”Ђ Р Р°СЃСЃС‹Р»РєР° в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.message_handler(state=WaitTextZFSM.text, content_types=types.ContentTypes.ANY)
async def sendall(message: types.Message, state: FSMContext):
	await state.finish()
	users = await db.get_all_user_ids()
	ok, fail = 0, 0

	# Р Р°СЃСЃС‹Р»РєР° С‚РѕР»СЊРєРѕ С‡РµСЂРµР· РѕСЃРЅРѕРІРЅРѕР№ Р±РѕС‚ (РЅРµ С‡РµСЂРµР· Р·РµСЂРєР°Р»Р°)
	for user_id in users:
		try:
			if message.text:
				await bot.send_message(user_id, message.text, parse_mode='Markdown', reply_markup=del_message2)
			elif message.photo:
				await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption, parse_mode='Markdown', reply_markup=del_message2)
			else:
				await bot.send_message(user_id, message.caption or "рџ“ў", parse_mode='Markdown', reply_markup=del_message2)
			ok += 1
		except Exception:
			fail += 1
		await asyncio.sleep(0.05)  # ~20 СЃРѕРѕР±С‰РµРЅРёР№/СЃРµРє, РЅРµ Р»РѕРІРёРј 429

	await message.answer(f'*рџЋ± Р Р°СЃСЃС‹Р»РєР° РѕРєРѕРЅС‡РµРЅР°!*\n*вњ… Р”РѕСЃС‚Р°РІР»РµРЅРѕ:* {ok}\n*вќЊ РќРµ РґРѕСЃС‚Р°РІР»РµРЅРѕ:* {fail}',
		parse_mode='Markdown', reply_markup=main_menu)
	await bot.send_message(bot_logs, f"рџ“ў *Р Р°СЃСЃС‹Р»РєР° Р·Р°РІРµСЂС€РµРЅР°*\n*вњ… {ok} / вќЊ {fail}*", parse_mode='Markdown')

# в”Ђв”Ђв”Ђ РџСЂРѕРјРѕРєРѕРґС‹ (Р°РєС‚РёРІР°С†РёСЏ) в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.message_handler(state=WaitPromoFSM.promo)
async def enter_promo(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	code = message.text.strip()
	await state.finish()

	# РџСЂРѕРІРµСЂСЏРµРј С‡С‚Рѕ РІ РёРјРµРЅРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РµСЃС‚СЊ СѓРїРѕРјРёРЅР°РЅРёРµ Р±РѕС‚Р°
	full_name = (message.from_user.first_name or "") + " " + (message.from_user.last_name or "")
	if "Brrown_V2bot" not in full_name and "Brrown_V2bot" not in (message.from_user.username or ""):
		markup = types.InlineKeyboardMarkup()
		markup.add(types.InlineKeyboardButton("вњ… РџСЂРѕРІРµСЂРёС‚СЊ", callback_data='promo_check_name'))
		await message.answer(
			"*вќЊ Р”Р»СЏ Р°РєС‚РёРІР°С†РёРё РїСЂРѕРјРѕРєРѕРґР° РґРѕР±Р°РІСЊС‚Рµ* `@Brrown_V2bot` *РІ СЃРІРѕС‘ РёРјСЏ РёР»Рё С„Р°РјРёР»РёСЋ РІ Telegram!*\n\n"
			"*РљР°Рє СЌС‚Рѕ СЃРґРµР»Р°С‚СЊ:*\n"
			"*1. Р—Р°Р№РґРё РІ РЅР°СЃС‚СЂРѕР№РєРё Telegram*\n"
			"*2. РР·РјРµРЅРёС‚СЊ РїСЂРѕС„РёР»СЊ в†’ РРјСЏ РёР»Рё Р¤Р°РјРёР»РёСЏ*\n"
			"*3. Р”РѕР±Р°РІСЊ* `@Brrown_V2bot` *Рё СЃРѕС…СЂР°РЅРё*\n\n"
			"*РџРѕСЃР»Рµ РёР·РјРµРЅРµРЅРёСЏ РЅР°Р¶РјРё РєРЅРѕРїРєСѓ РЅРёР¶Рµ:*",
			parse_mode="Markdown",
			reply_markup=markup
		)
		return

	promo_data = await db.get_promo(code)
	if not promo_data or promo_data['activations'] <= 0:
		await message.answer("*вќЊ РџСЂРѕРјРѕРєРѕРґ РЅРµ РЅР°Р№РґРµРЅ РёР»Рё РёСЃС‡РµСЂРїР°РЅ!*", parse_mode='Markdown'); return
	# РџСЂРѕРІРµСЂСЏРµРј вЂ” РЅРµ Р°РєС‚РёРІРёСЂРѕРІР°Р» Р»Рё СЌС‚РѕС‚ СЋР·РµСЂ СѓР¶Рµ СЌС‚РѕС‚ РїСЂРѕРјРѕРєРѕРґ
	if await db.is_promo_used_by(code, uid):
		await message.answer("*вќЊ Р’С‹ СѓР¶Рµ Р°РєС‚РёРІРёСЂРѕРІР°Р»Рё СЌС‚РѕС‚ РїСЂРѕРјРѕРєРѕРґ!*", parse_mode='Markdown'); return
	promo_type = promo_data.get('promo_type', 'normal')
	days = promo_data['days']
	await db.mark_promo_used(code, uid)
	# РЎРЅРёР¶Р°РµРј СЃС‡С‘С‚С‡РёРє Р°РєС‚РёРІР°С†РёР№
	pool = await db.get_pool()
	async with pool.acquire() as conn:
		await conn.execute("UPDATE promocode SET activations = activations - 1 WHERE code = $1", code)
	if promo_type == 'premium':
		await db.set_premium(uid, 1)
		await message.answer(f"*вњ… РџСЂРѕРјРѕРєРѕРґ Р°РєС‚РёРІРёСЂРѕРІР°РЅ!*\n*рџ‘‘ Р’Р°Рј РІС‹РґР°РЅ Premium РЅР°РІСЃРµРіРґР°!*", parse_mode='Markdown')
		await bot.send_message(bot_logs, f"рџЋЃ `{uid}` Р°РєС‚РёРІРёСЂРѕРІР°Р» РїСЂРѕРјРѕРєРѕРґ `{code}` вЂ” рџ‘‘ РџСЂРµРјРёСѓРј", parse_mode='Markdown')
	elif promo_type == 'reports':
		reports_count = days  # РІ РїРѕР»Рµ days С…СЂР°РЅРёС‚СЃСЏ РєРѕР»-РІРѕ СЂРµРїРѕСЂС‚РѕРІ
		await db.add_free_reports(uid, reports_count)
		await message.answer(f"*вњ… РџСЂРѕРјРѕРєРѕРґ Р°РєС‚РёРІРёСЂРѕРІР°РЅ!*\n*рџЋЇ Р’Р°Рј РЅР°С‡РёСЃР»РµРЅРѕ: {reports_count} Р±РµСЃРїР»Р°С‚РЅС‹С… СЂРµРїРѕСЂС‚РѕРІ!*", parse_mode='Markdown')
		await bot.send_message(bot_logs, f"рџЋЃ `{uid}` Р°РєС‚РёРІРёСЂРѕРІР°Р» РїСЂРѕРјРѕРєРѕРґ `{code}` вЂ” рџЋЇ {reports_count} СЂРµРїРѕСЂС‚РѕРІ", parse_mode='Markdown')
	else:
		new_date = (now_msk() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
		await db.set_subscribe(uid, new_date)
		await message.answer(f"*вњ… РџСЂРѕРјРѕРєРѕРґ Р°РєС‚РёРІРёСЂРѕРІР°РЅ!*\n*Р’Р°С€ РїРѕРґР°СЂРѕРє: {days} РґРЅРµР№!*", parse_mode='Markdown')
		await bot.send_message(bot_logs, f"рџЋЃ `{uid}` Р°РєС‚РёРІРёСЂРѕРІР°Р» РїСЂРѕРјРѕРєРѕРґ `{code}` вЂ” {days} РґРЅРµР№", parse_mode='Markdown')

# в”Ђв”Ђв”Ђ Р‘Р»РѕРєРёСЂРѕРІРєР°/СЂР°Р·Р±Р»РѕРєРёСЂРѕРІРєР° (Р°РґРјРёРЅ) в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

@dp.message_handler(state=BlockUserFSM.user_id)
async def admin_block_user(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ.", parse_mode="Markdown"); await state.finish(); return
		await db.block_user(target)
		await state.finish()
		await message.answer(f"рџљ« *РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {target} Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ.*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"рџљ« *Р—Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ* `{target}` *Р°РґРјРёРЅРѕРј* `{message.from_user.id}`", parse_mode="Markdown")
	except Exception:
		await message.answer("вќЊ РћС€РёР±РєР°."); await state.finish()

@dp.message_handler(state=UnblockUserFSM.user_id)
async def admin_unblock_user(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ.", parse_mode="Markdown"); await state.finish(); return
		await db.unblock_user(target)
		await state.finish()
		await message.answer(f"вњ… *РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {target} СЂР°Р·Р±Р»РѕРєРёСЂРѕРІР°РЅ.*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"вњ… *Р Р°Р·Р±Р»РѕРєРёСЂРѕРІР°РЅ* `{target}` *Р°РґРјРёРЅРѕРј* `{message.from_user.id}`", parse_mode="Markdown")
	except Exception:
		await message.answer("вќЊ РћС€РёР±РєР°."); await state.finish()

@dp.message_handler(state=DeleteUserFSM.user_id)
async def admin_delete_user(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ.", parse_mode="Markdown"); await state.finish(); return
		await db.delete_user(target)
		await state.finish()
		await message.answer(f"рџ—‘ *РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {target} СѓРґР°Р»С‘РЅ РёР· Р±Р°Р·С‹.*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"рџ—‘ *РЈРґР°Р»С‘РЅ РёР· Р‘Р”* `{target}` *Р°РґРјРёРЅРѕРј* `{message.from_user.id}`", parse_mode="Markdown")
	except Exception:
		await message.answer("вќЊ РћС€РёР±РєР°."); await state.finish()

@dp.message_handler(state=CreatePromoFSM.code)
async def create_promo_code(message: types.Message, state: FSMContext):
	code = message.text.strip()
	if not code or len(code) < 3:
		await message.answer("вќЊ *РљРѕРґ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РјРёРЅРёРјСѓРј 3 СЃРёРјРІРѕР»Р°. Р’РІРµРґРёС‚Рµ СЃРЅРѕРІР°:*", parse_mode="Markdown")
		return
	await state.update_data(code=code)
	data = await state.get_data()
	promo_type = data.get('promo_type', 'normal')
	if promo_type == 'premium':
		# Р”Р»СЏ РїСЂРµРјРёСѓРјР° РґРЅРё РЅРµ РЅСѓР¶РЅС‹ вЂ” СЃСЂР°Р·Сѓ Рє Р°РєС‚РёРІР°С†РёСЏРј
		await message.answer(f"рџ‘‘ *РљРѕРґ:* `{code}`\n\n*Р’РІРµРґРёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ Р°РєС‚РёРІР°С†РёР№:*", parse_mode="Markdown")
		await CreatePromoFSM.activations.set()
	elif promo_type == 'reports':
		await message.answer(f"рџЋЇ *РљРѕРґ:* `{code}`\n\n*Р’РІРµРґРёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ Р±РµСЃРїР»Р°С‚РЅС‹С… СЂРµРїРѕСЂС‚РѕРІ:*", parse_mode="Markdown")
		await CreatePromoFSM.days.set()
	else:
		await message.answer(f"рџ’Ћ *РљРѕРґ:* `{code}`\n\n*Р’РІРµРґРёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№ РїРѕРґРїРёСЃРєРё:*", parse_mode="Markdown")
		await CreatePromoFSM.days.set()

@dp.message_handler(state=CreatePromoFSM.days)
async def create_promo_days(message: types.Message, state: FSMContext):
	try:
		days = int(message.text.strip())
		if days <= 0:
			raise ValueError
		await state.update_data(days=days)
		await message.answer(f"рџ’Ћ *Р”РЅРµР№:* `{days}`\n\n*Р’РІРµРґРёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ Р°РєС‚РёРІР°С†РёР№:*", parse_mode="Markdown")
		await CreatePromoFSM.activations.set()
	except ValueError:
		await message.answer("вќЊ Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ Р±РѕР»СЊС€Рµ 0.")

@dp.message_handler(state=CreatePromoFSM.activations)
async def create_promo_activations(message: types.Message, state: FSMContext):
	try:
		activations = int(message.text.strip())
		if activations <= 0:
			raise ValueError
		data = await state.get_data()
		code = data['code']
		promo_type = data.get('promo_type', 'normal')
		days = data.get('days', 999)  # РґР»СЏ РїСЂРµРјРёСѓРјР° РґРЅРё РЅРµ РёСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ
		await state.finish()
		try:
			await db.create_promo(code, days, activations, promo_type=promo_type)
			if promo_type == 'premium':
				await message.answer(
					f"вњ… *РџСЂРµРјРёСѓРј РїСЂРѕРјРѕРєРѕРґ СЃРѕР·РґР°РЅ!*\n\n"
					f"рџ‘‘ *РљРѕРґ:* `{code}`\n"
					f"рџ”ў *РђРєС‚РёРІР°С†РёР№:* `{activations}`\n"
					f"*в””в”Ђ Р’С‹РґР°С‘С‚: РџСЂРµРјРёСѓРј РЅР°РІСЃРµРіРґР°*",
					parse_mode="Markdown")
			elif promo_type == 'reports':
				reports_count = days  # РІ РїРѕР»Рµ days С…СЂР°РЅРёС‚СЃСЏ РєРѕР»-РІРѕ СЂРµРїРѕСЂС‚РѕРІ
				await message.answer(
					f"вњ… *РџСЂРѕРјРѕРєРѕРґ РЅР° СЂРµРїРѕСЂС‚С‹ СЃРѕР·РґР°РЅ!*\n\n"
					f"рџЋЇ *РљРѕРґ:* `{code}`\n"
					f"рџЋЇ *Р РµРїРѕСЂС‚РѕРІ:* `{reports_count}`\n"
					f"рџ”ў *РђРєС‚РёРІР°С†РёР№:* `{activations}`",
					parse_mode="Markdown")
			else:
				await message.answer(
					f"вњ… *РџСЂРѕРјРѕРєРѕРґ СЃРѕР·РґР°РЅ!*\n\n"
					f"рџ’Ћ *РљРѕРґ:* `{code}`\n"
					f"рџ“… *Р”РЅРµР№:* `{days}`\n"
					f"рџ”ў *РђРєС‚РёРІР°С†РёР№:* `{activations}`",
					parse_mode="Markdown")
			await bot.send_message(bot_logs,
				f"рџ’Ћ *РЎРѕР·РґР°РЅ РїСЂРѕРјРѕРєРѕРґ* `{code}` ({'рџ‘‘ РџСЂРµРјРёСѓРј' if promo_type == 'premium' else ('рџЋЇ ' + str(days) + ' СЂРµРїРѕСЂС‚РѕРІ') if promo_type == 'reports' else f'рџ“… {days} РґРЅРµР№'}), {activations} Р°РєС‚. *Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂРѕРј* `{message.from_user.id}`",
				parse_mode="Markdown")
		except Exception:
			await message.answer(f"вќ—пёЏ *РџСЂРѕРјРѕРєРѕРґ* `{code}` *СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚!*", parse_mode="Markdown")
	except ValueError:
		await message.answer("вќЊ Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ Р±РѕР»СЊС€Рµ 0.")

@dp.message_handler(state=AdminAddReportsFSM.user_id)
async def admin_add_reports_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ.", parse_mode="Markdown"); await state.finish(); return
		await state.update_data(user_id=target)
		await message.answer(f"рџЋЇ *ID:* `{target}`\n*РЎРєРѕР»СЊРєРѕ СЂРµРїРѕСЂС‚РѕРІ РІС‹РґР°С‚СЊ?*", parse_mode="Markdown")
		await AdminAddReportsFSM.amount.set()
	except ValueError:
		await message.answer("вќЊ РћС€РёР±РєР°.")
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
		await message.answer(f"вњ… *Р’С‹РґР°РЅРѕ {amount} СЂРµРїРѕСЂС‚РѕРІ* `{target}`\n*РС‚РѕРіРѕ: {current}*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"рџЋЇ *+{amount} СЂРµРїРѕСЂС‚РѕРІ* `{target}` *РѕС‚ Р°РґРјРёРЅР°*", parse_mode="Markdown")
		try:
			await bot.send_message(target, f"рџЋЇ *Р’Р°Рј РІС‹РґР°РЅРѕ {amount} Р±РµСЃРїР»Р°С‚РЅС‹С… СЂРµРїРѕСЂС‚РѕРІ!*\n*РС‚РѕРіРѕ: {current}*", parse_mode="Markdown")
		except Exception:
			pass
	except ValueError:
		await message.answer("вќЊ Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ.")
		await state.finish()
	except Exception as e:
		await message.answer(f"вќЊ РћС€РёР±РєР°: `{str(e)[:100]}`", parse_mode="Markdown")
		await state.finish()

@dp.message_handler(state=AdminRemoveReportsFSM.user_id)
async def admin_remove_reports_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ `{raw}` РЅРµ РЅР°Р№РґРµРЅ.", parse_mode="Markdown"); await state.finish(); return
		await state.update_data(user_id=target)
		await message.answer(f"рџЋЇ *ID:* `{target}`\n*РЎРєРѕР»СЊРєРѕ СЂРµРїРѕСЂС‚РѕРІ Р·Р°Р±СЂР°С‚СЊ?*", parse_mode="Markdown")
		await AdminRemoveReportsFSM.amount.set()
	except Exception:
		await message.answer("вќЊ РћС€РёР±РєР°.")
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
		await message.answer(f"вњ… *Р—Р°Р±СЂР°РЅРѕ {amount} СЂРµРїРѕСЂС‚РѕРІ* `{target}`\n*РћСЃС‚Р°Р»РѕСЃСЊ: {new_amount}*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"рџЋЇ *-{amount} СЂРµРїРѕСЂС‚РѕРІ* `{target}` *РѕС‚ Р°РґРјРёРЅР°*", parse_mode="Markdown")
	except ValueError:
		await message.answer("вќЊ Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ.")
		await state.finish()

# в”Ђв”Ђв”Ђ Р—Р°РїСѓСЃРє в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

async def on_startup(dp):
	try:
		print(f"DATABASE_URL = {os.environ.get('DATABASE_URL', 'РќР• РЈРЎРўРђРќРћР’Р›Р•РќРђ')[:50]}")
		await db.init_db()
		print("Р‘Р” РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅР° СѓСЃРїРµС€РЅРѕ.")
	except Exception as e:
		print(f"РћРЁРР‘РљРђ Р‘Р” РїСЂРё СЃС‚Р°СЂС‚Рµ: {e}")
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
	print("Р‘РѕС‚ Р·Р°РїСѓС‰РµРЅ.")

if __name__ == "__main__":
	import sys
	# РћС‚РєР»СЋС‡Р°РµРј Р±СѓС„РµСЂРёР·Р°С†РёСЋ РІС‹РІРѕРґР° вЂ” Р»РѕРіРё СЃСЂР°Р·Сѓ РІРёРґРЅС‹ РІ Railway/РєРѕРЅСЃРѕР»Рё
	sys.stdout.reconfigure(line_buffering=True)
	while True:
		try:
			print("Р‘РѕС‚ Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ...", flush=True)
			executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
		except KeyboardInterrupt:
			exit()
		except Exception as e:
			print(f"РћС€РёР±РєР°: {e}. РџРµСЂРµР·Р°РїСѓСЃРє С‡РµСЂРµР· 10 СЃРµРє...", flush=True)
			time.sleep(10)

