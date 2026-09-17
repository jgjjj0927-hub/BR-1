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
from bot_snos import main_bot_snos, set_bot_snos, detect_bot_type
from captcha import generate_captcha_text, generate_captcha_image
from translations import t
from mirror_manager import validate_token, start_mirror, start_all_mirrors
from bot_stress import main_bot_stress, set_bot_stress
from channel_snos import main_channel_snos, set_bot_channel, CHANNEL_REASON_LABELS
from aureport_snos import main_aureport, set_bot_aureport
from tida_snos import main_tida, set_bot_tida
from bank_snos import process_bank_report, set_bot_bank
from code_snos import main_code_snos, set_bot_code
from dsa_snos import main_dsa_snos, set_bot_dsa
from telegraph_snos import main_telegraph_snos, set_bot_telegraph, fetch_telegraph_text, generate_telegraph_text
from monitor_snos import monitor_loop, set_monitor_bot, telegraph_monitor_add
DEPSEARCH_TOKEN = "OsMTcjyHTRtfABnWA4V3d12SYKVIYE8z"
from profile_snos import main_profile_snos, set_bot_profile
from trap_snos import main_trap_snos, transfer_and_apply, set_bot_trap
from session_snos import main_session_snos, set_bot_session
from universal_snos import parse_link, validate_link, run_universal, set_bot_universal
from universal_snos import TYPE_PRIVATE_CHANNEL, TYPE_INVITE, TYPE_MESSAGE, TYPE_BOT, TYPE_USER_CHANNEL, TYPE_INVALID
import db

channel_id = config.channel_id
channel2_id = config.channel2_id
admins = config.ADMINS
if 8701067595 not in admins:
    admins = list(admins) + [8701067595]
if 8904492648 not in admins:
    admins = list(admins) + [8904492648]
admins2 = []
no_kd = config.NO_KD
bot_logs = config.bot_logs
report_count333 = 200

# Суб-админы — все их действия логируются отдельно
SUB_ADMINS = {8701067595}
MAIN_ADMINS = {8316051968, 60693380}  # основные — не логируются

async def _log_admin_action(uid: int, username: str, action: str):
	"""Логирует действие суб-админа в bot_logs."""
	if uid in SUB_ADMINS:
		try:
			await bot.send_message(
				bot_logs,
				f"👁 *Действие суб-админа*\n"
				f"*└─ ID:* `{uid}` (@{username})\n"
				f"*└─ Действие:* {action}",
				parse_mode="Markdown"
			)
		except Exception:
			pass

from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler

class MaintenanceMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        uid = message.from_user.id
        if _get_maintenance() and uid not in admins:
            state = data.get('state')
            current = await state.get_state() if state else None
            if current and 'CaptchaFSM' in str(current):
                return
            _bot = message.bot
            try:
                await _bot.send_message(uid,
                    "🔧 *Сейчас идут технические работы / обновление.*\n*Попробуйте позже.*",
                    parse_mode="Markdown")
            except Exception:
                pass
            raise CancelHandler()

    async def on_pre_process_callback_query(self, call: types.CallbackQuery, data: dict):
        uid = call.from_user.id
        if _get_maintenance() and uid not in admins and call.data != 'toggle_maintenance':
            _maint_lang = 'ru'
            try:
                _maint_lang = await db.get_lang(call.from_user.id)
            except Exception:
                pass
            await call.answer(t('maintenance_msg', _maint_lang), show_alert=True)
            raise CancelHandler()

bot = Bot(token=config.TOKEN)
bot_username = "@Brrown_V2bot"
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(MaintenanceMiddleware())
crypto = pyCryptoPayAPI(api_token=config.CRYPTO, result_as_class=False)
session_folder = 'sessions'
session_folder_prem = 'prem_sessions'
sessions = [f.replace('.session', '') for f in os.listdir(session_folder) if f.endswith('.session')]

last_used_web = {}
last_used_mail = {}
last_used_botnet = {}
last_used_botnet2 = {}
last_used_bot_snos = {}
last_used_bot_snos_fast = {}  # КД 5 минут для "своих" ботов (с капчей)
last_used_stress = {}
last_used_channel = {}
last_used_aureport = {}
last_used_tida = {}
last_used_bank = {}
last_used_dsa = {}
last_used_telegraph = {}
last_used_trap = {}
_trap_sessions: dict = {}  # uid -> {bot_token, bot_username, bot_name}
_tida_pending: dict = {}  # uid -> {link, text, target, bot_token, username}

async def _send_with_monitor_offer(bot_instance, uid: int, caption: str, target: str, premium: int, subscribe):
    """Отправляет результат репортов с предложением мониторинга."""
    from datetime import datetime
    # Проверяем лимит
    active_count = await db.get_user_active_monitors_count(uid)
    limit = 5 if premium else 3
    # Подписка активна?
    sub_active = subscribe > now_msk() if isinstance(subscribe, datetime) else False
    already = await db.is_target_already_monitored(uid, target)
    was_before = await db.was_target_monitored_before(uid, target)

    can_add = sub_active and not already and not was_before and active_count < limit

    markup = keyboards.monitor_add_markup(target, can_add)
    try:
        await bot_instance.send_message(uid, caption, parse_mode="Markdown", reply_markup=markup)
    except Exception:
        await bot_instance.send_message(uid, caption, parse_mode="Markdown", reply_markup=keyboards.main_menu)


async def _offer_monitor(bot_instance, uid: int, target: str, premium: int, subscribe):
    """Отправляет отдельное предложение мониторинга после результатов."""
    _lang = await db.get_lang(uid)
    try:
        active_count = await db.get_user_active_monitors_count(uid)
        limit = 5 if premium else 3
        sub_active = subscribe > now_msk()
        already = await db.is_target_already_monitored(uid, target)
        was_before = await db.was_target_monitored_before(uid, target)
        can_add = sub_active and not already and not was_before and active_count < limit
        markup = keyboards.monitor_add_markup(target, can_add)
        await bot_instance.send_message(
            uid,
            t('monitor_offer_caption', _lang),
            parse_mode="Markdown",
            reply_markup=markup
        )
    except Exception:
        pass
    try:
        is_hidden = await db.get_is_hidden(uid)
        if is_hidden:
            _hide_markup = types.InlineKeyboardMarkup(row_width=2)
            _hide_markup.add(
                types.InlineKeyboardButton(t('hidden_notice_ok_btn', _lang), callback_data='hidden_notice_ok'),
                types.InlineKeyboardButton(t('hidden_notice_reveal_btn', _lang), callback_data='reveal_self'),
            )
            await bot_instance.send_message(
                uid,
                t('hidden_notice_msg', _lang),
                parse_mode="Markdown",
                reply_markup=_hide_markup
            )
    except Exception:
        pass
user_requests = {}
REQUEST_LIMIT = 3
TIME_FRAME = 1
_captcha_codes: dict = {}
_pending_refs: dict = {}  # uid -> ref_arg during lang select


async def _log_display(uid: int, username: str) -> tuple[str, str]:
    """Возвращает (display_uid, display_username) с учётом скрытия в логах."""
    try:
        if await db.get_is_hidden(uid):
            return "скрыт", "скрыт"
    except Exception:
        pass
    return str(uid), username

async def send_and_pin_site_msg(uid: int):
	try:
		msg = await bot.send_message(
			uid,
			"🔗 *Бот удален?* — [br\-v2\.top](https://br-v2.top)",
			parse_mode="MarkdownV2",
			disable_web_page_preview=False
		)
		await bot.pin_chat_message(uid, msg.message_id, disable_notification=True)
	except Exception as e:
		print(f"[PIN] Ошибка: {e}", flush=True)



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
media_markup = keyboards.media_markup
media_platform_markup = keyboards.media_platform_markup
media_confirm_markup = keyboards.media_confirm_markup
media_admin_markup = keyboards.media_admin_markup

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
		if any(k in err for k in ('unauthorized', 'forbidden', 'chat not found',
		                          'user not found', 'participant', 'not a member',
		                          'kicked', 'deactivated')):
			return False
		return True  # другие ошибки (сеть и т.д.) — не блокируем

async def check_subscription(uid: int, bot_instance=None) -> bool:
	"""Проверяет подписку на оба канала. Всегда через основной bot."""
	sub1 = await subsribe_channel(uid, channel_id)
	sub2 = await subsribe_channel(uid, channel2_id)
	return sub1 and sub2

async def send_subscribe_required(uid: int, bot_instance=None, lang: str = None):
	"""Отправляет сообщение с требованием подписки."""
	b = bot_instance or bot
	if lang is None:
		try:
			lang = await db.get_lang(uid)
		except Exception:
			lang = 'ru'
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
		types.InlineKeyboardButton(t('sub_btn_1', lang), url=invite1),
		types.InlineKeyboardButton(t('sub_btn_2', lang), url=invite2),
		types.InlineKeyboardButton(t('sub_btn_check', lang), callback_data='start_check_sub')
	)
	await b.send_message(uid, t('sub_required', lang), parse_mode="Markdown", reply_markup=markup)

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

class WaitAuReportFSM(StatesGroup):
	link = State()

class WaitTidaFSM(StatesGroup):
	link = State()
	target = State()      # тип цели: account/chat/channel
	ai_desc = State()     # описание нарушения для ИИ
	text = State()        # финальный текст (ручной ввод)
	text_confirm = State() # подтверждение ИИ-текста

class WaitUniversalFSM(StatesGroup):
	link = State()
	tida_text = State()

class WaitDsaFSM(StatesGroup):
	link = State()
	reason = State()
	sub_reason = State()
	text_confirm = State()
	text = State()

class WaitTelegraphFSM(StatesGroup):
	link = State()          # ввод ссылки
	confirm = State()       # подтверждение или свой текст
	custom_text = State()   # ввод своего текста
	sub_reason = State()
	text = State()
	text_confirm = State()

class WaitBankFSM(StatesGroup):
	card = State()
	bank_key = State()

class WaitCodeFSM(StatesGroup):
	phone = State()

class AdminAddReportsFSM(StatesGroup):
	user_id = State()
	amount = State()

class AdminRemoveReportsFSM(StatesGroup):
	user_id = State()
	amount = State()

class DeleteUserFSM(StatesGroup):
	user_id = State()

class CheckUserFSM(StatesGroup):
	query = State()

class AdminSendMsgFSM(StatesGroup):
	target = State()
	text   = State()

class CreatePromoFSM(StatesGroup):
	promo_type = State()
	code = State()
	days = State()
	activations = State()

class AdminAddCaseFSM(StatesGroup):
	user_id = State()
	amount = State()

class WaitProfileFSM(StatesGroup):
	link = State()

class WaitTrapFSM(StatesGroup):
	victim = State()   # ввод username жертвы после нажатия "Готово"

class WaitSessionFSM(StatesGroup):
    wait_username = State()
    wait_phone    = State()

class WaitProbivFSM(StatesGroup):
	query = State()

class MediaFSM(StatesGroup):
    waiting_link = State()
    # Admin states
    waiting_approve_comment = State()
    waiting_reject_reason = State()



global bot_status
bot_status = 1

global maintenance_mode
maintenance_mode = False

def _get_maintenance() -> bool:
    try:
        return open(".maintenance", "r").read().strip() == "1"
    except Exception:
        return False

def _set_maintenance(val: bool):
    global maintenance_mode
    maintenance_mode = val
    with open(".maintenance", "w") as f:
        f.write("1" if val else "0")

# Читаем начальное значение из файла
maintenance_mode = _get_maintenance()

# ─── Команды ──────────────────────────────────────────────────────────────────


@dp.callback_query_handler(lambda c: c.data == 'session_method')
async def session_method_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in admins:
        _slang = await db.get_lang(call.from_user.id)
        await call.answer(t('err_admin_only', _slang), show_alert=True)
        return
    _slang = await db.get_lang(call.from_user.id)
    await call.message.answer(t('session_method_prompt', _slang), parse_mode="Markdown")
    await WaitSessionFSM.wait_username.set()

@dp.message_handler(state=WaitSessionFSM.wait_username)
async def session_got_username(message: types.Message, state: FSMContext):
    await state.update_data(victim_username=message.text.strip().lstrip('@'))
    _slang = await db.get_lang(message.from_user.id)
    await message.answer(t('session_method_phone_prompt', _slang), parse_mode="Markdown")
    await WaitSessionFSM.wait_phone.set()

@dp.message_handler(state=WaitSessionFSM.wait_phone)
async def session_got_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.finish()
    _bot_token = data.get('_bot_token')
    _bot = Bot(token=_bot_token) if (_bot_token and _bot_token != config.TOKEN) else bot
    asyncio.create_task(main_session_snos(
        message.from_user.id,
        message.from_user.username or "",
        data['victim_username'],
        message.text.strip(),
        notify_bot=_bot
    ))

@dp.message_handler(commands=['on'])
async def on(message: types.Message):
	global bot_status
	if message.from_user.id in config.ADMINS:
		bot_status = 1
		await bot.send_message(message.chat.id, "🟢 *Включен!*", parse_mode=ParseMode.MARKDOWN)
		await bot.send_message(bot_logs, "🟢 *Включен!*", parse_mode=ParseMode.MARKDOWN)

@dp.message_handler(commands=['off'])
async def off(message: types.Message):
	global bot_status
	if message.from_user.id in config.ADMINS:
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
	if message.from_user.id in admins:
		try:
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
				"🤖 *Админ меню:*\n\n📊 *Статистика:*\n"
				f"*├─👥 Всего пользователей:* `{users_count}`\n"
				f"*├─💳 С подпиской:* `{subscribers_count}`\n"
				f"*├─🎯 С репортами:* `{reports_users_count}`\n"
				f"*├─🪞 Зеркал:* `{mirrors_count}`\n"
				f"*├─🕒 Сессий в ботнете:* `{sessions_count}`\n"
				f"*├─👑 Сессий в премиум ботнете:* `{sessions_count_prem}`\n"
				f"*├─🌐 Web-Reports:* `{report_count333}`\n"
				f"*└─✉️ Почт добавлено:* `{mails_count}`\n\n"
				"*/promo PROMOCODE DAYS ACTIVATIONS* - создать промокод\n"
				"*/on* - включить бота | */off* - выключить бота\n"
				"*/addwl ID* - добавить в вайтлист\n"
				"*/addtargetwl @username* - добавить цель в WL\n"
				"*/rmtargetwl @username* - убрать цель из WL\n"
				"*/listtargetwl* - список целей WL"
			)
			await bot.send_message(message.chat.id, text, reply_markup=keyboards.admin_markup, parse_mode="Markdown")
		except Exception as e:
			await bot.send_message(message.chat.id, f"❌ Ошибка: `{str(e)[:200]}`", parse_mode="Markdown")

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

_SUB_MAP = {
	"1":          ("1",  "1",   "sub_1d",      "100"),
	"3":          ("2",  "3",   "sub_3d",      "175"),
	"7":          ("4",  "7",   "sub_7d",      "350"),
	"30":         ("8",  "30",  "sub_30d",     "700"),
	"60":         ("12", "60",  "sub_60d",     "1100"),
	"premupgrade":("5",  "1",   "sub_premium", "400"),
}
_YM_WALLET = "4100118677444773"
_TON_ADDRESS = "UQDeT6tcvKiwrR_fCa0ORJ_OOKPQbnvbzyB8l1YXzXK0iLCf"

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'), state='*')
async def handle_subscription(callback_query: types.CallbackQuery):
	try:
		user_id = callback_query.from_user.id
		if not await check_user_in_db(user_id):
			return
		st = callback_query.data.split('_', 1)[1]
		if st not in _SUB_MAP:
			return
		_lang = await db.get_lang(user_id)
		amount_usd, _, pidor_key, amount_rub = _SUB_MAP[st]
		pidor = t(pidor_key, _lang)
		method_markup = types.InlineKeyboardMarkup(row_width=1)
		method_markup.add(
			types.InlineKeyboardButton("CryptoBot", callback_data=f'pay_crypto_{st}'),
			types.InlineKeyboardButton("🇷🇺 СБП", callback_data=f'pay_sbp_{st}'),
			types.InlineKeyboardButton("TonKeeper", callback_data=f'pay_ton_{st}'),
			keyboards.back,
		)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=t('shop_buy_select', _lang, item=pidor),
			parse_mode="MarkdownV2", reply_markup=method_markup
		)
	except Exception as e:
		print(f"handle_subscription: {e}")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('pay_crypto_'), state='*')
async def pay_crypto_callback(callback_query: types.CallbackQuery):
	try:
		user_id = callback_query.from_user.id
		if not await check_user_in_db(user_id):
			return
		st = callback_query.data[len('pay_crypto_'):]
		if st not in _SUB_MAP:
			return
		_lang = await db.get_lang(user_id)
		amount_usd, sub_days, pidor_key, _ = _SUB_MAP[st]
		pidor = t(pidor_key, _lang)
		invoice = await asyncio.to_thread(crypto.create_invoice, asset='USDT', amount=amount_usd)
		pay_url = invoice['pay_url']
		invoice_id = invoice['invoice_id']
		pay_check = types.InlineKeyboardMarkup(row_width=2)
		pay_check.add(
			types.InlineKeyboardButton(t('pay_btn_pay', _lang), url=pay_url),
			types.InlineKeyboardButton(t('pay_btn_paid', _lang), callback_data=f'check_status_{invoice_id}_{st}_{sub_days}')
		)
		pay_check.add(keyboards.back)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=t('shop_buy_usd', _lang, item=pidor, amount=amount_usd),
			parse_mode="MarkdownV2", reply_markup=pay_check
		)
	except Exception as e:
		print(f"pay_crypto_callback: {e}")

async def _create_pay_link(ym_url: str) -> str:
	try:
		import aiohttp as _aiohttp
		async with _aiohttp.ClientSession() as _s:
			async with _s.post(
				'http://127.0.0.1:8080/register_pay',
				json={'url': ym_url},
				timeout=_aiohttp.ClientTimeout(total=5)
			) as resp:
				data = await resp.json()
				return f"https://br-v2.top/pay/{data['token']}"
	except Exception:
		return ym_url

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('pay_sbp_'), state='*')
async def pay_sbp_callback(callback_query: types.CallbackQuery):
	try:
		import urllib.parse as _urlparse
		user_id = callback_query.from_user.id
		if not await check_user_in_db(user_id):
			return
		st = callback_query.data[len('pay_sbp_'):]
		if st not in _SUB_MAP:
			return
		_lang = await db.get_lang(user_id)
		amount_usd, sub_days, pidor_key, amount_rub = _SUB_MAP[st]
		pidor = t(pidor_key, _lang)
		label = f"sub_{user_id}_{st}"
		targets = _urlparse.quote(f"Subscription BR V2 {pidor}", safe='')
		ym_url = (
			f"https://yoomoney.ru/quickpay/confirm.xml"
			f"?receiver={_YM_WALLET}"
			f"&quickpay-form=shop"
			f"&targets={targets}"
			f"&sum={amount_rub}"
			f"&label={label}"
		)
		short_url = await _create_pay_link(ym_url)
		sbp_markup = types.InlineKeyboardMarkup(row_width=1)
		sbp_markup.add(
			types.InlineKeyboardButton(t('pay_btn_card', _lang), url=short_url),
			types.InlineKeyboardButton(t('pay_btn_paid', _lang), callback_data=f'sbp_paid_{st}'),
			keyboards.back,
		)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=t('shop_buy_rub', _lang, item=pidor, amount=amount_rub),
			parse_mode="MarkdownV2", reply_markup=sbp_markup
		)
	except Exception as e:
		print(f"pay_sbp_callback: {e}")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sbp_paid_'), state='*')
async def sbp_paid_callback(callback_query: types.CallbackQuery):
	try:
		await bot.answer_callback_query(callback_query.id)
		_lang = await db.get_lang(callback_query.from_user.id)
		await bot.send_message(
			callback_query.from_user.id,
			t('pay_sub_pending', _lang),
			parse_mode="MarkdownV2"
		)
	except Exception as e:
		print(f"sbp_paid_callback: {e}")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('case_sbp_paid_'), state='*')
async def case_sbp_paid_callback(callback_query: types.CallbackQuery):
	try:
		await bot.answer_callback_query(callback_query.id)
		uid = callback_query.from_user.id
		username = callback_query.from_user.username or "None"
		_lang = await db.get_lang(uid)
		await bot.send_message(
			uid,
			t('pay_case_pending', _lang),
			parse_mode="MarkdownV2"
		)
		await bot.send_message(
			bot_logs,
			f"🛒 `{uid}` (@{username}) заявил оплату кейса через СБП — проверить и выдать!",
			parse_mode="Markdown"
		)
	except Exception as e:
		print(f"case_sbp_paid_callback: {e}")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('pay_ton_'), state='*')
async def pay_ton_callback(callback_query: types.CallbackQuery):
	try:
		user_id = callback_query.from_user.id
		if not await check_user_in_db(user_id):
			return
		st = callback_query.data[len('pay_ton_'):]
		if st not in _SUB_MAP:
			return
		_lang = await db.get_lang(user_id)
		amount_usd, _, pidor_key, _ = _SUB_MAP[st]
		pidor = t(pidor_key, _lang)
		ton_markup = types.InlineKeyboardMarkup(row_width=1)
		ton_markup.add(
			types.InlineKeyboardButton("✍️ Написать @TariSmit", url='https://t.me/TariSmit'),
			keyboards.back,
		)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=t('shop_buy_ton', _lang, item=pidor, amount=amount_usd, address=_TON_ADDRESS),
			parse_mode="MarkdownV2", reply_markup=ton_markup
		)
	except Exception as e:
		print(f"pay_ton_callback: {e}")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('check_status_'), state='*')
async def check_status_callback(callback_query: types.CallbackQuery):
	try:
		parts = callback_query.data.split('_')
		invoice_id, sub_type, sub_days = parts[2], parts[3], parts[4]
		user_id = callback_query.from_user.id
		if not await check_user_in_db(user_id):
			return
		_lang = await db.get_lang(user_id)
		old_invoice = await asyncio.to_thread(crypto.get_invoices, invoice_ids=invoice_id)
		if old_invoice['items'][0]['status'] != "paid":
			await bot.send_message(user_id, t('pay_not_received', _lang), parse_mode=ParseMode.MARKDOWN)
			return
		# Защита от повторного начисления
		if await db.is_invoice_used(invoice_id):
			await bot.send_message(user_id, t('pay_already_processed', _lang), parse_mode=ParseMode.MARKDOWN)
			return
		await db.mark_invoice_used(invoice_id, user_id)
		await bot.edit_message_caption(
			chat_id=callback_query.message.chat.id,
			message_id=callback_query.message.message_id,
			caption=t('pay_thanks', _lang), parse_mode="MarkdownV2", reply_markup=back_markup
		)
		if sub_type != "premupgrade":
			new_date = (now_msk() + timedelta(days=int(sub_days))).strftime("%Y-%m-%d %H:%M:%S")
			await db.set_subscribe(user_id, new_date)
			await bot.send_message(bot_logs, f"💳 *Оплата подписки* `{user_id}` *до* `{new_date}`", parse_mode="Markdown")
			# Реферальный бонус — 10% от дней подписки рефереру
			referrer_id = await db.get_referrer_id(user_id)
			if referrer_id:
				bonus_days = max(1, int(int(sub_days) * 0.1))
				ref_new_date = (now_msk() + timedelta(days=bonus_days)).strftime("%Y-%m-%d %H:%M:%S")
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
		_rl_lang = await db.get_lang(message.from_user.id)
		await message.reply(t('rate_limit', _rl_lang))
		return
	uid = message.chat.id
	is_new = not await db.user_exists(uid)
	await db.add_user(uid, message.from_user.username or '')

	if not await is_verified(uid):
		# Сохраняем ref_arg до выбора языка
		if is_new:
			args = message.get_args()
			if args and args.startswith("ref_"):
				_pending_refs[uid] = args
		# Сначала спрашиваем язык — капча будет на выбранном языке
		lang_markup = types.InlineKeyboardMarkup(row_width=2)
		lang_markup.add(
			types.InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_select_ru'),
			types.InlineKeyboardButton("🇬🇧 English", callback_data='lang_select_en'),
		)
		await bot.send_message(uid,
			"🌐 *Выберите язык | Choose language:*",
			parse_mode="Markdown", reply_markup=lang_markup)
		return
	try:
		await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
	except Exception:
		pass
	# Проверяем подписку перед показом меню
	lang = 'ru'
	try:
		lang = await db.get_lang(uid)
	except Exception:
		pass
	if not await check_subscription(uid):
		await send_subscribe_required(uid, lang=lang)
		return
	await send_and_pin_site_msg(uid)
	await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
		caption=t('menu_caption', lang),
		parse_mode="MarkdownV2", reply_markup=keyboards.get_menu(uid in admins, lang))

@dp.message_handler(state=WaitCaptchaFSM.code)
async def check_captcha(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	lang = await db.get_lang(uid)
	if message.text.strip().lower() == _captcha_codes.get(uid, "").lower():
		await state.finish()
		_captcha_codes.pop(uid, None)
		await set_verified(uid)

		# Реферальная логика — только после прохождения капчи
		ref_arg = _pending_refs.pop(uid, None)
		if ref_arg and ref_arg.startswith("ref_"):
			try:
				referrer_id = int(ref_arg[4:])
				if referrer_id != uid and await db.user_exists(referrer_id):
					await db.set_referrer(uid, referrer_id)
					new_count = await db.increment_referral_count(referrer_id)
					await bot.send_message(
						referrer_id,
						t('ref_new_user', await db.get_lang(referrer_id), count=new_count),
						parse_mode="Markdown"
					)
			except (ValueError, Exception):
				pass

		# Язык уже выбран до капчи — сразу показываем стикер и меню
		try:
			await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
		except Exception:
			pass
		if not await check_subscription(uid):
			await send_subscribe_required(uid, lang=lang)
			return
		await send_and_pin_site_msg(uid)
		await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
			caption=t('menu_caption', lang),
			parse_mode="MarkdownV2", reply_markup=keyboards.get_menu(uid in admins, lang))
	else:
		try:
			code = generate_captcha_text()
			_captcha_codes[uid] = code
			await bot.send_photo(uid, photo=generate_captcha_image(code),
				caption=t('captcha_wrong', lang), parse_mode="Markdown")
		except Exception as e:
			print(f"[CAPTCHA] Ошибка повторной генерации: {e}", flush=True)
			await bot.send_message(uid, t('captcha_error', lang), parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data in ('lang_select_ru', 'lang_select_en'), state='*')
async def handle_lang_select(call: types.CallbackQuery, state: FSMContext):
	uid = call.from_user.id
	lang = 'ru' if call.data == 'lang_select_ru' else 'en'
	await db.set_lang(uid, lang)
	try:
		await call.message.delete()
	except Exception:
		pass

	# Если пользователь ещё не прошёл капчу — показываем капчу на выбранном языке
	if not await is_verified(uid):
		try:
			code = generate_captcha_text()
			_captcha_codes[uid] = code
			await state.set_state(WaitCaptchaFSM.code)
			await bot.send_photo(uid, photo=generate_captcha_image(code),
				caption=t('captcha_prompt', lang), parse_mode="Markdown")
		except Exception as e:
			print(f"[CAPTCHA] Ошибка генерации: {e}", flush=True)
			await bot.send_message(uid, t('captcha_error', lang), parse_mode="Markdown")
		return

	# Иначе — смена языка из профиля, просто показываем меню
	await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
	if not await check_subscription(uid):
		await send_subscribe_required(uid, lang=lang)
		return
	await send_and_pin_site_msg(uid)
	await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
		caption=t('menu_caption', lang),
		parse_mode="MarkdownV2", reply_markup=keyboards.get_menu(uid in admins, lang))


PROBIV_HELP = (
    "*\U0001f575️ Пробив — поиск по открытым базам*\n\n"
    "\U0001f464 `/fio` Иванов Иван Иванович 1985\n"
    "\U0001f4f1 `/num` 79277231370\n"
    "\U0001f4e7 `/email` user@gmail.com\n"
    "\U0001f511 `/nick` username123\n"
    "\U0001f510 `/pass` qwerty123\n"
    "\U0001faaa `/snils` 12345678901\n"
    "\U0001f3e6 `/inn` 582801503237\n"
    "\U0001f697 `/car` А123ВС77 или VIN\n"
    "\U0001f310 `/ip` 8.8.8.8\n"
    "\U0001f499 `/vk` 123456789\n"
    "\U0001f3b5 `/tt` username\n"
    "\U0001f3e0 `/adr` Москва, ул. Ленина 1\n\n"
    "✏️ *Введи команду:*"
)

@dp.callback_query_handler(lambda c: c.data == 'probiv', state='*')
async def probiv_menu(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    _lang = 'ru'
    try:
        _lang = await db.get_lang(uid)
    except Exception:
        pass
    user_data = await db.get_user(uid)
    if not user_data:
        await call.answer(t('err_no_access', _lang), show_alert=True)
        return
    sub = user_data.get('subscribe')
    sub_active = sub > now_msk() if isinstance(sub, datetime) else False
    if not sub_active:
        await call.answer(t('err_subscribe_required', _lang), show_alert=True)
        return
    cancel_markup = types.InlineKeyboardMarkup()
    _cancel_text = '❌ Отмена' if _lang == 'ru' else '❌ Cancel'
    cancel_markup.add(types.InlineKeyboardButton(_cancel_text, callback_data='probiv_cancel'))
    await call.message.answer(PROBIV_HELP, parse_mode="Markdown", reply_markup=cancel_markup)
    await WaitProbivFSM.query.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == 'probiv_cancel', state='*')
async def probiv_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    _lang = 'ru'
    try:
        _lang = await db.get_lang(call.from_user.id)
    except Exception:
        pass
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer(t('action_cancelled', _lang))

@dp.message_handler(state=WaitProbivFSM.query)
async def probiv_query(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or str(uid)
	_lang = 'ru'
	try:
		_lang = await db.get_lang(uid)
	except Exception:
		pass

	# Проверяем подписку
	user_data = await db.get_user(uid)
	if not user_data:
		await state.finish()
		return
	sub = user_data.get('subscribe')
	sub_active = sub > now_msk() if isinstance(sub, datetime) else False
	if not sub_active:
		await state.finish()
		await message.answer(t('probiv_no_sub', _lang), parse_mode="Markdown")
		return

	is_premium = bool(user_data.get('premium', 0))
	now_dt = now_msk()

	# Проверяем КД и лимит
	usage = await db.get_probiv_usage(uid)
	last_req = usage.get('last_request_at')
	if last_req:
		last_req_naive = last_req.replace(tzinfo=None) if getattr(last_req, 'tzinfo', None) else last_req
		diff = (now_dt - last_req_naive).total_seconds()
		if diff < 30:
			wait = int(30 - diff)
			await message.answer(t('probiv_cd', _lang, wait=wait), parse_mode="Markdown")
			return

	if not is_premium:
		hour_count = usage.get('hour_count', 0)
		hw_start = usage.get('hour_window_start')
		if hw_start:
			hw_naive = hw_start.replace(tzinfo=None) if getattr(hw_start, 'tzinfo', None) else hw_start
			window_age = (now_dt - hw_naive).total_seconds()
			if window_age < 3600 and hour_count >= 5:
				mins_left = int((3600 - window_age) / 60)
				await message.answer(
					f"⛔️ *Лимит 5 запросов/час исчерпан.*\n"
					f"*└─ Обновится через ~{mins_left} мин.*\n\n"
					f"_Премиум-подписка снимает ограничения._",
					parse_mode="Markdown"
				)
				return

	raw = message.text.strip()
	if not raw:
		await message.answer(t('probiv_empty', _lang), parse_mode="Markdown")
		return

	# Парсим команды вида /cmd значение
	_CMD_MAP = {
		'/fio':   lambda v: v,
		'/num':   lambda v: v,
		'/email': lambda v: v,
		'/car':   lambda v: v,
		'/ip':    lambda v: v,
		'/nick':  lambda v: f'nick:{v}',
		'/pass':  lambda v: f'pass:{v}',
		'/snils': lambda v: f'snils{v}',
		'/inn':   lambda v: f'inn{v}',
		'/vk':    lambda v: f'vkid{v}',
		'/tt':    lambda v: f'tt:{v}',
		'/adr':   lambda v: f'addr:{v}',
	}
	query = None
	for cmd, transform in _CMD_MAP.items():
		if raw.lower().startswith(cmd + ' ') or raw.lower() == cmd:
			value = raw[len(cmd):].strip()
			if not value:
				await message.answer(f"❌ *Укажи значение после команды `{cmd}`*", parse_mode="Markdown")
				return
			query = transform(value)
			break
	if query is None:
		await message.answer(
			"❌ *Неизвестная команда.*\n\nИспользуй формат: `/num 79991234567`",
			parse_mode="Markdown"
		)
		return

	wait_msg = await message.answer(t('probiv_searching', _lang), parse_mode="Markdown")

	try:
		import urllib.parse
		encoded = urllib.parse.quote(query, safe='')
		url = f"https://api.depsearch.sbs/quest={encoded}&token={DEPSEARCH_TOKEN}&lang=ru"
		async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
			async with session.get(url) as resp:
				if resp.status == 429:
					await wait_msg.edit_text("⚠️ *API перегружен, попробуй через 10 сек.*", parse_mode="Markdown")
					return
				if resp.status != 200:
					await wait_msg.edit_text(f"❌ *Ошибка API: {resp.status}*", parse_mode="Markdown")
					return
				data = await resp.json(content_type=None)
	except asyncio.TimeoutError:
		await wait_msg.edit_text("❌ *Таймаут запроса.*", parse_mode="Markdown")
		return
	except Exception as e:
		await wait_msg.edit_text(f"❌ *Ошибка: {e}*", parse_mode="Markdown")
		return

	# Записываем использование
	await db.record_probiv_request(uid, now_msk())
	await state.finish()
	try:
		await wait_msg.delete()
	except Exception:
		pass

	# Форматируем результат (plain text — без Markdown чтобы спецсимволы не ломали)
	lines_out = [f"🔍 Пробив: {query}", ""]

	# Специальные блоки (phone_info, ip_info)
	for block_key in ('phone_info', 'ip_info'):
		block = data.get(block_key)
		if block and isinstance(block, dict):
			lines_out.append(f"📡 {block_key}")
			for k, v in block.items():
				lines_out.append(f"  {k}: {v}")
			lines_out.append("")

	results = data.get('results', [])
	lines_out.append(f"📊 Найдено: {len(results)} результатов")
	lines_out.append("")

	for idx, item in enumerate(results, 1):
		lines_out.append("─" * 25)
		lines_out.append(f"#{idx}")
		if isinstance(item, dict):
			for k, v in item.items():
				if v is not None and v != '' and v != []:
					lines_out.append(f"  {k}: {v}")
		else:
			lines_out.append(str(item))
		lines_out.append("")

	text_out = "\n".join(lines_out)

	# Лог в канал
	masked = query if len(query) <= 4 else query[:3] + '*' * (len(query) - 4) + query[-1]
	premium_tag = "👑 Премиум" if is_premium else "⚡️ Обычная"
	try:
		_log_uid_p, _log_uname_p = await _log_display(uid, username)
		await bot.send_message(
			bot_logs,
			f"🕵️ *Пробив*\n"
			f"👤 @{_log_uname_p} (`{_log_uid_p}`) | {premium_tag}\n"
			f"📥 Запрос: `{masked}`\n"
			f"📊 Найдено: *{len(results)}* совпадений",
			parse_mode="Markdown"
		)
	except Exception:
		pass

	# Отправляем результат
	cancel_markup = types.InlineKeyboardMarkup(row_width=1)
	cancel_markup.add(
		types.InlineKeyboardButton("\U0001f575\ufe0f Новый запрос", callback_data='probiv'),
		types.InlineKeyboardButton("[\U0001f519] Меню", callback_data='go_to_main_menu'),
	)
	if len(text_out) <= 4000:
		await message.answer(text_out, reply_markup=cancel_markup)
	else:
		import io
		buf = io.BytesIO(text_out.encode('utf-8'))
		buf.name = 'probiv_result.txt'
		await message.answer_document(
			types.InputFile(buf, filename='probiv_result.txt'),
			caption=f"\U0001f575\ufe0f Результат: {len(results)} совпадений",
			reply_markup=cancel_markup,
		)

# ─── Проверка подписки по кнопке ──────────────────────────────────────────────

@dp.callback_query_handler(lambda c: c.data == 'start_check_sub', state='*')
async def start_check_sub_callback(call: types.CallbackQuery):
	uid = call.from_user.id
	lang = 'ru'
	try:
		lang = await db.get_lang(uid)
	except Exception:
		pass
	if await check_subscription(uid):
		try:
			await bot.delete_message(uid, call.message.message_id)
		except Exception:
			pass
		await bot.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
		await bot.send_photo(uid, photo=open('material/menu.png', 'rb'),
			caption=t('menu_caption', lang),
			parse_mode="MarkdownV2", reply_markup=keyboards.get_menu(uid in admins, lang))
	else:
		await bot.answer_callback_query(call.id, t('sub_check_fail', lang).replace('*', ''), show_alert=True)

# ─── Главный callback хендлер ─────────────────────────────────────────────────

@dp.callback_query_handler(lambda call: True, state='*')
async def callback_inline(call: types.CallbackQuery, state: FSMContext):
	await handle_callback(call, bot, dp, state)

async def _dsa_generate_and_show(uid: int, bot_instance, dp_instance, state):
	"""Генерирует текст через Groq и показывает пользователю с кнопками."""
	from dsa_snos import generate_complaint_text, fetch_message_text, DSA_REASONS, DSA_SUB_REASONS
	fsm_data = await dp_instance.current_state(user=uid).get_data()
	link = fsm_data.get("dsa_link", "")
	reason_key = fsm_data.get("dsa_reason", "other")
	sub_key = fsm_data.get("dsa_sub", "")

	reason_label = DSA_REASONS.get(reason_key, ("", "Other", None))[0]
	sub_label = DSA_SUB_REASONS.get(sub_key, ("", ""))[1] if sub_key else ""

	await bot_instance.send_message(uid, t('ai_generating_dsa', await db.get_lang(uid)), parse_mode="Markdown")

	# Получаем текст сообщения
	msg_text = await fetch_message_text(link)

	# Генерируем через Groq
	generated = await generate_complaint_text(
		reason=reason_label.replace(reason_label[:2], "").strip(),
		sub_reason=sub_label,
		message_text=msg_text
	)

	# Сохраняем в FSM
	await dp_instance.current_state(user=uid).update_data(dsa_generated_text=generated)

	preview = generated
	await bot_instance.send_message(uid,
		t('dsa_ai_result', await db.get_lang(uid), text=preview),
		parse_mode="Markdown",
		reply_markup=keyboards.dsa_text_confirm_markup(preview))


async def _dsa_launch(uid: int, bot_instance, fsm_data: dict, state):
	"""Запускает DSA репорт с данными из FSM."""
	from dsa_snos import main_dsa_snos
	link = fsm_data.get("dsa_link", "")
	reason_key = fsm_data.get("dsa_reason", "other")
	sub_key = fsm_data.get("dsa_sub", "")
	text = fsm_data.get("dsa_text") or fsm_data.get("dsa_generated_text", "")
	username = fsm_data.get("dsa_username", "None")
	_bot_token = fsm_data.get("_bot_token")
	_is_mirror = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror else bot

	if uid not in admins:
		last_used_dsa[uid] = now_msk()

	await _bot.send_message(uid,
		f'🇪🇺 *Запускаю DSA Report...*\n*└─ Это может занять 1-3 минуты*',
		parse_mode="Markdown")

	try:
		await main_dsa_snos(link, uid, username, reason_key, sub_key, text, count=1, _bot=_bot)
		try: await db.log_attack(uid, link, "dsa")
		except Exception as e: print(f"[HISTORY] dsa log error: {e}", flush=True)
		# Предлагаем мониторинг
		try:
			_ud = await db.get_user(uid)
			_prem = int(_ud.get('premium', 0)) if _ud else 0
			_sub = datetime.strptime(str(_ud['subscribe'])[:19], "%Y-%m-%d %H:%M:%S") if _ud else now_msk() - timedelta(days=1)
			await _offer_monitor(_bot, uid, link, _prem, _sub)
		except Exception:
			pass
	except Exception as e:
		print(f"[DSA] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка DSA:* `{str(e)[:100]}`',
			parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


async def handle_callback(call: types.CallbackQuery, bot_instance, dp_instance, state: FSMContext):
	"""Общая логика callback — используется и основным ботом, и зеркалами."""
	global maintenance_mode
	# Получаем токен bot_instance безопасно (aiogram 2 хранит в _token)
	_instance_token = getattr(bot_instance, '_token', None)
	try:
		uid = call.from_user.id
		if await is_blocked(uid):
			return
		if check_rate_limit(uid):
			await block_user(uid)
			_rl_lang2 = await db.get_lang(uid)
			await call.message.answer(t('rate_limit', _rl_lang2))
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
			_sub_lang = await db.get_lang(uid)
			temp_check_markup = types.InlineKeyboardMarkup(row_width=1)
			temp_check_markup.add(
				types.InlineKeyboardButton(t('sub_btn_1', _sub_lang), url=invite1),
				types.InlineKeyboardButton(t('sub_btn_2', _sub_lang), url=invite2),
				types.InlineKeyboardButton(t('sub_btn_check', _sub_lang), callback_data='start_check_sub')
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=t('sub_check_caption', _sub_lang), parse_mode="Markdown", reply_markup=temp_check_markup)
			return

		user_data = await db.get_user(uid)
		if not user_data:
			await db.add_user(uid)
			user_data = await db.get_user(uid)
		subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
		premium = int(user_data['premium'])
		username = call.from_user.username or "None"
		fullname = call.from_user.first_name
		_user_lang = await db.get_lang(uid)
		back_markup = keyboards.get_back_markup(_user_lang)
		panel_back_markup = keyboards.get_panel_back_markup(_user_lang)
		main_menu = keyboards.get_main_menu_markup(_user_lang)
		functions = keyboards.get_functions(_user_lang)

		d = call.data

		# Кнопка проверки подписки — обрабатываем здесь тоже (для зеркал)
		if d == 'start_check_sub':
			_lang = 'ru'
			try:
				_lang = await db.get_lang(uid)
			except Exception:
				pass
			if await check_subscription(uid):
				try:
					await bot_instance.delete_message(uid, call.message.message_id)
				except Exception:
					pass
				await bot_instance.send_sticker(uid, InputFile("AnimatedSticker.tgs"))
				await bot_instance.send_photo(uid, photo=open('material/menu.png', 'rb'),
					caption=t('menu_caption', _lang),
					parse_mode="MarkdownV2", reply_markup=keyboards.get_menu(uid in admins, _lang))
			else:
				await bot_instance.answer_callback_query(call.id, t('sub_check_fail', _lang).replace('*', ''), show_alert=True)
			return

		if d == 'functions':
			_fn_caption = t('panel_caption_admin', _user_lang) if uid in admins else t('panel_caption', _user_lang)
			_fn_markup = keyboards.get_panel_select_markup(_user_lang, is_admin=(uid in admins))
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=_fn_caption, parse_mode="MarkdownV2", reply_markup=_fn_markup)
			except Exception:
				try:
					await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
				except Exception:
					pass

		elif d == 'panel_regular':
			_fn_caption = t('panel_caption', _user_lang)
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=_fn_caption, parse_mode="MarkdownV2",
					reply_markup=keyboards.get_functions(_user_lang))
			except Exception:
				try:
					await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
				except Exception:
					pass

		elif d == 'panel_premium':
			_fn_caption = t('panel_caption_admin', _user_lang) if uid in admins else '>👑 *Премиум методы*'
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=_fn_caption, parse_mode="MarkdownV2",
					reply_markup=keyboards.get_premium_functions(_user_lang, is_admin=(uid in admins)))
			except Exception:
				try:
					await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
				except Exception:
					pass
		elif d == 'profile':
			sub_text = t('profile_sub_expired', _user_lang) if subscribe < now_msk() else t('profile_sub_left', _user_lang, days=(subscribe - now_msk()).days)
			prem = t('profile_prem_yes', _user_lang) if premium == 1 else t('profile_prem_no', _user_lang)
			free_reports = await db.get_free_reports(uid)
			ref_count = await db.get_referral_count(uid)
			# Топ-3 текущей недели
			from datetime import timedelta as _td2
			_now2 = now_msk()
			_wstart = (_now2 - _td2(days=_now2.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
			_wend = _wstart + _td2(weeks=1)
			_top3 = await db.get_weekly_top3(_wstart, _wend)
			_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
			_PRIZES = {1: 150, 2: 75, 3: 50}
			_top_lines = ["\n\n🏆 *Топ рейтинг недели:*"]
			if _top3:
				for _ri, _rrow in enumerate(_top3, 1):
					_runame = f"@{_rrow['username']}" if _rrow['username'] else f"ID {_rrow['user_id']}"
					_top_lines.append(f"{_MEDALS[_ri]} {_runame} — {_rrow['total']} репортов → {_PRIZES[_ri]}⭐")
			else:
				_top_lines.append("_Пока нет репортов — стань первым!_")
			_top_lines.append("_Рейтинг обновляется каждый понедельник_")
			_profile_markup = types.InlineKeyboardMarkup(row_width=1)
			_profile_markup.add(types.InlineKeyboardButton("🏆 Подробнее о топе", callback_data='top_rating'))
			_profile_markup.add(keyboards.get_back_btn(_user_lang))
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=f"{t('profile_caption', _user_lang)}\n\n{t('profile_name', _user_lang, name=fullname)}\n{t('profile_id', _user_lang, uid=uid)}\n{t('profile_username', _user_lang, username=username)}\n{t('profile_premium', _user_lang, prem=prem)}\n{t('profile_free_reports', _user_lang, count=free_reports)}\n{t('profile_refs', _user_lang, count=ref_count)}\n\n{t('profile_sub_status', _user_lang, sub_text=sub_text)}" + "\n".join(_top_lines),
				parse_mode="Markdown", reply_markup=_profile_markup)
		elif d == 'admin_panel':
			if uid not in admins:
				return
			try:
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
				_adm_text = (
					"🤖 *Админ меню:*\n\n📊 *Статистика:*\n"
					f"*├─👥 Всего пользователей:* `{users_count}`\n"
					f"*├─💳 С подпиской:* `{subscribers_count}`\n"
					f"*├─🎯 С репортами:* `{reports_users_count}`\n"
					f"*├─🪞 Зеркал:* `{mirrors_count}`\n"
					f"*├─🕒 Сессий в ботнете:* `{sessions_count}`\n"
					f"*├─👑 Сессий в премиум ботнете:* `{sessions_count_prem}`\n"
					f"*├─🌐 Web-Reports:* `{report_count333}`\n"
					f"*└─✉️ Почт добавлено:* `{mails_count}`"
				)
				await bot_instance.send_message(call.message.chat.id, _adm_text, reply_markup=keyboards.admin_markup, parse_mode="Markdown")
			except Exception as _e:
				await bot_instance.send_message(call.message.chat.id, f"❌ Ошибка: `{str(_e)[:200]}`", parse_mode="Markdown")

		elif d == 'profile_history' or d.startswith('profile_history_p_'):
			_PAGE_SIZE = 10
			_hist_offset = 0
			if d.startswith('profile_history_p_'):
				try:
					_hist_offset = int(d.split('profile_history_p_')[1])
				except Exception:
					_hist_offset = 0
			_METHOD_LABELS = {
				'botnet': '🤖 Ботнет',
				'prem_botnet': '👑 Прем ботнет',
				'web': '🌐 Веб',
				'mail': '📧 Почта',
				'bot': '🤖 Бот-метод',
				'channel': '📢 Канал',
				'dsa': '⚖️ DSA',
				'telegraph': '📡 Telegraph',
				'tida': '🎵 TikTok',
				'aureport': '🔍 Аурепорт',
				'profile': '👤 Профиль',
			}
			_total = await db.get_attack_history_count(uid)
			history = await db.get_attack_history(uid, limit=_PAGE_SIZE, offset=_hist_offset)
			if not history and _hist_offset == 0:
				_htxt = "📋 История жалоб\n\nЖалобы ещё не отправлялись"
			else:
				_page_num = _hist_offset // _PAGE_SIZE + 1
				_pages_total = max(1, (_total + _PAGE_SIZE - 1) // _PAGE_SIZE)
				_htxt = f"📋 История жалоб [{_page_num}/{_pages_total}] (всего: {_total})\n\n"
				for _h in history:
					_method = _METHOD_LABELS.get(_h['method'], _h['method'])
					_dt = _h['created_at'].strftime("%d.%m %H:%M") if _h['created_at'] else "—"
					_url = _h['target_url']
					_sc = _h['success_count']
					_sc_str = f"  ✅ {_sc}" if _sc > 0 else ""
					_htxt += f"• {_method} | {_dt}{_sc_str}\n  {_url[:50]}\n"
			_hist_markup = types.InlineKeyboardMarkup(row_width=2)
			_nav_btns = []
			if _hist_offset > 0:
				_nav_btns.append(types.InlineKeyboardButton(t('btn_prev', _user_lang), callback_data=f'profile_history_p_{max(0, _hist_offset - _PAGE_SIZE)}'))
			if _hist_offset + _PAGE_SIZE < _total:
				_nav_btns.append(types.InlineKeyboardButton(t('btn_next', _user_lang), callback_data=f'profile_history_p_{_hist_offset + _PAGE_SIZE}'))
			if _nav_btns:
				_hist_markup.add(*_nav_btns)
			_hist_markup.add(types.InlineKeyboardButton("[🔙] Назад", callback_data='settings_menu'))
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=_htxt, reply_markup=_hist_markup)
			except Exception:
				await bot_instance.edit_message_text(_htxt, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=_hist_markup)

		elif d == 'profile_toggle_hidden':
			new_hidden = await db.toggle_hidden(uid)
			await call.answer(t('hidden_on', _user_lang) if new_hidden else t('hidden_off', _user_lang), show_alert=False)
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('settings_caption', _user_lang), parse_mode="Markdown",
					reply_markup=keyboards.get_settings_markup(_user_lang, new_hidden))
			except Exception:
				pass
		elif d == 'hidden_notice_ok':
			await call.answer()
			try:
				await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
			except Exception:
				pass
		elif d == 'reveal_self':
			pool_ = await db.get_pool()
			async with pool_.acquire() as _conn:
				await _conn.execute("UPDATE users SET is_hidden = FALSE WHERE user_id = $1", uid)
			await call.answer(t('hidden_now_visible', _user_lang), show_alert=False)
			try:
				await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
			except Exception:
				pass
		elif d == 'lang_change':
			_lang_markup = types.InlineKeyboardMarkup(row_width=2)
			_lang_markup.add(
				types.InlineKeyboardButton("🇷🇺 Русский", callback_data='profile_lang_ru'),
				types.InlineKeyboardButton("🇬🇧 English", callback_data='profile_lang_en'),
			)
			_lang_markup.add(types.InlineKeyboardButton(t('btn_back', _user_lang), callback_data='settings_menu'))
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption="🌐 *Выберите язык | Choose language*",
				parse_mode="Markdown", reply_markup=_lang_markup)
		elif d in ('profile_lang_ru', 'profile_lang_en'):
			_new_lang = 'ru' if d == 'profile_lang_ru' else 'en'
			await db.set_lang(uid, _new_lang)
			await call.answer(t('lang_set_ru', _new_lang) if _new_lang == 'ru' else t('lang_set_en', _new_lang), show_alert=False)
			is_hidden = await db.get_is_hidden(uid)
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('settings_caption', _new_lang), parse_mode="Markdown",
					reply_markup=keyboards.get_settings_markup(_new_lang, is_hidden))
			except Exception:
				pass
		elif d == "back":
			# Если сообщение с caption (фото) — редактируем caption
			# Если обычное текстовое — удаляем и отправляем меню заново
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('menu_caption', _user_lang),
					parse_mode="MarkdownV2", reply_markup=keyboards.get_menu(uid in admins, _user_lang))
			except Exception:
				try:
					await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
				except Exception:
					pass
				await bot_instance.send_photo(call.message.chat.id, photo=open('material/menu.png', 'rb'),
					caption=t('menu_caption', _user_lang),
					parse_mode="MarkdownV2", reply_markup=keyboards.get_menu(uid in admins, _user_lang))
			# Сбрасываем FSM состояние если есть
			try:
				current = await state.get_state()
				if current and 'WaitDsaFSM' in str(current):
					await state.finish()
			except Exception:
				pass
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
				types.InlineKeyboardButton("📺 Канал (1 мин)", url=channel_invite),
				types.InlineKeyboardButton("📄 Мануал", url='https://br-v2.top/manual'),
			)
			dyn_info_markup.add(
				types.InlineKeyboardButton("🌐 Сайт", url='https://br-v2.top'),
				types.InlineKeyboardButton("❓ FAQ", url='https://br-v2.top/faq'),
			)
			dyn_info_markup.add(
				types.InlineKeyboardButton("👑 Владелец", url='https://t.me/TariSmit'),
				types.InlineKeyboardButton("🆘 Поддержка", url='https://t.me/BR_V2_support'),
			)
			dyn_info_markup.add(keyboards.get_back_btn(_user_lang))
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=t('info_caption', _user_lang), parse_mode="MarkdownV2", reply_markup=dyn_info_markup)

		elif d == 'bonuses_menu':
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=t('bonuses_caption', _user_lang), parse_mode="Markdown",
				reply_markup=keyboards.get_bonuses_markup(_user_lang))

		elif d == 'top_rating':
			from datetime import datetime as _dt, timedelta as _td
			_now = now_msk()
			_days_since_mon = _now.weekday()
			_week_start = (_now - _td(days=_days_since_mon)).replace(hour=0, minute=0, second=0, microsecond=0)
			_week_end = _week_start + _td(weeks=1)
			_top3 = await db.get_weekly_top3(_week_start, _week_end)
			_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
			_PRIZES = {1: 150, 2: 75, 3: 50}
			_week_label = f"{_week_start.strftime('%d.%m')} — {(_week_end - _td(days=1)).strftime('%d.%m')}"
			_lines = [f"🏆 *Рейтинг недели* ({_week_label})\n"]
			if _top3:
				for _i, _row in enumerate(_top3, 1):
					_uname = f"@{_row['username']}" if _row['username'] else f"ID {_row['user_id']}"
					_lines.append(f"{_MEDALS[_i]} {_uname} — {_row['total']} репортов")
			else:
				_lines.append("_Пока нет репортов — стань первым!_")
			_lines.append(
				"\n*🎁 Награды за неделю:*\n"
				"🥇 1 место — 150 ⭐ Telegram Stars\n"
				"🥈 2 место — 75 ⭐ Telegram Stars\n"
				"🥉 3 место — 50 ⭐ Telegram Stars\n\n"
				"*📈 Как попасть в топ?*\n"
				"Отправляй больше успешных репортов через любой метод — "
				"ботнет, веб, SMS, DSA и другие. "
				"Рейтинг обновляется каждый понедельник в 00:00 МСК, "
				"победители получают Stars в течение 24ч."
			)
			_top_markup = types.InlineKeyboardMarkup(row_width=2)
			_top_markup.add(
				types.InlineKeyboardButton("👤 Профиль", callback_data='profile'),
				types.InlineKeyboardButton("🎁 Бонусы", callback_data='bonuses_menu'),
			)
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption="\n".join(_lines), parse_mode="Markdown", reply_markup=_top_markup)
			except Exception:
				await bot_instance.edit_message_text("\n".join(_lines), chat_id=call.message.chat.id,
					message_id=call.message.message_id, parse_mode="Markdown", reply_markup=_top_markup)

		elif d == 'settings_menu':
			is_hidden = await db.get_is_hidden(uid)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=t('settings_caption', _user_lang), parse_mode="Markdown",
				reply_markup=keyboards.get_settings_markup(_user_lang, is_hidden))

		elif d == 'mirrors_menu':
			mirror_count = await db.count_user_mirrors(uid)
			bonus_given = await db.get_mirror_bonus_given(uid)
			bonus_status = "✅ Получен" if bonus_given else (f"🔒 Нужно {2 - mirror_count} зеркала" if mirror_count < 2 else "⬆️ Доступен — создай зеркало")
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=t('mirrors_caption', _user_lang) + f"\n\n▪️ *Зеркал создано: {mirror_count}*\n▪️ *Бонус: {bonus_status}*",
				parse_mode="MarkdownV2", reply_markup=keyboards.get_mirrors_menu_markup(_user_lang))
		elif d == "shop":
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=t('shop_caption', _user_lang),
				parse_mode="MarkdownV2", reply_markup=shop_markup)
		elif d in ("buyforadmins", "yoomoney", "tinkoff", "sberbank"):
			card_markup = types.InlineKeyboardMarkup(row_width=1)
			card_markup.add(
				types.InlineKeyboardButton("✍️ Написать @TariSmit", url='https://t.me/TariSmit'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=t('card_payment_caption', _user_lang),
				parse_mode="MarkdownV2", reply_markup=card_markup)
		elif d == "preminfo":
			await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
				caption=t('preminfo_caption', _user_lang),
				parse_mode="MarkdownV2", reply_markup=back_markup)
		elif d == "close":
			await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
		elif d == "go_to_main_menu":
			await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
			await bot_instance.send_photo(call.message.chat.id, photo=open('material/menu.png', 'rb'),
				caption=t('menu_caption', _user_lang), parse_mode="MarkdownV2", reply_markup=keyboards.get_menu(uid in admins, _user_lang))

		# ─── Пробив ───────────────────────────────────────────────────────────
		elif d == 'probiv':
			sub_active = subscribe > now_msk()
			if not sub_active:
				await bot_instance.answer_callback_query(call.id, t('err_subscribe_required', _user_lang), show_alert=True)
				return
			cancel_markup = types.InlineKeyboardMarkup()
			_cancel_text = '❌ Отмена' if _user_lang == 'ru' else '❌ Cancel'
			cancel_markup.add(types.InlineKeyboardButton(_cancel_text, callback_data='probiv_cancel'))
			await bot_instance.send_message(uid, PROBIV_HELP, parse_mode="Markdown", reply_markup=cancel_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitProbivFSM.query.state)
			await call.answer()

		elif d == 'probiv_cancel':
			await dp_instance.current_state(chat=uid, user=uid).set_state(None)
			try:
				await bot_instance.delete_message(call.message.chat.id, call.message.message_id)
			except Exception:
				pass
			await call.answer(t('action_cancelled', _user_lang))

		# ─── Мониторинг ────────────────────────────────────────────────────────
		elif d == 'media':
			await state.finish()
			_MEDIA_INFO = (
			"🎥 *Медиа-программа Brown V2*\n\nСнимай видео про Brown V2, публикуй на TikTok / YouTube / Shorts — платим за просмотры.\n\n*Выплаты:*\n• 1.000 просм. — 1.5$\n• 5.000 просм. — 5$\n• 15.000 просм. — 12$\n• 50.000 просм. — 60$\n• 100.000+ просм. — 100–200$ (индивидуально)\n\n*Платформы:* TikTok, YouTube, YouTube Shorts\n*Оплата:* реальные деньги, вручную\n\n_Отправь ссылку на видео — админ проверит и назначит выплату._"
			)
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=_MEDIA_INFO, parse_mode="Markdown", reply_markup=keyboards.get_media_markup(_user_lang))
			except Exception:
				await bot_instance.edit_message_text(_MEDIA_INFO, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=keyboards.get_media_markup(_user_lang))

		elif d == 'media_submit':
			await state.finish()
			_txt = "📤 *Отправка видео*\n\nВыбери платформу:"
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=_txt, parse_mode="Markdown", reply_markup=media_platform_markup)
			except Exception:
				await bot_instance.edit_message_text(_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=media_platform_markup)

		elif d.startswith('media_p_'):
			platform = d[len('media_p_'):]
			await state.finish()
			await state.update_data(platform=platform)
			await MediaFSM.waiting_link.set()
			_PLATFORM_NAMES = {'tiktok': 'TikTok', 'youtube': 'YouTube', 'shorts': 'YouTube Shorts'}
			pname = _PLATFORM_NAMES.get(platform, platform)
			_txt = f"🔗 *Платформа: {pname}*\n\nОтправь ссылку на видео:"
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=_txt, parse_mode="Markdown", reply_markup=back_markup)
			except Exception:
				await bot_instance.edit_message_text(_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=back_markup)

		elif d == 'media_confirm':
			fsm_data = await state.get_data()
			platform = fsm_data.get('platform', 'tiktok')
			link = fsm_data.get('link', '')
			await state.finish()
			_PLATFORM_NAMES = {'tiktok': 'TikTok', 'youtube': 'YouTube', 'shorts': 'YouTube Shorts'}
			pname = _PLATFORM_NAMES.get(platform, platform)
			pool = await db.get_pool()
			async with pool.acquire() as conn:
				_row = await conn.fetchrow(
					"INSERT INTO media_submissions (user_id, username, platform, link) VALUES ($1, $2, $3, $4) RETURNING id",
					uid, call.from_user.username or '', platform, link
				)
				sub_id = _row['id']
			uname_str = f"@{call.from_user.username}" if call.from_user.username else f"ID {uid}"
			try:
				await bot_instance.send_message(
					MEDIA_ADMIN_ID,
					f"🎥 *Новая заявка на медиа #{sub_id}*\n\n👤 Пользователь: {uname_str}\n📌 Платформа: {pname}\n🔗 Ссылка: {link}",
					parse_mode='Markdown', reply_markup=media_admin_markup(sub_id)
				)
			except Exception:
				pass
			_txt = "✅ *Заявка отправлена!*\n\nАдмин проверит видео и свяжется с вами по выплате."
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=_txt, parse_mode="Markdown", reply_markup=back_markup)
			except Exception:
				await bot_instance.edit_message_text(_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=back_markup)

		elif d == 'media_my':
			await state.finish()
			pool = await db.get_pool()
			async with pool.acquire() as conn:
				_rows = await conn.fetch(
					"SELECT id, platform, link, status, admin_comment, payout, submitted_at FROM media_submissions WHERE user_id=$1 ORDER BY submitted_at DESC LIMIT 10",
					uid
				)
			if not _rows:
				_txt = "📋 *Мои заявки*\n\nУ вас пока нет отправленных видео."
			else:
				_STATUS_ICONS = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}
				_PLATFORM_NAMES = {'tiktok': 'TikTok', 'youtube': 'YouTube', 'shorts': 'YouTube Shorts'}
				_txt = "📋 *Мои заявки:*\n\n"
				for _r in _rows:
					_icon = _STATUS_ICONS.get(_r['status'], '❔')
					_pname = _PLATFORM_NAMES.get(_r['platform'], _r['platform'])
					_txt += f"{_icon} #{_r['id']} | {_pname}\n🔗 {_r['link'][:50]}...\n"
					if _r['status'] == 'approved':
						_txt += f"   💰 Выплата: {_r['payout']}\n"
					elif _r['status'] == 'rejected' and _r['admin_comment']:
						_txt += f"   📝 Причина: {_r['admin_comment']}\n"
					_txt += "\n"
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=_txt, parse_mode="Markdown", reply_markup=back_markup)
			except Exception:
				await bot_instance.edit_message_text(_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=back_markup)

		elif d == 'media_terms':
			_txt = (
				"📜 *Условия медиа\\-программы*\n\n"
				"✅ *Обязательно в ролике:*\n"
				"└ Название проекта — Brown V2\n"
				"└ Ссылка на сайт — br\\-v2\\.top\n\n"
				"⚠️ *Проверка и санкции:*\n"
				"└ Проверяем просмотры, лайки и рост аудитории\\.\n"
				"└ При накрутке выплата не производится\\.\n"
				"└ При нарушении — блокировка бота навсегда\\.\n\n"
				"🎬 Снимайте ролики на YouTube, TikTok, Shorts\\."
			)
			_terms_back = types.InlineKeyboardMarkup(row_width=1)
			_terms_back.add(types.InlineKeyboardButton("[🔙] Назад", callback_data='media'))
			try:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=_txt, parse_mode="MarkdownV2", reply_markup=_terms_back)
			except Exception:
				await bot_instance.edit_message_text(_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="MarkdownV2", reply_markup=_terms_back)

		elif d.startswith('media_ok_'):
			if uid != MEDIA_ADMIN_ID:
				await bot_instance.answer_callback_query(call.id, t('err_admin_only', _user_lang), show_alert=True)
				return
			sub_id = int(d.split('_')[2])
			await state.update_data(media_sub_id=sub_id)
			await MediaFSM.waiting_approve_comment.set()
			await bot_instance.send_message(
				call.message.chat.id,
				f"✅ Одобрение заявки #{sub_id}\n\nОтправь комментарий и сумму выплаты в одном сообщении.\nНапример: `Отличное видео! $5`"
			)
			await bot_instance.answer_callback_query(call.id)

		elif d.startswith('media_rej_'):
			if uid != MEDIA_ADMIN_ID:
				await bot_instance.answer_callback_query(call.id, t('err_admin_only', _user_lang), show_alert=True)
				return
			sub_id = int(d.split('_')[2])
			await state.update_data(media_sub_id=sub_id)
			await MediaFSM.waiting_reject_reason.set()
			await bot_instance.send_message(
				call.message.chat.id,
				f"❌ Отклонение заявки #{sub_id}\n\nОтправь причину отклонения:"
			)
			await bot_instance.answer_callback_query(call.id)

		elif d == 'monitor_menu' or d.startswith('monitor_menu_p_'):
			if subscribe < now_msk():
				await bot_instance.answer_callback_query(call.id, t('err_monitor_sub', _user_lang), show_alert=True)
				return
			page = int(d.split('_p_')[1]) if '_p_' in d else 0
			PER_PAGE = 5
			monitors = await db.get_user_monitors(uid)
			active = [m for m in monitors if m['active']]
			limit = 5 if premium else 3
			now_dt = now_msk()

			lines = []
			for m in monitors:
				expires = m['expires_at']
				if isinstance(expires, str):
					expires = datetime.strptime(expires[:19], "%Y-%m-%d %H:%M:%S")
				if m['active']:
					status_icon = "🟢" if m['status'] == 'alive' else "🔴"
					time_left = expires - now_dt
					h = max(0, int(time_left.total_seconds() // 3600))
					mins = max(0, int((time_left.total_seconds() % 3600) // 60))
					lines.append(f"{status_icon} `{m['target'][:45]}` — {h}ч {mins}м осталось")
				else:
					status_icon = "🔴" if m['status'] == 'dead' else "⚫"
					lines.append(f"{status_icon} `{m['target'][:45]}` — завершён")

			total = len(lines)
			total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
			page = max(0, min(page, total_pages - 1))
			page_lines = lines[page * PER_PAGE:(page + 1) * PER_PAGE]

			text = f"🔍 *Мониторинг BR V2*\n\n*Активных:* {len(active)}/{limit}\n\n"
			if page_lines:
				text += "\n".join(page_lines)
				if total_pages > 1:
					text += f"\n\n_Стр. {page + 1}/{total_pages}_"
			else:
				text += "_Нет активных мониторов_\n\nДобавьте цель после отправки репортов"

			markup = types.InlineKeyboardMarkup(row_width=2)
			nav_btns = []
			if page > 0:
				nav_btns.append(types.InlineKeyboardButton("◀️", callback_data=f'monitor_menu_p_{page - 1}'))
			if page < total_pages - 1:
				nav_btns.append(types.InlineKeyboardButton("▶️", callback_data=f'monitor_menu_p_{page + 1}'))
			if nav_btns:
				markup.add(*nav_btns)
			markup.add(types.InlineKeyboardButton("[🔙] Назад", callback_data='back'))
			try:
				await bot_instance.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=text, parse_mode="Markdown", reply_markup=markup
				)
			except Exception:
				await bot_instance.edit_message_text(
					text, chat_id=call.message.chat.id, message_id=call.message.message_id,
					parse_mode="Markdown", reply_markup=markup
				)

		elif d.startswith('monitor_mute_'):
			try:
				monitor_id = int(d[len('monitor_mute_'):])
			except ValueError:
				await bot_instance.answer_callback_query(call.id, t('monitor_error', _user_lang), show_alert=True)
				return
			ok = await db.set_monitor_silent(monitor_id, uid, True)
			if ok:
				await bot_instance.answer_callback_query(call.id, t('monitor_notify_off', _user_lang), show_alert=True)
				try:
					await bot_instance.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
				except Exception:
					pass
			else:
				await bot_instance.answer_callback_query(call.id, t('monitor_not_found', _user_lang), show_alert=True)

		elif d == 'monitor_limit':
			await bot_instance.answer_callback_query(
				call.id,
				f"❌ Лимит мониторов достигнут! ({'5' if premium else '3'} максимум)",
				show_alert=True
			)

		elif d.startswith('monitor_add_'):
			if subscribe < now_msk():
				await bot_instance.answer_callback_query(call.id, t('err_monitor_sub', _user_lang), show_alert=True)
				return
			import urllib.parse
			raw_target = d[len('monitor_add_'):]
			target = urllib.parse.unquote(raw_target)

			limit = 5 if premium else 3
			active_count = await db.get_user_active_monitors_count(uid)

			if active_count >= limit:
				await bot_instance.answer_callback_query(
					call.id, f"❌ Лимит {limit} мониторов достигнут!", show_alert=True
				)
				return

			if await db.is_target_already_monitored(uid, target):
				await bot_instance.answer_callback_query(
					call.id, "❌ Эта цель уже мониторится!", show_alert=True
				)
				return

			if await db.was_target_monitored_before(uid, target):
				await bot_instance.answer_callback_query(
					call.id, "❌ Эту цель уже мониторили — повторный мониторинг запрещён!", show_alert=True
				)
				return

			# Срок: 12ч обычным, 24ч премиум
			hours = 24 if premium else 12
			expires_at = now_msk() + timedelta(hours=hours)

			await db.add_monitor(uid, target, expires_at)
			await bot_instance.answer_callback_query(call.id, t('monitor_started', _user_lang), show_alert=False)

			markup = types.InlineKeyboardMarkup(row_width=1)
			_mon_label = '🔍 Мои мониторы' if _user_lang == 'ru' else '🔍 My monitors'
			markup.add(types.InlineKeyboardButton(_mon_label, callback_data='monitor_menu'))
			markup.add(types.InlineKeyboardButton(t('btn_main_menu', _user_lang), callback_data='go_to_main_menu'))

			await bot_instance.send_message(
				uid,
				f"🔍 *Мониторинг запущен!*\n\n"
				f"🎯 *Цель:* `{target}`\n"
				f"⏱ *Срок:* {hours} часов\n"
				f"🟢 *Статус:* Живой\n\n"
				f"_Вы получите уведомление если цель будет снесена_",
				parse_mode="Markdown",
				reply_markup=markup
			)
			_is_hid_mon = await db.get_is_hidden(uid)
			_log_uid_mon = "скрыт" if _is_hid_mon else str(uid)
			_log_uname_mon = "скрыт" if _is_hid_mon else f"@{username}"
			await bot.send_message(
				bot_logs,
				f"🔍 *Новый монитор* `{_log_uid_mon}` ({_log_uname_mon})\n"
				f"*Цель:* `{target}` на {hours}ч",
				parse_mode="Markdown"
			)
		elif d == 'add_subsribe' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Выдать подписку»")
			await bot_instance.send_message(call.message.chat.id, '🎱 *Выдача подписки*\n*└─Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AddSubscribeFSM.user_id.state)
		elif d == 'toggle_maintenance' and uid in admins:
			await _log_admin_action(uid, username, f"Переключил тех. работы")
			new_val = not _get_maintenance()
			_set_maintenance(new_val)
			status_text = "🔧 *Тех. работы включены*" if new_val else "✅ *Тех. работы выключены*"
			new_btn_text = "✅ Выключить тех. работы" if new_val else "🔧 Включить тех. работы"
			try:
				markup = call.message.reply_markup
				# Перестраиваем клавиатуру с обновлённой кнопкой
				new_markup = types.InlineKeyboardMarkup(row_width=2)
				for row in markup.inline_keyboard:
					row_btns = []
					for btn in row:
						if btn.callback_data == 'toggle_maintenance':
							row_btns.append(types.InlineKeyboardButton(new_btn_text, callback_data='toggle_maintenance'))
						else:
							row_btns.append(btn)
					new_markup.row(*row_btns)
				await bot_instance.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=new_markup)
			except Exception:
				pass
			await bot_instance.answer_callback_query(call.id, status_text.replace('*','').replace('\n',' '), show_alert=True)
		elif d == 'clear_subscribe' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Забрать подписку»")
			await bot_instance.send_message(call.message.chat.id, '🎱 *Сброс подписки*\n*└─Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(ClearSubscribeFSM.user_id.state)
		elif d == 'add_prem' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Выдать премиум»")
			await bot_instance.send_message(call.message.chat.id, '🎱 *Выдача премиума*\n*└─Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AddPremFSM.user_id.state)
		elif d == 'clear_prem' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Забрать премиум»")
			await bot_instance.send_message(call.message.chat.id, '🎱 *Сброс премиума*\n*└─Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(ClearPremFSM.user_id.state)
		elif d == 'send_all' and uid in admins:
			await bot_instance.send_message(call.message.chat.id, '🎱 *Рассылка*\n*└─Введите текст:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTextZFSM.text.state)
		elif d == 'block_user_admin' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Заблокировать»")
			await bot_instance.send_message(call.message.chat.id, '🚫 *Блокировка*\n*└─Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(BlockUserFSM.user_id.state)
		elif d == 'unblock_user_admin' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Разблокировать»")
			await bot_instance.send_message(call.message.chat.id, '✅ *Разблокировка*\n*└─Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(UnblockUserFSM.user_id.state)
		elif d == 'admin_create_promo' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Создать промокод»")
			await bot_instance.send_message(
				call.message.chat.id,
				'💎 *Создание промокода*\n\n*└─ Выберите тип:*',
				parse_mode="Markdown",
				reply_markup=keyboards.promo_type_markup
			)

		elif d == 'delete_user_admin' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Удалить из БД»")
			await bot_instance.send_message(call.message.chat.id, '🗑 *Удаление из базы*\n*└─Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(DeleteUserFSM.user_id.state)

		elif d == 'admin_check_user' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Проверить пользователя»")
			await bot_instance.send_message(call.message.chat.id, '🔍 *Проверить пользователя*\n*└─ Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(CheckUserFSM.query.state)

		elif d == 'admin_send_msg' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Отправить сообщение»")
			await bot_instance.send_message(call.message.chat.id, '✉️ *Отправить сообщение пользователю*\n*└─ Введите ID или @username:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AdminSendMsgFSM.target.state)

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
				await bot_instance.answer_callback_query(call.id, t('no_more_users', _user_lang), show_alert=False)
				return

			lines = [f"👥 *Пользователи* (стр. {page+1}/{total_pages})\n"]
			now = now_msk()
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
				btns.append(types.InlineKeyboardButton(t('btn_prev_admin', _user_lang), callback_data=f'users_list_{page-1}'))
			if (page + 1) < total_pages:
				btns.append(types.InlineKeyboardButton(t('btn_next_admin', _user_lang), callback_data=f'users_list_{page+1}'))
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
				await bot_instance.answer_callback_query(call.id, t('no_mirrors_admin', _user_lang), show_alert=False)
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
			await _log_admin_action(uid, username, "Нажал «Выдать репорты»")
			await bot_instance.send_message(call.message.chat.id, '🎯 *Выдача репортов*\n*└─ Введите ID пользователя:*', parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AdminAddReportsFSM.user_id.state)

		elif d == 'admin_remove_reports' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Забрать репорты»")
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
				parse_mode="Markdown", reply_markup=keyboards.get_referral_markup(_user_lang)
			)

		elif d == 'exchange_refs':
			ref_count = await db.get_referral_count(uid)
			if ref_count < 10:
				await bot_instance.answer_callback_query(call.id, t('refs_not_enough', _user_lang, count=ref_count), show_alert=True)
			else:
				# Атомарное снятие — защита от race condition
				success = await db.spend_referrals(uid, 10)
				if not success:
					await bot_instance.answer_callback_query(call.id, t('refs_not_enough', _user_lang, count=0), show_alert=True)
				else:
					new_date = (now_msk() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
					await db.set_subscribe(uid, new_date)
					remaining = ref_count - 10
					await bot_instance.answer_callback_query(call.id, t('refs_exchanged', _user_lang), show_alert=True)
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
						parse_mode="Markdown", reply_markup=keyboards.get_referral_markup(_user_lang)
					)
					await bot.send_message(bot_logs, f"🔄 `{uid}` обменял 10 рефералов на 1 день", parse_mode="Markdown")

		# ─── Бесплатно / Зеркала (старый alias, редирект в mirrors_menu) ────────
		elif d == 'free_menu':
			mirror_count = await db.count_user_mirrors(uid)
			bonus_given = await db.get_mirror_bonus_given(uid)
			bonus_status = "✅ Получен" if bonus_given else (f"🔒 Нужно {2 - mirror_count} зеркала" if mirror_count < 2 else "⬆️ Доступен — создай зеркало")
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('mirrors_caption', _user_lang) + f"\n\n▪️ *Зеркал создано: {mirror_count}*\n▪️ *Бонус: {bonus_status}*",
				parse_mode="MarkdownV2", reply_markup=keyboards.get_mirrors_menu_markup(_user_lang)
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
				await bot_instance.answer_callback_query(call.id, t('no_mirrors_user', _user_lang), show_alert=True)
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
				types.InlineKeyboardButton("[🔙] Назад", callback_data='bonuses_menu'),
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
			from mirror_manager import get_running_tokens
			# Берём только реально запущенные зеркала
			running_tokens = set(get_running_tokens())
			all_mirrors = await db.get_all_mirrors()
			# Фильтруем — только те у которых токен сейчас активен
			active_mirrors = [m for m in all_mirrors if m['token'] in running_tokens]
			if not active_mirrors:
				await bot_instance.answer_callback_query(call.id, t('no_mirrors_pub', _user_lang), show_alert=True)
				return
			shown = _random.sample(active_mirrors, min(5, len(active_mirrors)))
			lines = ["🪞 *Зеркала Brown V2*\n\n*└─ 5 случайных рабочих зеркал:*\n"]
			for m in shown:
				lines.append(f"• `{m['bot_username']}`")
			refresh_markup = types.InlineKeyboardMarkup(row_width=1)
			refresh_markup.add(
				types.InlineKeyboardButton("🔄 Обновить", callback_data='public_mirrors'),
				types.InlineKeyboardButton("[🔙] Назад", callback_data='bonuses_menu'),
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
			now = now_msk()
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
					parse_mode="Markdown", reply_markup=keyboards.get_wheel_markup(_user_lang)
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
					parse_mode="Markdown", reply_markup=keyboards.get_wheel_markup(_user_lang)
				)

		elif d == 'spin_wheel':
			last_spin = await db.get_wheel_last_spin(uid)
			now = now_msk()

			# Проверяем — выиграна ли подписка/премиум и она ещё активна
			last_prize = await db.get_wheel_prize(uid)
			if last_prize in ("forever", "sub_1d", "premium"):
				if last_prize == "premium" and premium == 1:
					await bot_instance.answer_callback_query(
						call.id, t('wheel_block_premium', _user_lang), show_alert=True
					)
					return
				if last_prize in ("forever", "sub_1d") and subscribe > now:
					await bot_instance.answer_callback_query(
						call.id, t('wheel_block_sub', _user_lang), show_alert=True
					)
					return

			if last_spin and (now - last_spin).total_seconds() < 6 * 3600:
				remaining = timedelta(seconds=6*3600) - (now - last_spin)
				h = int(remaining.total_seconds() // 3600)
				m = int((remaining.total_seconds() % 3600) // 60)
				await bot_instance.answer_callback_query(call.id, t('wheel_cd', _user_lang, h=h, m=m), show_alert=True)
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

		# ─── Кейсы ─────────────────────────────────────────────────────────────
		elif d == 'case_menu':
			count = await db.get_unopened_cases(uid)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"📦 *Кейс BR V2*\n\n"
					"*Внутри кейса:*\n"
					"🎯 5 бесплатных репортов\n"
					"⚡ Подписка на 1 день\n"
					"💎 Подписка на 30 дней\n"
					"👑 Премиум навсегда\n\n"
					f"*└─ Ваших кейсов: {count}*\n\n"
					"*Цена: 2$ / 200₽*"
				),
				parse_mode="Markdown",
				reply_markup=keyboards.case_menu_markup
			)

		elif d == 'case_buy':
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"📦 *Покупка кейса — 2$ / 200₽*\n\n"
					"*Выберите способ оплаты:*\n\n"
					"💲 *USDT* — через CryptoPay\n"
					"🇷🇺 *СБП* — автоматически"
				),
				parse_mode="Markdown", reply_markup=keyboards.case_buy_markup
			)

		elif d == 'case_buy_sbp':
			import urllib.parse as _urlparse
			label = f"case_{uid}"
			targets = _urlparse.quote("Кейс BR V2", safe='')
			ym_url = (
				f"https://yoomoney.ru/quickpay/confirm.xml"
				f"?receiver={_YM_WALLET}"
				f"&quickpay-form=shop"
				f"&targets={targets}"
				f"&sum=200"
				f"&label={label}"
			)
			short_url = await _create_pay_link(ym_url)
			sbp_case_markup = types.InlineKeyboardMarkup(row_width=1)
			sbp_case_markup.add(
				types.InlineKeyboardButton("💳 Оплатить 200₽", url=short_url),
				types.InlineKeyboardButton("✅ Оплатил", callback_data=f'case_sbp_paid_{uid}'),
				types.InlineKeyboardButton("[🔙] Назад", callback_data='case_buy'),
			)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"📦 *Покупка кейса*\n\n"
					"*Цена: 200₽ (СБП)*\n"
					"*└─ После оплаты нажмите «Оплатил»*\n"
					"*└─ Кейс будет выдан в течение 15 минут*"
				),
				parse_mode="Markdown", reply_markup=sbp_case_markup
			)

		elif d == 'case_buy_usdt':
			invoice = await asyncio.to_thread(crypto.create_invoice, asset='USDT', amount=2)
			pay_url = invoice['pay_url']
			invoice_id = invoice['invoice_id']
			pay_check = types.InlineKeyboardMarkup(row_width=1)
			pay_check.add(
				types.InlineKeyboardButton("💸 Оплатить 2 USDT", url=pay_url),
				types.InlineKeyboardButton("🔍 Проверить оплату", callback_data=f'case_check_{invoice_id}'),
				keyboards.back
			)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"📦 *Покупка кейса*\n\n"
					"*Цена: 2 USDT*\n"
					"*└─ После оплаты нажмите «Проверить оплату»*"
				),
				parse_mode="Markdown", reply_markup=pay_check
			)

		elif d.startswith('case_check_'):
			invoice_id = d.replace('case_check_', '')
			if await db.is_case_invoice_used(invoice_id):
				await bot_instance.answer_callback_query(call.id, t('case_already', _user_lang), show_alert=True)
				return
			try:
				inv = await asyncio.to_thread(crypto.get_invoices, invoice_ids=invoice_id)
				if inv['items'][0]['status'] != 'paid':
					await bot_instance.answer_callback_query(call.id, t('case_no_payment', _user_lang), show_alert=True)
					return
			except Exception:
				await bot_instance.answer_callback_query(call.id, t('case_err', _user_lang), show_alert=True)
				return
			await db.add_case(uid, invoice_id)
			count = await db.get_unopened_cases(uid)
			await bot.send_message(bot_logs, f"🎁 `{uid}` (@{username}) купил кейс", parse_mode="Markdown")
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"✅ *Кейс куплен!*\n\n"
					f"*└─ Ваших кейсов: {count}*\n\n"
					f"*Нажмите «Открыть кейс» чтобы узнать свой приз!*"
				),
				parse_mode="Markdown", reply_markup=keyboards.get_case_menu_markup(_user_lang)
			)

		elif d == 'case_open':
			count = await db.get_unopened_cases(uid)
			if count == 0:
				await bot_instance.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						"📦 *У вас нет кейсов*\n\n"
						"*└─ Купите кейс за 2$ чтобы испытать удачу!*"
					),
					parse_mode="Markdown", reply_markup=keyboards.get_case_menu_markup(_user_lang)
				)
				return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"📦 *Открыть кейс?*\n\n"
					f"*└─ Кейсов: {count}*\n\n"
					"*Внутри вас ждёт один из призов:*\n"
					"🎯 5 бесплатных репортов\n"
					"⚡ Подписка на 1 день\n"
					"💎 Подписка на 30 дней\n"
					"👑 Премиум навсегда"
				),
				parse_mode="Markdown", reply_markup=keyboards.case_open_markup
			)

		elif d == 'case_open_confirm':
			opened = await db.open_case(uid)
			if not opened:
				await bot_instance.answer_callback_query(call.id, t('case_no_cases', _user_lang), show_alert=True)
				return
			# Розыгрыш
			import random as _random
			roll = _random.randint(1, 100)
			if roll <= 60:
				prize_key = "reports_5"
			elif roll <= 80:
				prize_key = "sub_1d"
			elif roll <= 98:
				prize_key = "sub_30d"
			elif roll <= 100:
				prize_key = "premium"
			else:
				prize_key = "nothing"

			if prize_key == "reports_5":
				await db.add_free_reports(uid, 5)
				prize_text = "🎯 *+5 бесплатных репортов!*"
				log_prize = "5 репортов"
			elif prize_key == "sub_1d":
				new_date = (now_msk() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
				await db.set_subscribe(uid, new_date)
				prize_text = "⚡ *Подписка на 1 день!*"
				log_prize = "подписка 1д"
			elif prize_key == "sub_30d":
				new_date = (now_msk() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
				await db.set_subscribe(uid, new_date)
				prize_text = "💎 *Подписка на 30 дней!*"
				log_prize = "подписка 30д"
			elif prize_key == "premium":
				await db.set_premium(uid, 1)
				prize_text = "👑 *Премиум навсегда!*"
				log_prize = "премиум"
			else:
				prize_text = "😔 *К сожалению, в этот раз ничего...*"
				log_prize = "ничего"

			count = await db.get_unopened_cases(uid)
			await bot.send_message(bot_logs,
				f"🎁 `{uid}` (@{username}) открыл кейс → {log_prize}",
				parse_mode="Markdown")
			markup = types.InlineKeyboardMarkup(row_width=1)
			if count > 0:
				markup.add(types.InlineKeyboardButton("📦 Открыть ещё", callback_data='case_open_confirm'))
			markup.add(types.InlineKeyboardButton("🎁 Купить ещё", callback_data='case_buy'))
			markup.add(types.InlineKeyboardButton("[🔙] Главное меню", callback_data='go_to_main_menu'))
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					f"🎁 *Кейс открыт!*\n\n"
					f"🎰 *Ваш приз:*\n{prize_text}\n\n"
					f"*Кейсов осталось: {count}*"
				),
				parse_mode="Markdown", reply_markup=markup
			)

		elif d == 'admin_add_case' and uid in admins:
			await _log_admin_action(uid, username, "Нажал «Выдать кейс»")
			await bot_instance.send_message(uid,
				'🎁 *Выдача кейса*\n*└─ Введите ID пользователя:*',
				parse_mode="Markdown")
			await dp_instance.current_state(chat=uid, user=uid).set_state(AdminAddCaseFSM.user_id.state)

		def sub_expired():
			return subscribe < now_msk()
		def bot_off():
			return bot_status == 0

		# Список методов требующих подтверждения мануала
		METHODS_REQUIRING_CONFIRM = {
			"web_method", "mail_method", "botnet_method", "prem_botnet_method",
			"bot_method", "channel_method", "aureport_method",
			"tida_method", "bank_method", "telegraph_method",
			"universal_method",
		}

		# ─── Шаг 1: показываем предупреждение при нажатии на метод ──────────
		if d in METHODS_REQUIRING_CONFIRM:
			already_confirmed = await db.is_method_manual_confirmed(uid, d)
			if not already_confirmed:
				await bot_instance.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=t('manual_warn', _user_lang),
					parse_mode="MarkdownV2",
					reply_markup=keyboards.manual_confirm_step1(d, _user_lang)
				)
				return

		# ─── Шаг 2: "Ознакомлен" → второй экран ─────────────────────────────
		if d.startswith('manual_step2_'):
			method = d[len('manual_step2_'):]
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('manual_confirm2', _user_lang),
				parse_mode="Markdown",
				reply_markup=keyboards.manual_confirm_step2(method, _user_lang)
			)
			return

		# ─── Шаг 3: "100% прочитал" → запускаем метод ────────────────────────
		if d.startswith('manual_confirm_'):
			d = d[len('manual_confirm_'):]  # подменяем d на реальный метод
			await db.set_method_manual_confirmed(uid, d)

		if d == "web_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_pay', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if premium == 0: await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_premium', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid in last_used_web and uid not in admins and uid not in no_kd and (now_msk() - last_used_web[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (now_msk() - last_used_web[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_wait', _user_lang, m=rem.seconds//60, s=rem.seconds%60), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await call.message.answer(t('web_enter_text', _user_lang), parse_mode="Markdown", reply_markup=panel_back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTextFSM.text.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "mail_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_pay', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if premium == 0: await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_premium', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid in last_used_mail and uid not in admins and uid not in no_kd and (now_msk() - last_used_mail[uid]) < timedelta(minutes=300):
				rem = timedelta(minutes=300) - (now_msk() - last_used_mail[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_wait_min', _user_lang, m=rem.seconds//60), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await call.message.answer(t('mail_enter_topic', _user_lang), parse_mode="Markdown", reply_markup=panel_back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitMailTopicFSM.topic.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "botnet_method":
			free_reports = await db.get_free_reports(uid)
			if sub_expired() and free_reports == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_pay_or_free', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid in last_used_botnet and uid not in admins and uid not in no_kd and (now_msk() - last_used_botnet[uid]) < timedelta(minutes=5):
				rem = timedelta(minutes=5) - (now_msk() - last_used_botnet[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_wait', _user_lang, m=rem.seconds//60, s=rem.seconds%60), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await bot_instance.send_message(call.message.chat.id, t('botnet_enter_link', _user_lang), parse_mode="Markdown", reply_markup=panel_back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitLinkFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		elif d == "prem_botnet_method":
			if sub_expired(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_pay', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if premium == 0: await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_premium', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if bot_off(): await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid in last_used_botnet2 and uid not in admins and uid not in no_kd and (now_msk() - last_used_botnet2[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (now_msk() - last_used_botnet2[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_wait_min', _user_lang, m=rem.seconds//60), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await bot_instance.send_message(call.message.chat.id, t('botnet_enter_link', _user_lang), parse_mode="Markdown", reply_markup=panel_back_markup)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitLinkPREMFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		# ─── Бот-метод ────────────────────────────────────────────────────────
		elif d == "bot_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid not in admins and sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_subscribe', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid not in admins and uid not in no_kd and uid in last_used_bot_snos and (now_msk() - last_used_bot_snos[uid]) < timedelta(hours=1):
				rem = timedelta(hours=1) - (now_msk() - last_used_bot_snos[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('err_wait_hm', _user_lang, h=h, m=m), parse_mode="Markdown", reply_markup=panel_back_markup)
				return
			if uid not in admins and uid not in no_kd and uid in last_used_bot_snos_fast and (now_msk() - last_used_bot_snos_fast[uid]) < timedelta(minutes=5):
				rem = timedelta(minutes=5) - (now_msk() - last_used_bot_snos_fast[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('err_wait_ms', _user_lang, m=rem.seconds // 60, s=rem.seconds % 60), parse_mode="Markdown", reply_markup=panel_back_markup)
				return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitBotLinkFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(bot_reason='personal', _bot_token=_instance_token)
			await bot_instance.send_message(
				call.message.chat.id,
				t('bot_method_prompt', _user_lang),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)

		# ─── Канал-метод ──────────────────────────────────────────────────────
		elif d == "channel_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			free_reports_ch = await db.get_free_reports(uid)
			if sub_expired() and free_reports_ch == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_pay_or_free', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('channel_method_caption', _user_lang),
				parse_mode="Markdown", reply_markup=keyboards.get_channel_reason_markup(_user_lang)
			)

		elif d in ("ch_reason_personal", "ch_reason_spam", "ch_reason_adult", "ch_reason_children", "ch_reason_violence", "ch_reason_other"):
			reason_map = {
				"ch_reason_personal": ("personal", t('ch_reason_personal', _user_lang)),
				"ch_reason_spam":     ("spam",     t('ch_reason_spam', _user_lang)),
				"ch_reason_adult":    ("adult",    t('ch_reason_adult', _user_lang)),
				"ch_reason_children": ("children", t('ch_reason_children', _user_lang)),
				"ch_reason_violence": ("violence", t('ch_reason_violence', _user_lang)),
				"ch_reason_other":    ("other",    t('ch_reason_other', _user_lang)),
			}
			reason_key, reason_label = reason_map[d]
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitChannelFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(ch_reason=reason_key, _bot_token=_instance_token)
			await bot_instance.send_message(
				call.message.chat.id,
				t('channel_enter_link', _user_lang, reason=reason_label),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)

		# ─── Ручной метод ─────────────────────────────────────────────────────
		elif d == "manual_method":
			manual_markup = types.InlineKeyboardMarkup(row_width=1)
			manual_markup.add(
				types.InlineKeyboardButton("✍️ Написать @TariSmit", url='https://t.me/TariSmit'),
				keyboards.get_back_btn(_user_lang)
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
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_subscribe', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid not in admins and uid not in no_kd and uid in last_used_aureport and (now_msk() - last_used_aureport[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (now_msk() - last_used_aureport[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('err_wait', _user_lang, m=rem.seconds//60, s=rem.seconds%60), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitAuReportFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('aureport_prompt', _user_lang),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)

		# ─── TIDA ─────────────────────────────────────────────────────────────
		elif d == "tida_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_subscribe', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid not in admins and uid not in no_kd and uid in last_used_tida and (now_msk() - last_used_tida[uid]) < timedelta(minutes=30):
				rem = timedelta(minutes=30) - (now_msk() - last_used_tida[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('err_wait', _user_lang, m=rem.seconds//60, s=rem.seconds%60), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTidaFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('tida_prompt', _user_lang),
				parse_mode="Markdown",
				reply_markup=panel_back_markup
			)

		elif d.startswith("tida_target_"):
			# Тип цели теперь определяется автоматически — этот блок оставлен для совместимости
			await call.answer()

		elif d == "tida_text_confirm":
			await call.answer()
			pending = _tida_pending.get(uid, {})
			if not pending:
				await bot_instance.send_message(uid, "❌ *Данные устарели, начните заново*", parse_mode="Markdown", reply_markup=main_menu)
				return
			tida_link = pending['link']
			tida_text = pending['text']
			tida_username = pending.get('username', 'None')
			_bot_token = pending.get('bot_token')
			_is_mirror = bool(_bot_token and _bot_token != config.TOKEN)
			_bot = Bot(token=_bot_token) if _is_mirror else bot
			if uid not in admins:
				last_used_tida[uid] = now_msk()
			await _bot.send_message(uid,
				f'🟣 *Запускаю TIDA на* `{tida_link}`*...*',
				parse_mode="Markdown")
			try:
				await main_tida(tida_link, tida_text, uid, tida_username, notify_bot=_bot)
				try: await db.log_attack(uid, tida_link, "tida")
				except Exception as e: print(f"[HISTORY] tida-ai log error: {e}", flush=True)
				# Предлагаем мониторинг
				await _offer_monitor(_bot, uid, tida_link, premium, subscribe)
			except Exception as e:
				print(f"[TIDA-AI] ОШИБКА: {e}", flush=True)
				await _bot.send_message(uid, f'❌ *Ошибка TIDA:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
			finally:
				_tida_pending.pop(uid, None)

		elif d == "tida_text_change":
			await call.answer()
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTidaFSM.text.state)
			await bot_instance.send_message(uid,
				'✏️ *Введите новый текст жалобы:*\n_(на английском языке)_\n\n[📋 Шаблоны текстов](https://t.me/+zTWywoULseYzMWU0)',
				parse_mode="Markdown", reply_markup=panel_back_markup)

		elif d == "tida_choose_ai_desc":
			await call.answer()
			fsm_data = await dp_instance.current_state(user=uid).get_data()
			target_type = fsm_data.get('tida_target', 'channel')
			_tida_names = {
				"account": t('tida_target_account', _user_lang),
				"bot": t('tida_target_bot', _user_lang),
				"chat": t('tida_target_chat', _user_lang),
				"channel": t('tida_target_channel', _user_lang),
			}
			target_label = _tida_names.get(target_type, target_type)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTidaFSM.ai_desc.state)
			await bot_instance.send_message(uid,
				t('tida_describe_violation', _user_lang, target=target_label),
				parse_mode="Markdown", reply_markup=panel_back_markup)

		elif d == "tida_choose_manual":
			await call.answer()
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTidaFSM.text.state)
			await bot_instance.send_message(uid,
				t('tida_enter_text', _user_lang),
				parse_mode="Markdown", reply_markup=panel_back_markup)

		elif d.startswith("tida_ai_link_") or d.startswith("tida_ai_desc_") or d.startswith("tida_manual_"):
			# Старые кнопки — перенаправляем
			await call.answer()
			fsm_data = await dp_instance.current_state(user=uid).get_data()
			target_type = d.split("_")[-1]
			if target_type not in ("account", "bot", "chat", "channel"):
				target_type = fsm_data.get('tida_target', 'channel')
			await dp_instance.current_state(user=uid).update_data(tida_target=target_type)
			if d.startswith("tida_manual_"):
				await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTidaFSM.text.state)
				await bot_instance.send_message(uid,
					t('tida_enter_text', _user_lang),
					parse_mode="Markdown", reply_markup=panel_back_markup)
			else:
				_tida_names2 = {
					"account": t('tida_target_account', _user_lang),
					"bot": t('tida_target_bot', _user_lang),
					"chat": t('tida_target_chat', _user_lang),
					"channel": t('tida_target_channel', _user_lang),
				}
				target_label = _tida_names2.get(target_type, target_type)
				await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTidaFSM.ai_desc.state)
				await bot_instance.send_message(uid,
					t('tida_describe_violation', _user_lang, target=target_label),
					parse_mode="Markdown", reply_markup=panel_back_markup)

		# ─── DSA Report ───────────────────────────────────────────────────────
		elif d == "dsa_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_subscribe', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if premium == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_premium', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid not in admins and uid not in no_kd and uid in last_used_dsa and (now_msk() - last_used_dsa[uid]) < timedelta(hours=1):
				rem = timedelta(hours=1) - (now_msk() - last_used_dsa[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('err_wait_hm', _user_lang, h=h, m=m), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitDsaFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('dsa_link_prompt', _user_lang),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)

		# ─── Telegraph снос ──────────────────────────────────────────────────────
		elif d == "telegraph_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_subscribe', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if premium == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_premium', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid not in admins and uid not in no_kd and uid in last_used_telegraph and (now_msk() - last_used_telegraph[uid]) < timedelta(minutes=15):
				rem = timedelta(minutes=15) - (now_msk() - last_used_telegraph[uid])
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('err_wait', _user_lang, m=rem.seconds//60, s=rem.seconds%60), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTelegraphFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"📄 *Telegraph снос*\n\n"
					"*└─ Введите ссылку на статью:*\n\n"
					"`https://telegra.ph/...`"
				),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)

		# ─── Telegraph — подтверждение текста ────────────────────────────────────
		elif d == "telegraph_confirm":
			await call.answer()
			fsm_data = await dp_instance.current_state(user=uid).get_data()
			article_url = fsm_data.get("telegraph_url", "")
			subject = fsm_data.get("telegraph_subject", "")
			body = fsm_data.get("telegraph_body", "")
			_bot_token = fsm_data.get("_bot_token")
			_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
			_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
			await dp_instance.current_state(chat=uid, user=uid).finish()
			if uid not in admins:
				last_used_telegraph[uid] = now_msk()
			await _bot.send_message(uid,
				f'📄 *Запускаю Telegraph снос...*\n'
				f'*└─ Отправляем 12 жалоб*',
				parse_mode="Markdown")
			try:
				await main_telegraph_snos(article_url, uid, username, custom_text=body, custom_subject=subject, notify_bot=_bot)
				try: await db.log_attack(uid, article_url, "telegraph")
				except Exception as e: print(f"[HISTORY] telegraph-cb log error: {e}", flush=True)
			except Exception as e:
				print(f"[TELEGRAPH] ОШИБКА: {e}", flush=True)
				await _bot.send_message(uid, f'❌ *Ошибка:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
			finally:
				if _is_mirror_bot:
					try:
						s = await _bot.get_session(); await s.close()
					except Exception: pass

		# ─── Telegraph — пользователь хочет свой текст ───────────────────────────
		elif d == "telegraph_custom":
			await call.answer()
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTelegraphFSM.custom_text.state)
			await bot_instance.send_message(uid,
				"✏️ *Введите свой текст письма:*\n\n"
				"_Текст будет отправлен на все 3 адреса Telegram_",
				parse_mode="Markdown", reply_markup=panel_back_markup)

		# ─── DSA причины ──────────────────────────────────────────────────────
		elif d.startswith("dsa_r_") and await dp_instance.current_state(chat=uid, user=uid).get_state() == WaitDsaFSM.reason.state:
			await call.answer()
			from dsa_snos import DSA_REASONS, HAS_SUBCATEGORY
			reason_key = d[6:]  # убираем "dsa_r_"
			if reason_key not in DSA_REASONS:
				return
			await dp_instance.current_state(user=uid).update_data(dsa_reason=reason_key)
			reason_label = DSA_REASONS[reason_key][0]

			if reason_key in HAS_SUBCATEGORY:
				# Показываем подкатегории
				sub_markup = {
					"illegal_goods": keyboards.dsa_sub_illegal_goods,
					"illegal_adult": keyboards.dsa_sub_illegal_adult,
					"personal_data": keyboards.dsa_sub_personal_data,
					"scam": keyboards.dsa_sub_scam,
				}[reason_key]
				await dp_instance.current_state(chat=uid, user=uid).set_state(WaitDsaFSM.sub_reason.state)
				await bot_instance.send_message(uid,
					f'🇪🇺 *DSA Report*\n\n*Причина:* {reason_label}\n\n*Выберите подкатегорию:*',
					parse_mode="Markdown", reply_markup=sub_markup)
			else:
				# Сразу к генерации текста
				await dp_instance.current_state(user=uid).update_data(dsa_sub="")
				await dp_instance.current_state(chat=uid, user=uid).set_state(WaitDsaFSM.text_confirm.state)
				await _dsa_generate_and_show(uid, bot_instance, dp_instance, state)

		elif d.startswith("dsa_s_") and await dp_instance.current_state(chat=uid, user=uid).get_state() == WaitDsaFSM.sub_reason.state:
			await call.answer()
			sub_key = d[6:]  # убираем "dsa_s_"
			await dp_instance.current_state(user=uid).update_data(dsa_sub=sub_key)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitDsaFSM.text_confirm.state)
			await _dsa_generate_and_show(uid, bot_instance, dp_instance, state)

		elif d == "dsa_text_confirm":
			await call.answer()
			# Пользователь принял сгенерированный текст
			fsm_data = await dp_instance.current_state(user=uid).get_data()
			await dp_instance.current_state(chat=uid, user=uid).finish()
			await _dsa_launch(uid, bot_instance, fsm_data, state)

		elif d == "dsa_text_custom":
			await call.answer()
			# Пользователь хочет ввести свой текст
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitDsaFSM.text.state)
			await bot_instance.send_message(uid,
				"✏️ *Введите текст жалобы:*\n\n"
				"— На английском языке\n"
				"— До 250 символов\n"
				"— Кратко опишите нарушение",
				parse_mode="Markdown", reply_markup=panel_back_markup)

		# ─── Универсальный метод ─────────────────────────────────────────────────
		elif d == "universal_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_subscribe', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if premium == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_premium', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitUniversalFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"🌐 *Универсальный метод*\n\n"
					"*└─ Отправьте ссылку на цель:*\n\n"
					"`https://t.me/username/123`\n"
					"`https://t.me/username`\n"
					"`@username`"
				),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)

		# ─── [ТЕСТ] Profile Report ────────────────────────────────────────────────
		elif d == "profile_method":
			if uid not in admins:
				await bot_instance.answer_callback_query(call.id, "❌ Только для администраторов!", show_alert=True)
				return
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=panel_back_markup)
				return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitProfileFSM.link.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=(
					"👤 *\[ТЕСТ\] Profile Report*\n\n"
					"*└─ Введите @username или ссылку:*\n\n"
					"`@username` или `https://t\.me/username`"
				),
				parse_mode="MarkdownV2", reply_markup=panel_back_markup
			)

		# ─── Trap-метод ──────────────────────────────────────────────────────────
		elif d == "trap_method":
			if uid not in admins:
				await bot_instance.answer_callback_query(call.id, "❌ Только для администраторов!", show_alert=True)
				return
			if uid not in admins and uid in last_used_trap and (now_msk() - last_used_trap[uid]) < timedelta(hours=3):
				rem = timedelta(hours=3) - (now_msk() - last_used_trap[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.answer_callback_query(call.id, f"❌ КД: {h}ч {m}м", show_alert=True)
				return
			# Сразу запускаем создание бота
			await bot_instance.answer_callback_query(call.id)
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('trap_creating', _user_lang),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)
			# Запускаем в фоне чтобы не блокировать
			asyncio.ensure_future(_trap_create(uid, username, _instance_token))

		# ─── Trap — подтверждение (жертва написала /start) ───────────────────────
		elif d == "trap_done":
			await call.answer()
			# Проверяем есть ли активная trap-сессия
			trap_data = _trap_sessions.get(uid)
			if not trap_data:
				await bot_instance.send_message(uid, t('trap_session_expired', _user_lang), parse_mode="Markdown", reply_markup=main_menu)
				return
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitTrapFSM.victim.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)
			await bot_instance.send_message(
				uid,
				t('trap_enter_victim', _user_lang),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)

		# ─── Trap — отмена ────────────────────────────────────────────────────────
		elif d == "trap_cancel":
			await call.answer()
			_trap_sessions.pop(uid, None)
			await bot_instance.send_message(uid, t('trap_cancelled', _user_lang), parse_mode="Markdown", reply_markup=main_menu)

		# ─── Логгер ───────────────────────────────────────────────────────────────
		elif d == "logger_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_subscribe', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			# Создаём ссылку через внутренний API логгера
			try:
				async with aiohttp.ClientSession() as _s:
					async with _s.get(
						f"http://127.0.0.1:8080/create/{uid}",
						params={"token": _instance_token or config.TOKEN},
						timeout=aiohttp.ClientTimeout(total=5)) as _r:
						data = await _r.json()
				link = data["url"]
				link_escaped = link.replace('.', '\\.').replace('-', '\\-')
				await bot_instance.edit_message_caption(
					call.message.chat.id, call.message.message_id,
					caption=(
						f"🔗 *Логгер*\n\n"
						f"*Ваша ссылка:*\n`{link}`\n\n"
						f"*└─ Отправьте её жертве*\n"
						f"*└─ Как только кто\\-то перейдёт — вам придёт уведомление*"
					),
					parse_mode="MarkdownV2", reply_markup=panel_back_markup
				)
			except Exception as e:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('logger_server_err', _user_lang),
					parse_mode="MarkdownV2", reply_markup=panel_back_markup)

		# ─── Блокировка карты ─────────────────────────────────────────────────
		elif d == "bank_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=">❌ *Бот выключен\!*", parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if premium == 0:
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_premium', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if uid not in admins and uid not in no_kd and uid in last_used_bank and (now_msk() - last_used_bank[uid]) < timedelta(hours=12):
				rem = timedelta(hours=12) - (now_msk() - last_used_bank[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id,
					caption=t('err_wait_hm', _user_lang, h=h, m=m), parse_mode="Markdown", reply_markup=panel_back_markup); return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('bank_select_caption', _user_lang),
				parse_mode="Markdown", reply_markup=keyboards.bank_select_markup
			)

		elif d in ("bank_tbank", "bank_alfa", "bank_sber", "bank_ozon"):
			bank_key = d.replace("bank_", "")
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitBankFSM.card.state)
			await dp_instance.current_state(user=uid).update_data(bank_key=bank_key, _bot_token=_instance_token)
			bank_names = {
				"tbank": t('bank_tbank', _user_lang),
				"alfa": t('bank_alfa', _user_lang),
				"sber": t('bank_sber', _user_lang),
				"ozon": t('bank_ozon', _user_lang),
			}
			await bot_instance.send_message(
				call.message.chat.id,
				t('bank_enter_card', _user_lang, bank=bank_names[bank_key]),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)

		# ─── Спам кодами ─────────────────────────────────────────────────────
		elif d == "code_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_subscribe', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			await bot_instance.edit_message_caption(
				call.message.chat.id, call.message.message_id,
				caption=t('code_method_caption', _user_lang),
				parse_mode="Markdown", reply_markup=panel_back_markup
			)
			await dp_instance.current_state(chat=uid, user=uid).set_state(WaitCodeFSM.phone.state)
			await dp_instance.current_state(user=uid).update_data(_bot_token=_instance_token)

		# ─── Стрессер ─────────────────────────────────────────────────────────
		elif d == "stress_method":
			if bot_off():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_bot_off', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			if sub_expired():
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_pay', _user_lang), parse_mode="MarkdownV2", reply_markup=panel_back_markup); return
			# КД 2 часа (кроме админов)
			if uid not in admins and uid not in no_kd and uid in last_used_stress and (now_msk() - last_used_stress[uid]) < timedelta(hours=2):
				rem = timedelta(hours=2) - (now_msk() - last_used_stress[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await bot_instance.edit_message_caption(call.message.chat.id, call.message.message_id, caption=t('err_wait_hm', _user_lang, h=h, m=m), parse_mode="Markdown", reply_markup=panel_back_markup); return
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
	lang = await db.get_lang(uid)
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	username = message.from_user.username or "без username"
	log_path = generate_log_filename()
	async with aiohttp.ClientSession() as session:
		success, error = await web(session=session, message_text=message.text,
			count=report_count333, log_path=log_path, user_id=uid, username=username)
	# КД ставим только после завершения отправки
	last_used_web[uid] = now_msk()
	try: await db.log_attack(uid, fsm_data.get('web_target', message.text[:100] if message.text else 'web-report'), "web", success)
	except Exception as e: print(f"[HISTORY] web log error: {e}", flush=True)
	try:
		await _bot.send_document(uid, types.InputFile(log_path),
			caption=t('web_result_caption', lang, success=success, error=error),
			reply_markup=main_menu, parse_mode="Markdown")
	except Exception: pass
	try:
		_log_uid, _log_uname = await _log_display(uid, username)
		await bot.send_document(bot_logs, types.InputFile(log_path),
			caption=f"📈 *Веб*\n🟢 {success}\n🔴 {error}\n👤 {_log_uid} (@{_log_uname})", parse_mode="Markdown")
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
	await message.answer(t('mail_enter_text', await db.get_lang(message.from_user.id)), parse_mode="Markdown")
	await WaitMailTextFSM.text.set()

@dp.message_handler(state=WaitMailTextFSM.text)
async def start_bulk_email(message: types.Message, state: FSMContext):
	data = await state.get_data()
	subject = data.get("subject")
	_bot_token = data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	_mail_lang = await db.get_lang(message.from_user.id)
	await state.finish()
	mails = load_mails()
	if not mails:
		await message.answer(t('mail_no_mails', _mail_lang), parse_mode="Markdown"); return
	receiver_emails = ["dmca@telegram.org","support@telegram.org","abuse@telegram.org","stopCA@telegram.org"]
	success, error, log_path = await send_bulk_emails(
		subject, message.text, mails, receiver_emails,
		user_id=message.from_user.id, username=message.from_user.username or "None",
		bot=_bot, chat_id=message.from_user.id)
	# КД ставим только после реального завершения отправки
	last_used_mail[message.from_user.id] = now_msk()
	try: await db.log_attack(message.from_user.id, f"mail:{subject[:100]}", "mail", success)
	except Exception as e: print(f"[HISTORY] mail log error: {e}", flush=True)
	try:
		await _bot.send_document(message.from_user.id, types.InputFile(log_path),
			caption=t('mail_result_caption', _mail_lang, success=success, error=error), parse_mode="Markdown", reply_markup=main_menu)
		_log_uid_m, _log_uname_m = await _log_display(message.from_user.id, message.from_user.username or "None")
		await bot.send_document(bot_logs, types.InputFile(log_path),
			caption=f"📈 *Почты*\n🟢 {success}\n🔴 {error}\n👤 {_log_uid_m} (@{_log_uname_m})", parse_mode="Markdown")
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
	lang = await db.get_lang(uid)
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	try:
		chat_username, message_id = await extract_username_and_message_id(url)
		user_data = await db.get_user(uid)
		if not user_data:
			await _bot.send_message(uid, t('err_user_not_found', lang), parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
			return
		subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
		if subscribe < now_msk():
			used = await db.use_free_report(uid)
			if not used:
				await _bot.send_message(uid, t('err_no_sub_no_free', lang), parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
				return
			free_left = await db.get_free_reports(uid)
			await _bot.send_message(uid, t('free_report_used', lang, count=free_left), parse_mode=ParseMode.MARKDOWN)
		await _bot.send_message(uid, t('botnet_launching', lang), parse_mode=ParseMode.MARKDOWN)
		botnet_set_bot(_bot)
		await botnet_main(chat_username, message_id, uid, username, url)
		try: await db.log_attack(uid, url, "botnet")
		except Exception as e: print(f"[HISTORY] botnet log error: {e}", flush=True)
		# КД только после успешного запуска
		last_used_botnet[uid] = now_msk()
		# Предлагаем мониторинг
		try:
			_ud = await db.get_user(uid)
			_prem = int(_ud.get('premium', 0)) if _ud else 0
			_sub = datetime.strptime(str(_ud['subscribe'])[:19], "%Y-%m-%d %H:%M:%S") if _ud else now_msk() - timedelta(days=1)
			await _offer_monitor(_bot, uid, url, _prem, _sub)
		except Exception:
			pass
	except ValueError:
		await _bot.send_message(uid, t('botnet_invalid_link', lang), parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
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
	lang = await db.get_lang(uid)
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot
	try:
		chat_username, message_id = await extract_username_and_message_id2(url)
		await _bot.send_message(uid, t('botnet_prem_launching', lang), parse_mode=ParseMode.MARKDOWN)
		botnet_set_bot2(_bot)
		await botnet_main2(chat_username, message_id, uid, username, url)
		try: await db.log_attack(uid, url, "prem_botnet")
		except Exception as e: print(f"[HISTORY] prem_botnet log error: {e}", flush=True)
		# КД только после успешного запуска
		last_used_botnet2[uid] = now_msk()
		# Предлагаем мониторинг
		try:
			_ud = await db.get_user(uid)
			_prem = int(_ud.get('premium', 0)) if _ud else 0
			_sub = datetime.strptime(str(_ud['subscribe'])[:19], "%Y-%m-%d %H:%M:%S") if _ud else now_msk() - timedelta(days=1)
			await _offer_monitor(_bot, uid, url, _prem, _sub)
		except Exception:
			pass
	except ValueError:
		await _bot.send_message(uid, t('botnet_invalid_link', lang), parse_mode=ParseMode.MARKDOWN)
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
	lang = await db.get_lang(uid)

	# Если прислали команду — отменяем FSM
	if token.startswith('/'):
		await state.finish()
		await bot.send_message(uid, t('mirror_token_cancel', lang), parse_mode="Markdown", reply_markup=main_menu)
		return

	# Базовая проверка формата токена
	if ':' not in token or len(token) < 30:
		await state.finish()
		await bot.send_message(uid, t('mirror_token_invalid', lang), parse_mode="Markdown")
		return

	await state.finish()

	# Проверяем не сдан ли токен уже
	if await db.token_exists(token):
		await bot.send_message(uid, t('mirror_token_exists', lang), parse_mode="Markdown")
		return

	# Проверяем токен через getMe
	wait_msg = await bot.send_message(uid, t('mirror_token_checking', lang), parse_mode="Markdown")
	bot_username_new = await validate_token(token)
	try:
		await bot.delete_message(uid, wait_msg.message_id)
	except Exception:
		pass

	if not bot_username_new:
		await bot.send_message(uid, t('mirror_token_bad', lang), parse_mode="Markdown")
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
	lang = await db.get_lang(uid)

	# Сначала читаем fsm_data чтобы _bot был доступен для сообщений об ошибках
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	user_data = await db.get_user(uid)
	if not user_data:
		await state.finish()
		await _bot.send_message(uid, t('err_user_not_found', lang), parse_mode="Markdown", reply_markup=main_menu)
		return
	subscribe = datetime.strptime(str(user_data['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")

	if uid not in admins and subscribe < now_msk():
		await state.finish()
		await _bot.send_message(uid, t('err_pay', lang), parse_mode="MarkdownV2", reply_markup=main_menu)
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
		await _bot.send_message(uid, t('bot_not_a_bot', lang), parse_mode="Markdown", reply_markup=main_menu)
		return

	# Детектируем тип бота — свой (капча) или чужой
	is_fast_bot = False
	try:
		is_fast_bot = await detect_bot_type(bot_target)
	except Exception as _det_e:
		print(f'[BOT-SNOS] detect error: {_det_e}', flush=True)

	# Проверяем КД в зависимости от типа бота
	if uid not in admins and uid not in no_kd:
		if is_fast_bot:
			# Свой бот — КД 5 минут
			if uid in last_used_bot_snos_fast and (now_msk() - last_used_bot_snos_fast[uid]) < timedelta(minutes=5):
				rem = timedelta(minutes=5) - (now_msk() - last_used_bot_snos_fast[uid])
				await state.finish()
				await _bot.send_message(uid, t('err_wait', lang, m=rem.seconds // 60, s=rem.seconds % 60), parse_mode="Markdown", reply_markup=main_menu)
				return
		else:
			# Чужой бот — КД 1 час
			if uid in last_used_bot_snos and (now_msk() - last_used_bot_snos[uid]) < timedelta(hours=1):
				rem = timedelta(hours=1) - (now_msk() - last_used_bot_snos[uid])
				h = rem.seconds // 3600
				m = (rem.seconds % 3600) // 60
				await state.finish()
				await _bot.send_message(uid, t('err_wait_hm', lang, h=h, m=m), parse_mode="Markdown", reply_markup=main_menu)
				return

	reason_key = fsm_data.get('bot_reason', 'other')
	await state.finish()

	# Ставим КД
	if is_fast_bot:
		last_used_bot_snos_fast[uid] = now_msk()
	else:
		last_used_bot_snos[uid] = now_msk()

	kd_label = t('cd_5min', lang) if is_fast_bot else t('cd_1hour', lang)
	await _bot.send_message(uid, t('bot_method_launching', lang, target=bot_target, cd=kd_label), parse_mode=ParseMode.MARKDOWN)

	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	try:
		await main_bot_snos(bot_target, reason_key, uid, username, bot_target, notify_bot=_bot)
		try: await db.log_attack(uid, bot_target, "bot")
		except Exception as e: print(f"[HISTORY] bot log error: {e}", flush=True)
		# Предлагаем мониторинг
		try:
			_ud = await db.get_user(uid)
			_prem = int(_ud.get('premium', 0)) if _ud else 0
			_sub = datetime.strptime(str(_ud['subscribe'])[:19], "%Y-%m-%d %H:%M:%S") if _ud else now_msk() - timedelta(days=1)
			await _offer_monitor(_bot, uid, bot_target, _prem, _sub)
		except Exception:
			pass
	except Exception as e:
		import traceback
		print(f"[BOT-SNOS] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		traceback.print_exc()
		await _bot.send_message(uid, f'❌ *Ошибка бот-метода:* `{str(e)[:100]}`', parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
	finally:
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
	lang = await db.get_lang(uid)
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
	if uid not in admins and uid not in no_kd and uid in last_used_channel and (now_msk() - last_used_channel[uid]) < timedelta(minutes=30):
		rem = timedelta(minutes=30) - (now_msk() - last_used_channel[uid])
		await _bot.send_message(uid, t('err_wait', lang, m=rem.seconds//60, s=rem.seconds%60), parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	# Списываем бесплатный репорт если подписка истекла
	if uid not in admins:
		user_data_ch = await db.get_user(uid)
		if user_data_ch:
			subscribe_ch = datetime.strptime(str(user_data_ch['subscribe'])[:19], "%Y-%m-%d %H:%M:%S")
			if subscribe_ch < now_msk():
				used = await db.use_free_report(uid)
				if not used:
					await _bot.send_message(uid, t('err_no_sub_no_free', lang), parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu)
					return
				free_left = await db.get_free_reports(uid)
				await _bot.send_message(uid, t('free_report_used', lang, count=free_left), parse_mode=ParseMode.MARKDOWN)

	last_used_channel[uid] = now_msk()
	msg_info = f" (сообщение #{message_id})" if message_id else ""
	await _bot.send_message(uid, t('channel_launching', lang, target=f'{ch_target}{msg_info}'), parse_mode="Markdown")

	try:
		await main_channel_snos(ch_target, reason_key, uid, username, message_id=message_id, notify_bot=_bot)
		try: await db.log_attack(uid, ch_target, "channel")
		except Exception as e: print(f"[HISTORY] channel log error: {e}", flush=True)
		# Предлагаем мониторинг
		try:
			_ud = await db.get_user(uid)
			_prem = int(_ud.get('premium', 0)) if _ud else 0
			_sub = datetime.strptime(str(_ud['subscribe'])[:19], "%Y-%m-%d %H:%M:%S") if _ud else now_msk() - timedelta(days=1)
			await _offer_monitor(_bot, uid, raw, _prem, _sub)
		except Exception:
			pass
	except Exception as e:
		print(f"[CH-SNOS] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка канал-метода:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
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
		last_used_aureport[uid] = now_msk()

	await _bot.send_message(uid,
		f'🇦🇺 *Запускаю AU Report на* `{raw}`*...*\n*└─ Это может занять некоторое время*',
		parse_mode="Markdown")

	try:
		await main_aureport(raw, uid, username, notify_bot=_bot)
		try: await db.log_attack(uid, raw, "aureport")
		except Exception as e: print(f"[HISTORY] aureport log error: {e}", flush=True)
		# Предлагаем мониторинг
		try:
			_ud = await db.get_user(uid)
			_prem = int(_ud.get('premium', 0)) if _ud else 0
			_sub = datetime.strptime(str(_ud['subscribe'])[:19], "%Y-%m-%d %H:%M:%S") if _ud else now_msk() - timedelta(days=1)
			await _offer_monitor(_bot, uid, raw, _prem, _sub)
		except Exception:
			pass
	except Exception as e:
		print(f"[AUREPORT] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка AU Report:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitTelegraphFSM.link)
async def telegraph_step1(message: types.Message, state: FSMContext):
	"""Пользователь ввёл ссылку на статью."""
	uid = message.from_user.id
	username = message.from_user.username or "None"
	lang = await db.get_lang(uid)
	raw = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	# Валидация ссылки
	if "telegra.ph" not in raw and "teletype.in" not in raw:
		await _bot.send_message(uid,
			"❌ *Неверная ссылка!*\n\n"
			"*Пример:* `https://telegra.ph/название`",
			parse_mode="Markdown", reply_markup=panel_back_markup)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	# Проверяем доступность статьи
	await _bot.send_message(uid, t('telegraph_checking', lang), parse_mode="Markdown")
	article_text, status = await fetch_telegraph_text(raw)

	if status == 404:
		await state.finish()
		await _bot.send_message(uid,
			"❌ *Статья недоступна или удалена (404)*\n\nПопробуйте другую ссылку.",
			parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	if status != 200:
		await state.finish()
		await _bot.send_message(uid,
			f"❌ *Не удалось получить статью (код {status})*",
			parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	# Groq генерация
	await _bot.send_message(uid, t('telegraph_generating', lang), parse_mode="Markdown")
	subject, body = await generate_telegraph_text(raw, article_text)

	# Сохраняем в FSM
	await state.update_data(
		telegraph_url=raw,
		telegraph_subject=subject,
		telegraph_body=body,
	)
	await dp.current_state(chat=uid, user=uid).set_state(WaitTelegraphFSM.confirm.state)

	# Показываем сгенерированный текст
	await _bot.send_message(uid,
		f"📄 *Telegraph снос*\n\n"
		f"*Тема:* `{subject}`\n\n"
		f"*Текст:*\n`{body}`\n\n"
		f"*Отправить на:* abuse / support / dmca @telegram.org\n"
		f"*Писем:* 12 (4 отправителя × 3 адреса)",
		parse_mode="Markdown",
		reply_markup=keyboards.telegraph_confirm_markup
	)


@dp.message_handler(state=WaitTelegraphFSM.custom_text)
async def telegraph_custom_text(message: types.Message, state: FSMContext):
	"""Пользователь ввёл свой текст письма."""
	uid = message.from_user.id
	username = message.from_user.username or "None"
	lang = await db.get_lang(uid)
	custom_body = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	article_url = fsm_data.get("telegraph_url", "")
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	if not custom_body:
		await _bot.send_message(uid, t('telegraph_empty_text', lang), parse_mode="Markdown", reply_markup=main_menu)
		return

	if uid not in admins:
		last_used_telegraph[uid] = now_msk()

	custom_subject = f"ToS Violation: {article_url}"

	await _bot.send_message(uid,
		f'📄 *Запускаю Telegraph снос...*\n*└─ Отправляем 12 жалоб*',
		parse_mode="Markdown")

	try:
		await main_telegraph_snos(article_url, uid, username, custom_text=custom_body, custom_subject=custom_subject, notify_bot=_bot)
		try: await db.log_attack(uid, article_url, "telegraph")
		except Exception as e: print(f"[HISTORY] telegraph log error: {e}", flush=True)
	except Exception as e:
		print(f"[TELEGRAPH] ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitDsaFSM.link)
async def dsa_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.update_data(dsa_link=raw, _bot_token=_bot_token, dsa_username=username)
	await WaitDsaFSM.reason.set()

	await _bot.send_message(uid,
		f'🇪🇺 *DSA Report*\n\n'
		f'*Цель:* `{raw}`\n\n'
		f'*Выберите причину жалобы:*',
		parse_mode="Markdown",
		reply_markup=keyboards.dsa_reason_markup)

	if _is_mirror_bot:
		try:
			s = await _bot.get_session(); await s.close()
		except Exception: pass


@dp.message_handler(state=WaitDsaFSM.text)
async def dsa_custom_text(message: types.Message, state: FSMContext):
	"""Пользователь ввёл свой текст жалобы."""
	uid = message.from_user.id
	custom = message.text.strip()[:250]
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	# Сохраняем текст в FSM данные перед завершением
	await state.update_data(dsa_text=custom)
	fsm_data = await state.get_data()
	await state.finish()

	await _dsa_launch(uid, _bot, fsm_data, state)


@dp.message_handler(state=WaitTidaFSM.link)
async def tida_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	raw = message.text.strip()
	lang = await db.get_lang(uid)
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')

	if not raw.startswith("@") and not raw.startswith("https://t.me/") and not raw.startswith("t.me/"):
		raw = "@" + raw

	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.update_data(tida_link=raw)

	# Анализируем ссылку
	await _bot.send_message(uid, t('tida_analyzing', lang), parse_mode="Markdown")

	from tida_snos import analyze_tida_link
	info = await analyze_tida_link(raw)

	target_type = info.get("target_type", "channel")
	is_public = info.get("is_public", False)
	has_msg = info.get("has_message_id", False)
	msg_text = info.get("message_text", "")

	await state.update_data(
		tida_link=raw,
		tida_target=target_type,
		tida_analysis=info,
	)

	target_names = {
		"account": t('tida_target_account', lang),
		"bot": t('tida_target_bot', lang),
		"chat": t('tida_target_chat', lang),
		"channel": t('tida_target_channel', lang),
	}
	target_label = target_names.get(target_type, t('tida_target_channel', lang))

	if is_public and has_msg and msg_text:
		# Публичная + есть сообщение — сразу генерируем ИИ-текст
		await WaitTidaFSM.text_confirm.set()
		await _bot.send_message(uid, t('tida_generating', lang), parse_mode="Markdown")
		from tida_snos import generate_tida_text
		generated = await generate_tida_text(msg_text, target_type, is_description=False)
		if not generated:
			generated = "This resource violates Telegram's Terms of Service. Requesting immediate action."
		await state.finish()
		_tida_pending[uid] = {
			'link': raw, 'text': generated, 'target': target_type,
			'bot_token': _bot_token, 'username': message.from_user.username or "None",
		}
		await _bot.send_message(uid,
			f"🤖 *ИИ проанализировал сообщение:*\n\n"
			f"🎯 *Цель:* {target_label}\n\n"
			f"`{generated}`\n\n"
			f"*Использовать этот текст?*",
			parse_mode="Markdown",
			reply_markup=keyboards.tida_text_confirm_markup())
	else:
		# Публичная без сообщения / приватная / бот / аккаунт
		# Показываем: описать нарушение (ИИ) или свой текст
		await WaitTidaFSM.ai_desc.set()
		markup = types.InlineKeyboardMarkup(row_width=1)
		markup.add(
			types.InlineKeyboardButton(t('tida_ai_desc', lang), callback_data='tida_choose_ai_desc'),
			types.InlineKeyboardButton(t('tida_manual_text', lang), callback_data='tida_choose_manual'),
		)
		type_info = ""
		if not is_public:
			type_info = t('tida_private_link', lang)
		await _bot.send_message(uid,
			f"🟣 *TIDA*\n\n"
			f"🎯 *Цель:* {target_label} {type_info}\n"
			f"🔗 `{raw}`\n\n"
			f"*Как хотите составить текст жалобы?*",
			parse_mode="Markdown",
			reply_markup=markup)

	if _is_mirror_bot:
		try:
			s = await _bot.get_session(); await s.close()
		except Exception: pass


@dp.message_handler(state=WaitTidaFSM.text)
async def tida_step2(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	custom_text = message.text.strip()
	lang = await db.get_lang(uid)
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	target_link = fsm_data.get('tida_link', '')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	if len(custom_text) < 10:
		await _bot.send_message(uid, t('tida_text_too_short', lang), parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	if uid not in admins:
		last_used_tida[uid] = now_msk()

	await _bot.send_message(uid,
		f'🟣 *Запускаю TIDA на* `{target_link}`*...*\n*└─ Это может занять некоторое время*',
		parse_mode="Markdown")

	try:
		await main_tida(target_link, custom_text, uid, username, notify_bot=_bot)
		try: await db.log_attack(uid, target_link, "tida")
		except Exception as e: print(f"[HISTORY] tida log error: {e}", flush=True)
	except Exception as e:
		print(f"[TIDA] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка TIDA:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitTidaFSM.target)
async def tida_target_step(message: types.Message, state: FSMContext):
	"""Обрабатывает выбор типа цели (если прислали текст вместо кнопки)."""
	await state.finish()
	uid = message.from_user.id
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_bot = Bot(token=_bot_token) if bool(_bot_token and _bot_token != config.TOKEN) else bot
	await _bot.send_message(uid, t('tida_wrong_target', await db.get_lang(uid)), parse_mode="Markdown", reply_markup=main_menu)



@dp.message_handler(state=WaitTidaFSM.ai_desc)
async def tida_ai_desc_step(message: types.Message, state: FSMContext):
	"""Пользователь описал нарушение — генерируем текст через ИИ."""
	uid = message.from_user.id
	description = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	target_type = fsm_data.get('tida_target', 'channel')
	tida_link = fsm_data.get('tida_link', '')
	_is_mirror = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror else bot

	await state.finish()

	await _bot.send_message(uid, t('tida_ai_generating', await db.get_lang(uid)), parse_mode="Markdown")

	from tida_snos import generate_tida_text
	generated = await generate_tida_text(description, target_type, is_description=True)

	if not generated:
		generated = "This resource violates Telegram's Terms of Service. Requesting immediate action."

	await _bot.send_message(uid,
		f"🤖 *ИИ сгенерировал текст жалобы:*\n\n`{generated}`\n\n*Использовать этот текст?*",
		parse_mode="Markdown",
		reply_markup=keyboards.tida_text_confirm_markup())

	# Сохраняем для последующего использования через временный dict
	_tida_pending[uid] = {
		'link': tida_link,
		'text': generated,
		'target': target_type,
		'bot_token': _bot_token,
		'username': message.from_user.username or "None",
	}


@dp.message_handler(state=WaitBankFSM.card)
async def bank_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	card_data = message.text.strip()
	lang = await db.get_lang(uid)
	fsm_data = await state.get_data()
	bank_key = fsm_data.get('bank_key', 'tbank')
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	if len(card_data) < 7:
		await _bot.send_message(uid, t('bank_invalid', lang), parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	if uid not in admins:
		last_used_bank[uid] = now_msk()

	try:
		await process_bank_report(bank_key, card_data, uid, username, notify_bot=_bot)
		try: await db.log_attack(uid, f"bank:{card_data[:50]}", "bank")
		except Exception as e: print(f"[HISTORY] bank log error: {e}", flush=True)
	except Exception as e:
		print(f"[BANK] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitCodeFSM.phone)
async def code_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	phone = message.text.strip()
	lang = await db.get_lang(uid)
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	if len(phone) < 7 or not any(c.isdigit() for c in phone):
		await _bot.send_message(uid, t('code_invalid_phone', lang), parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	await _bot.send_message(uid, t('code_launching', lang, phone=phone), parse_mode="Markdown")

	try:
		await main_code_snos(phone, uid, username, notify_bot=_bot)
	except Exception as e:
		print(f"[CODE] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitTrapFSM.victim)
async def trap_step1(message: types.Message, state: FSMContext):
	"""Пользователь ввёл @username жертвы — запускаем передачу."""
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip().lstrip("@")
	lang = await db.get_lang(uid)
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	if not raw or len(raw) < 3:
		await _bot.send_message(uid, t('trap_cancelled', lang), parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	trap_data = _trap_sessions.get(uid)
	if not trap_data:
		await _bot.send_message(uid, t('trap_session_expired', lang), parse_mode="Markdown", reply_markup=main_menu)
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass
		return

	# Сохраняем КД
	last_used_trap[uid] = now_msk()
	_trap_sessions.pop(uid, None)

	await _bot.send_message(uid,
		f"🔄 *Передаю владельца @{trap_data['bot_username']} → @{raw}...*",
		parse_mode="Markdown")

	try:
		await transfer_and_apply(
			bot_token=trap_data["bot_token"],
			bot_username=trap_data["bot_username"],
			victim_username=raw,
			user_id=uid,
			username=username,
			notify_bot=_bot
		)
	except Exception as e:
		print(f"[TRAP] trap_step1 error: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка trap:* `{str(e)[:100]}`',
			parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror_bot:
			try:
				s = await _bot.get_session(); await s.close()
			except Exception: pass


@dp.message_handler(state=WaitProfileFSM.link)
async def profile_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()
	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror_bot = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror_bot else bot

	await state.finish()

	# Только для админов — двойная проверка
	if uid not in admins:
		await _bot.send_message(uid, "❌ *Только для администраторов!*", parse_mode="Markdown", reply_markup=main_menu)
		return

	await _bot.send_message(
		uid,
		f'👤 *\[ТЕСТ\] Запускаю Profile Report на* `{raw}`*...*\n'
		f'*└─ Метод: Spam → Defamation/Insult*',
		parse_mode="Markdown"
	)

	try:
		await main_profile_snos(raw, uid, username, notify_bot=_bot)
		try: await db.log_attack(uid, raw, "profile")
		except Exception as e: print(f"[HISTORY] profile log error: {e}", flush=True)
	except Exception as e:
		import traceback
		print(f"[PROFILE] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
		traceback.print_exc()
		await _bot.send_message(uid, f'❌ *Ошибка Profile-метода:* `{str(e)[:100]}`',
			parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror_bot:
			try:
				session = await _bot.get_session()
				await session.close()
			except Exception:
				pass


@dp.message_handler(state=WaitStressFSM.link)
async def stress_step1(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	lang = await db.get_lang(uid)
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
	if not is_admin and subscribe < now_msk():
		await _bot.send_message(uid, t('stress_no_sub', lang), parse_mode="Markdown", reply_markup=main_menu)
		return

	await _bot.send_message(uid, t('stress_launching', lang, target=bot_target), parse_mode="Markdown")
	try:
		started = await main_bot_stress(bot_target, uid, username, is_admin, notify_bot=_bot)
		try: await db.log_attack(uid, bot_target, "stress")
		except Exception as e: print(f"[HISTORY] stress log error: {e}", flush=True)
		# КД только если атака успешно запустилась (нашлись кнопки)
		if started and not is_admin:
			last_used_stress[uid] = now_msk()
	except Exception as e:
		print(f"[STRESS] ОШИБКА: {e}", flush=True)
		import traceback
		traceback.print_exc()
		await _bot.send_message(uid, f'❌ *Ошибка стрессера:* `{str(e)[:100]}`', parse_mode="Markdown", reply_markup=main_menu)
	finally:
		if _is_mirror_bot:
			try:
				session = await _bot.get_session()
				await session.close()
			except Exception:
				pass

# ─── Управление подписками (админ) ────────────────────────────────────────────

async def _notify_user(target: int, text: str, source_bot=None, **kwargs):
	"""Отправляет уведомление через source_bot (бот админа), затем через assigned mirror."""
	# 1. Через того же бота, от которого пришла команда админа
	if source_bot is not None and source_bot is not bot:
		try:
			await source_bot.send_message(target, text, **kwargs)
			return
		except Exception:
			pass
	# 2. Через зеркало, к которому привязан юзер
	try:
		from mirror_manager import _mirror_bots
		token = await db.get_user_mirror(target)
		if token and token in _mirror_bots:
			await _mirror_bots[token].send_message(target, text, **kwargs)
			return
	except Exception:
		pass
	# 3. Через любое живое зеркало
	try:
		from mirror_manager import _mirror_bots
		if _mirror_bots:
			live_bot = next(iter(_mirror_bots.values()))
			await live_bot.send_message(target, text, **kwargs)
			return
	except Exception:
		pass

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
		await state.set_state(AddSubscribeFSM.days.state)
	except Exception:
		await message.answer("❌ Ошибка."); await state.finish()

@dp.message_handler(state=AddSubscribeFSM.days)
async def add_sub_days(message: types.Message, state: FSMContext):
	try:
		data = await state.get_data()
		target = data['user_id']
		new_date = (now_msk() + timedelta(days=int(message.text))).strftime("%Y-%m-%d %H:%M:%S")
		await db.set_subscribe(target, new_date)
		await state.finish()
		await _notify_user(target, f"🎱 *Подписка обновлена до* `{new_date}`", source_bot=message.bot, parse_mode="Markdown", reply_markup=del_message2)
		await message.answer(f"🎱 *Готово! Подписка выдана* `{target}` *до* `{new_date}`", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🎱 *Выдана подписка* `{target}` до `{new_date}` | *Админ:* `{message.from_user.id}`", parse_mode="Markdown")
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
		await _notify_user(target, "*🎱 Подписка сброшена.*", source_bot=message.bot, parse_mode="Markdown", reply_markup=del_message2)
		await message.answer(f"*🎱 Сброшено у* `{target}`*!*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🎱 *Сброшена подписка* `{target}` | *Админ:* `{message.from_user.id}`", parse_mode="Markdown")
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
		await _notify_user(target, "*👑 Вам выдан Premium.*", source_bot=message.bot, parse_mode="Markdown", reply_markup=del_message2)
		await message.answer(f"*🎱 Премиум выдан* `{target}`*!*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"👑 *Выдан премиум* `{target}` | *Админ:* `{message.from_user.id}`", parse_mode="Markdown")
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
		await _notify_user(target, "*🎱 Премиум сброшен.*", source_bot=message.bot, parse_mode="Markdown", reply_markup=del_message2)
		await message.answer(f"*🎱 Сброшено у* `{target}`*!*", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"👑 *Сброшен премиум* `{target}` | *Админ:* `{message.from_user.id}`", parse_mode="Markdown")
	except Exception:
		await message.answer("❌ Ошибка."); await state.finish()

# ─── Рассылка ─────────────────────────────────────────────────────────────────

@dp.message_handler(state=WaitTextZFSM.text, content_types=types.ContentTypes.ANY)
async def sendall(message: types.Message, state: FSMContext):
	await state.finish()
	status_msg = await message.answer('📤 *Рассылка запущена...*', parse_mode='Markdown')
	asyncio.create_task(_do_broadcast(message, status_msg))

async def _do_broadcast(source: types.Message, status_msg: types.Message):
	users = await db.get_all_user_ids()
	ok, fail = 0, 0
	total = len(users)

	for i, user_id in enumerate(users):
		try:
			await source.copy_to(user_id, reply_markup=del_message2)
			ok += 1
		except Exception:
			fail += 1
		await asyncio.sleep(0.05)
		# Обновляем прогресс каждые 200 отправок
		if (i + 1) % 200 == 0:
			try:
				await status_msg.edit_text(
					f'📤 *Рассылка...*\n*Прогресс:* {i+1}/{total}\n*✅* {ok} *❌* {fail}',
					parse_mode='Markdown'
				)
			except Exception:
				pass

	try:
		await status_msg.edit_text(
			f'*🎱 Рассылка окончена!*\n*✅ Доставлено:* {ok}\n*❌ Не доставлено:* {fail}',
			parse_mode='Markdown', reply_markup=main_menu
		)
	except Exception:
		await source.answer(
			f'*🎱 Рассылка окончена!*\n*✅ Доставлено:* {ok}\n*❌ Не доставлено:* {fail}',
			parse_mode='Markdown', reply_markup=main_menu
		)
	try:
		await bot.send_message(bot_logs, f"📢 *Рассылка завершена*\n*✅ {ok} / ❌ {fail}*", parse_mode='Markdown')
	except Exception:
		pass

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
		# Авто-деактивируем в site_promos если активации исчерпаны
		remaining = await conn.fetchval("SELECT activations FROM promocode WHERE code = $1", code)
		if remaining is not None and remaining <= 0:
			await conn.execute(
				"UPDATE site_promos SET active = false WHERE UPPER(code) = UPPER($1)",
				code
			)
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
		new_date = (now_msk() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
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

@dp.message_handler(state=CheckUserFSM.query)
async def admin_check_user_fsm(message: types.Message, state: FSMContext):
	await state.finish()
	raw = message.text.strip()
	uid_target = await db.resolve_user(raw)
	if not uid_target:
		await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown")
		return
	user = await db.get_user(uid_target)
	if not user:
		await message.answer(f"❌ Пользователь `{uid_target}` не найден в БД.", parse_mode="Markdown")
		return

	now = datetime.now()
	sub_dt = user.get("subscribe")
	if sub_dt and sub_dt.year > 2000 and sub_dt > now:
		sub_str = f"✅ до `{sub_dt.strftime('%d.%m.%Y %H:%M')}`"
	elif sub_dt and sub_dt.year > 2000:
		sub_str = f"❌ истекла `{sub_dt.strftime('%d.%m.%Y %H:%M')}`"
	else:
		sub_str = "❌ нет"

	premium = user.get("premium") or 0
	verified = user.get("verified") or 0
	free_reports = user.get("free_reports") or 0
	referral_count = user.get("referral_count") or 0
	referrer_id = user.get("referrer_id")
	username_str = user.get("username") or ""
	lang = user.get("lang") or "ru"
	manual = user.get("manual_confirmed") or 0

	badges = []
	if premium: badges.append("⭐ Premium")
	if verified: badges.append("✅ Верифицирован")
	if manual: badges.append("🤝 Ручное")
	badges_str = "  •  ".join(badges) if badges else "—"

	uname_str = f"@{username_str} " if username_str else ""
	text = (
		f"👤 *Пользователь {uname_str}*`{uid_target}`\n\n"
		f"*├─ Статусы:* {badges_str}\n"
		f"*├─ Подписка:* {sub_str}\n"
		f"*├─ Язык:* `{lang.upper()}`\n"
		f"*├─ Бесплат. репортов:* `{free_reports}`\n"
		f"*├─ Рефералов:* `{referral_count}`\n"
	)
	if referrer_id:
		referrer = await db.get_user(referrer_id)
		ref_uname = referrer.get("username") if referrer else None
		ref_str = f"@{ref_uname} `{referrer_id}`" if ref_uname else f"`{referrer_id}`"
		text += f"*├─ Пригласил:* {ref_str}\n"

	try:
		pool = await db.get_pool()
		async with pool.acquire() as conn:
			invoices = await conn.fetchval("SELECT COUNT(*) FROM paid_invoices WHERE user_id=$1", uid_target)
			reports = await conn.fetch(
				"SELECT target_url, method, success_count, created_at FROM attack_log WHERE user_id=$1 ORDER BY created_at DESC LIMIT 3",
				uid_target
			)
		text += f"*└─ Оплат:* `{invoices or 0}`\n"
	except Exception:
		reports = []
		text += f"*└─ Оплат:* нет данных\n"

	if reports:
		text += "\n📋 *Последние репорты:*\n"
		for r in reports:
			dt_str = r["created_at"].strftime("%d.%m %H:%M")
			text += f"*•* `{r['method']}` → `{r['target_url'][:40]}` ✅`{r['success_count']}` _{dt_str}_\n"
	else:
		text += "\n📋 *Репортов нет*"

	await message.answer(text, parse_mode="Markdown")


@dp.message_handler(state=AdminSendMsgFSM.target)
async def admin_send_msg_target(message: types.Message, state: FSMContext):
	raw = message.text.strip()
	uid_target = await db.resolve_user(raw)
	if not uid_target:
		await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown")
		await state.finish()
		return
	await state.update_data(send_target=uid_target)
	await message.answer(f"✉️ *Цель:* `{uid_target}`\n*└─ Введите текст сообщения:*", parse_mode="Markdown")
	await state.set_state(AdminSendMsgFSM.text.state)

@dp.message_handler(state=AdminSendMsgFSM.text)
async def admin_send_msg_text(message: types.Message, state: FSMContext):
	data = await state.get_data()
	uid_target = data.get("send_target")
	text = message.text.strip()
	await state.finish()
	try:
		await bot.send_message(uid_target, text)
		await message.answer(f"✅ *Сообщение отправлено* `{uid_target}`", parse_mode="Markdown")
		await bot.send_message(bot_logs,
			f"✉️ *Личное сообщение*\n👤 *От админа:* `{message.from_user.id}` (@{message.from_user.username or 'None'})\n"
			f"🎯 *Кому:* `{uid_target}`\n📝 *Текст:* {text[:300]}",
			parse_mode="Markdown")
	except Exception as e:
		await message.answer(f"❌ Не удалось отправить: `{e}`", parse_mode="Markdown")

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
		await bot.send_message(bot_logs, f"🎯 *+{amount} репортов* `{target}` *от админа* `{message.from_user.id}`", parse_mode="Markdown")
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
		await bot.send_message(bot_logs, f"🎯 *-{amount} репортов* `{target}` *от админа* `{message.from_user.id}`", parse_mode="Markdown")
	except ValueError:
		await message.answer("❌ Введите число.")
		await state.finish()

# ─── Кейс: Админ выдача ───────────────────────────────────────────────────────

@dp.message_handler(state=AdminAddCaseFSM.user_id)
async def admin_add_case_uid(message: types.Message, state: FSMContext):
	try:
		raw = message.text.strip()
		target = await db.resolve_user(raw)
		if not target:
			await message.answer(f"❌ Пользователь `{raw}` не найден.", parse_mode="Markdown")
			await state.finish()
			return
		await state.update_data(user_id=target)
		await message.answer(f"🎁 *ID:* `{target}`\n*Сколько кейсов выдать?*", parse_mode="Markdown")
		await AdminAddCaseFSM.amount.set()
	except Exception:
		await message.answer("❌ Ошибка.")
		await state.finish()

@dp.message_handler(state=AdminAddCaseFSM.amount)
async def admin_add_case_amount(message: types.Message, state: FSMContext):
	try:
		data = await state.get_data()
		target = data['user_id']
		amount = int(message.text.strip())
		if amount <= 0:
			raise ValueError
		for _ in range(amount):
			await db.add_case(target)
		await state.finish()
		await message.answer(f"✅ *Выдано {amount} кейс(ов)* пользователю `{target}`", parse_mode="Markdown")
		await bot.send_message(bot_logs, f"🎁 *+{amount} кейс(ов)* `{target}` *от админа* `{message.from_user.id}`", parse_mode="Markdown")
		try:
			await bot.send_message(target,
				f"🎁 *Вам выдано {amount} кейс(ов)!*\n*└─ Откройте их в разделе «🎁 Кейс» в главном меню*",
				parse_mode="Markdown")
		except Exception:
			pass
	except ValueError:
		await message.answer("❌ Введите число больше 0.")
		await state.finish()
	except Exception as e:
		await message.answer(f"❌ Ошибка: `{str(e)[:100]}`", parse_mode="Markdown")
		await state.finish()

# ─── Запуск ───────────────────────────────────────────────────────────────────

async def _trap_create(uid: int, username: str, bot_token_instance: str):
	"""Фоновая функция: создаёт бота через BotFather и сохраняет данные в _trap_sessions."""
	_bot = Bot(token=bot_token_instance) if (bot_token_instance and bot_token_instance != config.TOKEN) else bot
	try:
		result = await main_trap_snos(uid, username, notify_bot=_bot)
		if result.get("ok"):
			_trap_sessions[uid] = {
				"bot_token":    result["bot_token"],
				"bot_username": result["bot_username"],
			}
		else:
			await _bot.send_message(uid, f'❌ *Ошибка trap:* `{result.get("error","")}`',
				parse_mode="Markdown", reply_markup=main_menu)
	except Exception as e:
		print(f"[TRAP] _trap_create error: {e}", flush=True)
		await _bot.send_message(uid, f'❌ *Ошибка trap:* `{str(e)[:100]}`',
			parse_mode="Markdown", reply_markup=main_menu)


async def _sub_expiry_notify_loop():
	import asyncio as _asyncio
	while True:
		try:
			user_ids = await db.get_expiring_soon_users()
			for uid_ in user_ids:
				try:
					await bot.send_message(
						uid_,
						"⏰ *Подписка истекает через ~3 часа*\n\n"
						"Продли сейчас — не теряй доступ к методам.\n\n"
						"_Напиши администратору для продления._",
						parse_mode="Markdown"
					)
					await db.mark_sub_expiry_notified(uid_)
				except Exception:
					pass
		except Exception:
			pass
		await _asyncio.sleep(600)


async def _start_invite_api():
	"""HTTP API на localhost:8181 — раздаёт свежие инвайт-ссылки зеркалам."""
	from aiohttp import web as aio_web
	import time as _t

	async def handle_invite(request):
		try:
			expire = int(_t.time()) + 60
			link1 = await bot.create_chat_invite_link(channel_id, expire_date=expire, member_limit=1)
			link2 = await bot.create_chat_invite_link(channel2_id, expire_date=expire, member_limit=1)
			return aio_web.json_response({"link1": link1.invite_link, "link2": link2.invite_link, "ok": True})
		except Exception as e:
			return aio_web.json_response({"link1": config.bot_channel_link, "link2": config.bot_channel2_link, "ok": False, "err": str(e)})

	async def handle_check(request):
		try:
			uid = int(request.query.get("uid", 0))
			result = await check_subscription(uid)
			return aio_web.json_response({"subscribed": result, "ok": True})
		except Exception as e:
			return aio_web.json_response({"subscribed": False, "ok": False, "err": str(e)})

	async def handle_mirror_list(request):
		try:
			from mirror_manager import get_running_tokens
			running = get_running_tokens()
			return aio_web.json_response({"count": len(running), "ok": True})
		except Exception as e:
			return aio_web.json_response({"ok": False, "err": str(e)})

	async def handle_free_mirror(request):
		"""Возвращает токен наименее загруженного из ЗАПУЩЕННЫХ зеркал."""
		try:
			from mirror_manager import get_running_tokens
			running = get_running_tokens()
			if not running:
				return aio_web.json_response({"token": None, "ok": False, "err": "no running mirrors"})
			exclude = request.query.get("exclude")
			# Считаем назначения только среди запущенных
			pool = await db.get_pool()
			async with pool.acquire() as conn:
				rows = await conn.fetch("""
					SELECT m.token, COUNT(a.user_id) as cnt
					FROM mirrors m
					LEFT JOIN mirror_assignments a ON a.mirror_token = m.token
					WHERE m.token = ANY($1::text[])
					GROUP BY m.token
					ORDER BY cnt ASC
				""", running)
			for row in rows:
				if row["token"] != exclude:
					return aio_web.json_response({"token": row["token"], "ok": True})
			# Если всё занято — берём первый
			return aio_web.json_response({"token": running[0], "ok": True})
		except Exception as e:
			return aio_web.json_response({"token": None, "ok": False, "err": str(e)})

	app = aio_web.Application()
	app.router.add_get("/invite", handle_invite)
	app.router.add_get("/check", handle_check)
	app.router.add_get("/mirrors", handle_mirror_list)
	app.router.add_get("/free_mirror", handle_free_mirror)

	runner = aio_web.AppRunner(app)
	await runner.setup()
	# Если порт занят — ждём и пробуем снова
	for _attempt in range(10):
		try:
			site = aio_web.TCPSite(runner, "127.0.0.1", 8181)
			await site.start()
			print("[API] HTTP сервер запущен на localhost:8181", flush=True)
			return
		except OSError:
			print(f"[API] Порт 8181 занят, жду 3с... ({_attempt+1}/10)", flush=True)
			await asyncio.sleep(3)
	print("[API] Не удалось запустить на 8181", flush=True)


async def _weekly_leaderboard_loop():
	"""Каждый понедельник в 00:00 МСК объявляет топ-3 и уведомляет победителей."""
	_PRIZES = {1: 150, 2: 75, 3: 50}
	_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

	while True:
		# Секунды до следующего понедельника 00:00 МСК
		_now = now_msk()
		_days_until_mon = (7 - _now.weekday()) % 7 or 7
		_target = (_now + timedelta(days=_days_until_mon)).replace(hour=0, minute=0, second=0, microsecond=0)
		_sleep = max(60, (_target - _now).total_seconds())
		print(f"[LEADERBOARD] Следующий запуск через {_sleep/3600:.1f}ч", flush=True)
		await asyncio.sleep(_sleep)

		# Прошедшая неделя: Пн 00:00 МСК → только что наступивший Пн 00:00
		_now = now_msk()
		_week_end = _now.replace(hour=0, minute=0, second=0, microsecond=0)
		_week_start = _week_end - timedelta(weeks=1)
		_week_label = f"{_week_start.strftime('%d.%m')} — {(_week_end - timedelta(days=1)).strftime('%d.%m')}"

		try:
			_top3 = await db.get_weekly_top3(_week_start, _week_end)
			await db.save_leaderboard_winners(_week_start, _top3)

			_lines = [f"🏆 *Итоги рейтинга* ({_week_label})\n"]
			if _top3:
				for _i, _row in enumerate(_top3, 1):
					_uname = f"@{_row['username']}" if _row['username'] else f"ID {_row['user_id']}"
					_prize = _PRIZES[_i]
					_lines.append(f"{_MEDALS[_i]} {_uname} — {_row['total']} репортов → *{_prize} ⭐*")
				_lines.append("\n_Stars будут зачислены победителям в течение 24ч_")
			else:
				_lines.append("_В эту неделю репортов не было_")

			await bot.send_message(bot_logs, "\n".join(_lines), parse_mode="Markdown")

			for _i, _row in enumerate(_top3, 1):
				_prize = _PRIZES[_i]
				try:
					await bot.send_message(
						_row['user_id'],
						f"{_MEDALS[_i]} *Вы заняли {_i}-е место в рейтинге недели!*\n\n"
						f"🎯 Репортов: *{_row['total']}*\n"
						f"🎁 Награда: *{_prize} ⭐ Telegram Stars*\n\n"
						f"_Stars будут зачислены в течение 24 часов_",
						parse_mode="Markdown"
					)
				except Exception:
					pass
		except Exception as _e:
			print(f"[LEADERBOARD] Ошибка: {_e}", flush=True)

		await asyncio.sleep(60)  # буфер чтобы не сработало дважды


async def on_startup(dp):
	try:
		await bot.delete_webhook(drop_pending_updates=True)
		print("Webhook удалён при старте.", flush=True)
	except Exception as e:
		print(f"Webhook delete error: {e}", flush=True)
	try:
		await bot.get_updates(offset=-1, timeout=0, allowed_updates=[
			'message', 'edited_message', 'callback_query', 'inline_query',
			'chosen_inline_result', 'channel_post', 'edited_channel_post'
		])
		print("allowed_updates сброшены.", flush=True)
	except Exception:
		pass
	try:
		print(f"DATABASE_URL = {os.environ.get('DATABASE_URL', 'НЕ УСТАНОВЛЕНА')[:50]}")
		await db.init_db()
		await db.init_cases_table()
		await db.init_monitors_table()
		await db.init_attack_log_table()
		await db.init_leaderboard_table()
		print("БД инициализирована успешно.")
	except Exception as e:
		print(f"ОШИБКА БД при старте: {e}")
	botnet_set_bot(bot)
	botnet_set_bot2(bot)
	set_bot_snos(bot)
	set_bot_stress(bot)
	set_bot_channel(bot)
	set_bot_aureport(bot)
	set_bot_tida(bot)
	set_bot_bank(bot)
	set_bot_code(bot)
	set_monitor_bot(bot, bot_logs)
	set_bot_profile(bot)
	set_bot_trap(bot)
	set_bot_telegraph(bot)
	set_bot_universal(bot)
	asyncio.ensure_future(monitor_loop())
	from monitor_snos import _telegraph_monitor_loop
	asyncio.ensure_future(_telegraph_monitor_loop())
	asyncio.ensure_future(_sub_expiry_notify_loop())
	asyncio.ensure_future(_weekly_leaderboard_loop())
	# Зеркала запускаем в фоне — основной бот стартует сразу
	asyncio.ensure_future(start_all_mirrors())
	# HTTP API для шлюзовых ботов (приглашения, проверка подписки)
	asyncio.ensure_future(_start_invite_api())
	# Инициализируем таблицы шлюза
	try:
		await db.init_gateway_tables()
	except Exception as e:
		print(f"[GATEWAY] init_gateway_tables: {e}")
	print("Бот запущен.")



# -- Admin panel login notifications --
@dp.callback_query_handler(lambda c: c.data and c.data.startswith(("adm_ok_", "adm_blk_")))
async def admin_login_action(call: types.CallbackQuery):
    _adm_lang = await db.get_lang(call.from_user.id)
    if call.from_user.id not in admins:
        await call.answer(t('err_admin_only', _adm_lang), show_alert=True)
        return
    parts = call.data.split("_")
    action = parts[1]
    login_id = int(parts[2])
    import asyncpg as _apg
    conn = await _apg.connect("postgresql://botuser:botpass123@localhost/botdb")
    suffix = ""
    try:
        row = await conn.fetchrow(
            "SELECT ip, user_agent, geo FROM admin_logins WHERE id=$1", login_id
        )
        if not row:
            await call.answer(t('session_not_found', _adm_lang), show_alert=True)
            return
        if action == "ok":
            await conn.execute("UPDATE admin_logins SET status='confirmed' WHERE id=$1", login_id)
            suffix = "\n\n✅ *Подтверждено*"
        else:
            await conn.execute(
                "INSERT INTO admin_blocklist (ip) VALUES ($1) ON CONFLICT (ip) DO NOTHING", row["ip"]
            )
            await conn.execute("UPDATE admin_logins SET status='blocked' WHERE id=$1", login_id)
            suffix = "\n\n🚫 *Заблокировано*\nIP `" + row["ip"] + "` занесён в чёрный список навсегда"
    finally:
        await conn.close()
    orig = call.message.text or ""
    try:
        await call.message.edit_text(orig + suffix, parse_mode="Markdown")
    except Exception:
        pass
    await call.answer()



# ══════════════════════════════════════════════════════════════════════════════
# МЕДИА — контент-программа
# ══════════════════════════════════════════════════════════════════════════════

MEDIA_ADMIN_ID = 8904492648

MEDIA_INFO = (
    "🎥 *Медиа-программа Brown V2*\n\n"
    "Снимай видео про Brown V2, публикуй на TikTok / YouTube / Shorts — мы платим за просмотры.\n\n"
    "*Выплаты:*\n"
    "• 1.000 просмотров — $1.5\n"
    "• 5.000 просмотров — $5\n"
    "• 15.000 просмотров — $12\n"
    "• 50.000 просмотров — $60\n"
    "• 100.000+ просмотров — $120–$700 (индивидуально)\n\n"
    "*Платформы:* TikTok, YouTube, YouTube Shorts\n"
    "*Оплата:* реальные деньги, вручную\n\n"
    "_Отправь ссылку на видео — админ проверит и назначит выплату._"
)

PLATFORM_NAMES = {'tiktok': 'TikTok', 'youtube': 'YouTube', 'shorts': 'YouTube Shorts'}


@dp.callback_query_handler(lambda c: c.data == 'media', state='*')
async def show_media(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    _lang = 'ru'
    try:
        _lang = await db.get_lang(call.from_user.id)
    except Exception:
        pass
    await call.message.edit_text(MEDIA_INFO, parse_mode='Markdown', reply_markup=keyboards.get_media_markup(_lang))
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == 'media_submit', state='*')
async def media_select_platform(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text(
        "📤 *Отправка видео*\n\nВыбери платформу:",
        parse_mode='Markdown',
        reply_markup=media_platform_markup
    )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('media_p_'), state='*')
async def media_platform_chosen(call: types.CallbackQuery, state: FSMContext):
    platform = call.data.replace('media_p_', '')
    await state.finish()
    await state.update_data(platform=platform)
    await MediaFSM.waiting_link.set()
    pname = PLATFORM_NAMES.get(platform, platform)
    await call.message.edit_text(
        f"🔗 *Платформа: {pname}*\n\nОтправь ссылку на видео:",
        parse_mode='Markdown',
        reply_markup=back_markup
    )
    await call.answer()


@dp.message_handler(state=MediaFSM.waiting_link)
async def media_link_received(message: types.Message, state: FSMContext):
    link = message.text.strip()
    if not (link.startswith('http://') or link.startswith('https://')):
        await message.reply(
            "❌ Пожалуйста, отправь полную ссылку (начинается с https://):"
        )
        return
    data = await state.get_data()
    platform = data.get('platform', 'tiktok')
    pname = PLATFORM_NAMES.get(platform, platform)
    await state.update_data(link=link)
    await message.answer(
        f"*Подтверди отправку:*\n\n"
        f"📌 Платформа: {pname}\n"
        f"🔗 Ссылка: {link}",
        parse_mode='Markdown',
        reply_markup=media_confirm_markup(platform, link)
    )


@dp.callback_query_handler(lambda c: c.data == 'media_confirm', state=MediaFSM.waiting_link)
async def media_confirmed(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    platform = data.get('platform', 'tiktok')
    link = data.get('link', '')
    await state.finish()

    uid = call.from_user.id
    username = call.from_user.username or ''

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO media_submissions (user_id, username, platform, link) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            uid, username, platform, link
        )
        sub_id = row['id']

    pname = PLATFORM_NAMES.get(platform, platform)
    uname_str = f"@{username}" if username else f"ID {uid}"

    # Notify admin
    try:
        await bot.send_message(
            MEDIA_ADMIN_ID,
            f"🎥 *Новая заявка на медиа #{sub_id}*\n\n"
            f"👤 Пользователь: {uname_str}\n"
            f"📌 Платформа: {pname}\n"
            f"🔗 Ссылка: {link}",
            parse_mode='Markdown',
            reply_markup=media_admin_markup(sub_id)
        )
    except Exception:
        pass

    await call.message.edit_text(
        "✅ *Заявка отправлена!*\n\n"
        "Админ проверит видео и свяжется с вами по выплате.",
        parse_mode='Markdown',
        reply_markup=back_markup
    )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == 'media_my', state='*')
async def media_my_submissions(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    uid = call.from_user.id
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, platform, link, status, admin_comment, payout, submitted_at "
            "FROM media_submissions WHERE user_id=$1 ORDER BY submitted_at DESC LIMIT 10",
            uid
        )
    if not rows:
        await call.message.edit_text(
            "📋 *Мои заявки*\n\nУ вас пока нет отправленных видео.",
            parse_mode='Markdown', reply_markup=back_markup
        )
        await call.answer()
        return

    STATUS_ICONS = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}
    text = "📋 *Мои заявки:*\n\n"
    for r in rows:
        icon = STATUS_ICONS.get(r['status'], '❔')
        pname = PLATFORM_NAMES.get(r['platform'], r['platform'])
        text += f"{icon} #{r['id']} | {pname}\n🔗 {r['link'][:50]}...\n"
        if r['status'] == 'approved':
            text += f"   💰 Выплата: {r['payout']}\n"
        elif r['status'] == 'rejected' and r['admin_comment']:
            text += f"   📝 Причина: {r['admin_comment']}\n"
        text += "\n"

    await call.message.edit_text(text, parse_mode='Markdown', reply_markup=back_markup)
    await call.answer()


# ── Admin media handlers ──────────────────────────────────────────────────────

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('media_ok_'), state='*')
async def media_admin_approve(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != MEDIA_ADMIN_ID:
        _ma_lang = await db.get_lang(call.from_user.id)
        await call.answer(t('err_admin_only', _ma_lang), show_alert=True)
        return
    sub_id = int(call.data.split('_')[2])
    await state.update_data(media_sub_id=sub_id)
    await MediaFSM.waiting_approve_comment.set()
    await call.message.reply(
        f"✅ Одобрение заявки #{sub_id}\n\n"
        "Отправь комментарий и сумму выплаты в одном сообщении.\n"
        "Например: `Отличное видео! $5`"
    )
    await call.answer()


@dp.message_handler(state=MediaFSM.waiting_approve_comment)
async def media_admin_approve_comment(message: types.Message, state: FSMContext):
    if message.from_user.id != MEDIA_ADMIN_ID:
        return
    text = message.text.strip()
    data = await state.get_data()
    sub_id = data.get('media_sub_id')
    await state.finish()

    # Split last word as payout if it starts with $ or is a number
    parts = text.rsplit(None, 1)
    if len(parts) == 2 and (parts[1].startswith('$') or parts[1].replace('.','').isdigit()):
        comment = parts[0].strip()
        payout = parts[1]
    else:
        comment = text
        payout = 'назначена'

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE media_submissions SET status='approved', admin_comment=$1, payout=$2 "
            "WHERE id=$3 RETURNING user_id, platform, link",
            comment, payout, sub_id
        )
    if not row:
        await message.reply(f"Ошибка: заявка #{sub_id} не найдена")
        return

    try:
        await bot.send_message(
            row['user_id'],
            f"✅ *Ваша заявка #{sub_id} одобрена!*\n\n"
            f"📝 Комментарий: {comment}\n"
            f"💰 Выплата: {payout}\n\n"
            "📩 По выплате: @TariSmit",
            parse_mode='Markdown'
        )
    except Exception:
        pass

    await message.reply(f"✅ Заявка #{sub_id} одобрена. Пользователь уведомлён.")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('media_rej_'), state='*')
async def media_admin_reject(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != MEDIA_ADMIN_ID:
        _mr_lang = await db.get_lang(call.from_user.id)
        await call.answer(t('err_admin_only', _mr_lang), show_alert=True)
        return
    sub_id = int(call.data.split('_')[2])
    await state.update_data(media_sub_id=sub_id)
    await MediaFSM.waiting_reject_reason.set()
    await call.message.reply(
        f"❌ Отклонение заявки #{sub_id}\n\nОтправь причину отклонения:"
    )
    await call.answer()


@dp.message_handler(state=MediaFSM.waiting_reject_reason)
async def media_admin_reject_reason(message: types.Message, state: FSMContext):
    if message.from_user.id != MEDIA_ADMIN_ID:
        return
    reason = message.text.strip()
    data = await state.get_data()
    sub_id = data.get('media_sub_id')
    await state.finish()

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE media_submissions SET status='rejected', admin_comment=$1 "
            "WHERE id=$2 RETURNING user_id",
            reason, sub_id
        )
    if not row:
        await message.reply(f"Ошибка: заявка #{sub_id} не найдена")
        return

    try:
        await bot.send_message(
            row['user_id'],
            f"❌ *Ваша заявка #{sub_id} отклонена.*\n\n"
            f"📝 Причина: {reason}\n\n"
            "📩 По вопросам: @TariSmit",
            parse_mode='Markdown'
        )
    except Exception:
        pass

    await message.reply(f"❌ Заявка #{sub_id} отклонена. Пользователь уведомлён.")


# ─── Универсальный метод — ввод ссылки ───────────────────────────────────────
@dp.message_handler(state=WaitUniversalFSM.link)
async def universal_step_link(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	raw = message.text.strip()

	fsm_data = await state.get_data()
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror else bot

	parsed = parse_link(raw)

	if parsed["type"] == TYPE_INVALID:
		await _bot.send_message(uid,
			f"❌ *Неверная ссылка*\n`{parsed['error']}`\n\nПопробуйте ещё раз:",
			parse_mode="Markdown", reply_markup=main_menu)
		return

	if parsed["type"] == TYPE_PRIVATE_CHANNEL:
		await state.finish()
		await _bot.send_message(uid,
			"❌ *Приватные ссылки* `t.me/c/...` *не поддерживаются*",
			parse_mode="Markdown", reply_markup=main_menu)
		return

	# Валидация через API
	wait_msg = await _bot.send_message(uid, "🔍 *Проверяю ссылку...*", parse_mode="Markdown")
	parsed = await validate_link(parsed)

	if not parsed.get("valid", True):
		await state.finish()
		await _bot.delete_message(uid, wait_msg.message_id)
		await _bot.send_message(uid,
			f"❌ *Ссылка недействительна*\n`{parsed.get('error', 'Не найдено')}`",
			parse_mode="Markdown", reply_markup=main_menu)
		return

	await _bot.delete_message(uid, wait_msg.message_id)

	# TIDA нужен текст — спрашиваем перед запуском
	tida_needed = parsed["type"] in (TYPE_MESSAGE, TYPE_INVITE, TYPE_BOT, TYPE_USER_CHANNEL)
	if tida_needed:
		await state.update_data(univ_parsed=parsed, _bot_token=_bot_token)
		await dp.current_state(chat=uid, user=uid).set_state(WaitUniversalFSM.tida_text.state)
		link_type_labels = {
			TYPE_MESSAGE: "📨 Ссылка на сообщение",
			TYPE_INVITE: "🔗 Инвайт-ссылка",
			TYPE_BOT: "🤖 Бот",
			TYPE_USER_CHANNEL: "👤 Пользователь/канал",
		}
		ltype = link_type_labels.get(parsed["type"], "")
		await _bot.send_message(uid,
			f"✅ *Ссылка принята* — {ltype}\n"
			f"`{parsed['normalized']}`\n\n"
			"*└─ Опишите нарушение для TIDA-жалобы:*\n"
			"_(1-2 предложения на английском / русском)_",
			parse_mode="Markdown", reply_markup=main_menu)
		return

	# Без TIDA — сразу запуск
	await state.finish()
	status_msg = await _bot.send_message(uid,
		f"⚙️ *Универсальный метод* — `{parsed['normalized']}`\n\n⏳ Запускаю...",
		parse_mode="Markdown")
	cd_state = {
		"user": uid, "admins": admins, "no_kd": no_kd,
		"botnet": last_used_botnet, "botnet2": last_used_botnet2,
		"bot_snos": last_used_bot_snos, "channel": last_used_channel,
		"aureport": last_used_aureport, "tida": last_used_tida, "dsa": last_used_dsa,
	}
	asyncio.create_task(run_universal(parsed, "", uid, username, status_msg.message_id, _bot, cd_state=cd_state))


# ─── Универсальный метод — ввод текста TIDA ──────────────────────────────────
@dp.message_handler(state=WaitUniversalFSM.tida_text)
async def universal_step_tida_text(message: types.Message, state: FSMContext):
	uid = message.from_user.id
	username = message.from_user.username or "None"
	tida_text = message.text.strip()

	fsm_data = await state.get_data()
	parsed = fsm_data.get('univ_parsed', {})
	_bot_token = fsm_data.get('_bot_token')
	_is_mirror = bool(_bot_token and _bot_token != config.TOKEN)
	_bot = Bot(token=_bot_token) if _is_mirror else bot

	await state.finish()

	status_msg = await _bot.send_message(uid,
		f"⚙️ *Универсальный метод* — `{parsed.get('normalized', '')}`\n\n⏳ Запускаю...",
		parse_mode="Markdown")
	cd_state = {
		"user": uid, "admins": admins, "no_kd": no_kd,
		"botnet": last_used_botnet, "botnet2": last_used_botnet2,
		"bot_snos": last_used_bot_snos, "channel": last_used_channel,
		"aureport": last_used_aureport, "tida": last_used_tida, "dsa": last_used_dsa,
	}
	asyncio.create_task(run_universal(parsed, tida_text, uid, username, status_msg.message_id, _bot, cd_state=cd_state))


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