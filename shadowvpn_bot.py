"""
ShadowVPN Bot — @ShadowVPN_bot
Запуск: python3 shadowvpn_bot.py
"""
import asyncio
import random
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ParseMode

TOKEN = "8722916608:AAFWoe6jPYRpoNdAclBgv9pMzIusn2W450k"

bot = Bot(token=TOKEN, parse_mode=ParseMode.MARKDOWN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ─── Данные серверов ──────────────────────────────────────────────────────────

SERVERS = [
    {"flag": "🇩🇪", "country": "Германия",     "city": "Frankfurt",  "ping": (12, 28),  "load": (15, 45)},
    {"flag": "🇳🇱", "country": "Нидерланды",   "city": "Amsterdam",  "ping": (18, 35),  "load": (20, 55)},
    {"flag": "🇫🇮", "country": "Финляндия",    "city": "Helsinki",   "ping": (22, 40),  "load": (10, 30)},
    {"flag": "🇫🇷", "country": "Франция",      "city": "Paris",      "ping": (25, 45),  "load": (25, 60)},
    {"flag": "🇨🇭", "country": "Швейцария",    "city": "Zurich",     "ping": (30, 55),  "load": (5,  20)},
    {"flag": "🇸🇪", "country": "Швеция",       "city": "Stockholm",  "ping": (20, 38),  "load": (18, 40)},
    {"flag": "🇺🇸", "country": "США",          "city": "New York",   "ping": (80, 130), "load": (30, 65)},
    {"flag": "🇬🇧", "country": "Великобритания","city": "London",    "ping": (35, 60),  "load": (35, 70)},
    {"flag": "🇯🇵", "country": "Япония",       "city": "Tokyo",      "ping": (120, 180),"load": (10, 35)},
    {"flag": "🇸🇬", "country": "Сингапур",     "city": "Singapore",  "ping": (90, 150), "load": (20, 50)},
]

PLANS = [
    {"name": "1 месяц",   "price": 199,  "emoji": "⚡️"},
    {"name": "3 месяца",  "price": 499,  "emoji": "🔥"},
    {"name": "6 месяцев", "price": 799,  "emoji": "💎"},
    {"name": "1 год",     "price": 1299, "emoji": "👑"},
]


def _rand_ping(lo, hi):
    return random.randint(lo, hi)

def _rand_load(lo, hi):
    return random.randint(lo, hi)

def _load_bar(pct):
    filled = round(pct / 10)
    empty  = 10 - filled
    color  = "🟢" if pct < 40 else ("🟡" if pct < 70 else "🔴")
    return color + " " + "█" * filled + "░" * empty + f" {pct}%"


# ─── Клавиатуры ───────────────────────────────────────────────────────────────

def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🌐 Серверы",      callback_data="servers"),
        types.InlineKeyboardButton("📊 Статус VPN",   callback_data="status"),
    )
    kb.add(
        types.InlineKeyboardButton("💳 Купить доступ", callback_data="buy"),
        types.InlineKeyboardButton("👤 Мой профиль",  callback_data="profile"),
    )
    kb.add(types.InlineKeyboardButton("ℹ️ О сервисе", callback_data="about"))
    return kb

def servers_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, s in enumerate(SERVERS):
        load = _rand_load(*s["load"])
        ping = _rand_ping(*s["ping"])
        label = f"{s['flag']} {s['country']} — {ping}ms · {load}%"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"server_{i}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="main"))
    return kb

def buy_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, p in enumerate(PLANS):
        kb.add(types.InlineKeyboardButton(
            f"{p['emoji']} {p['name']} — {p['price']} ₽",
            callback_data=f"plan_{i}"
        ))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="main"))
    return kb

def back_main():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="main"))
    return kb


# ─── Тексты ───────────────────────────────────────────────────────────────────

WELCOME = (
    "🛡 *ShadowVPN* — быстрый и безопасный VPN\n\n"
    "• 10 стран · 50+ серверов\n"
    "• Без логов · AES-256 шифрование\n"
    "• Работает везде — Netflix, Instagram, TikTok\n"
    "• Скорость до *1 Гбит/с*\n\n"
    "Выбери действие:"
)

ABOUT = (
    "🛡 *ShadowVPN*\n\n"
    "*Протоколы:* WireGuard · OpenVPN · V2Ray\n"
    "*Шифрование:* AES-256-GCM\n"
    "*Логи:* отсутствуют (no-log policy)\n"
    "*Серверы:* 50+ в 10 странах\n"
    "*Скорость:* до 1 Гбит/с\n"
    "*Kill Switch:* есть\n"
    "*Устройства:* Android, iOS, Windows, macOS\n\n"
    "💬 Поддержка: @ShadowVPN\\_Support"
)

STATUS_CONNECTED = (
    "🟢 *VPN подключён*\n\n"
    "🌍 *Сервер:* {flag} {country}, {city}\n"
    "⚡️ *Пинг:* {ping} мс\n"
    "📶 *Скорость:* ↓ {down} Мбит · ↑ {up} Мбит\n"
    "🔐 *Протокол:* WireGuard\n"
    "📦 *Трафик сегодня:* {traffic} МБ\n\n"
    "_Ваши данные надёжно защищены_"
)


# ─── Хендлеры ─────────────────────────────────────────────────────────────────

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer_photo(
        photo="https://i.imgur.com/placeholder.png",  # можно заменить на реальное фото
        caption=WELCOME,
        reply_markup=main_menu()
    )


@dp.callback_query_handler(lambda c: c.data == "main")
async def cb_main(call: types.CallbackQuery):
    try:
        await call.message.edit_caption(caption=WELCOME, reply_markup=main_menu())
    except Exception:
        await call.message.edit_text(WELCOME, reply_markup=main_menu())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "servers")
async def cb_servers(call: types.CallbackQuery):
    text = "🌐 *Список серверов*\n_Выбери сервер для подключения:_\n"
    try:
        await call.message.edit_caption(caption=text, reply_markup=servers_menu())
    except Exception:
        await call.message.edit_text(text, reply_markup=servers_menu())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("server_"))
async def cb_server(call: types.CallbackQuery):
    idx = int(call.data.split("_")[1])
    s   = SERVERS[idx]
    ping  = _rand_ping(*s["ping"])
    load  = _rand_load(*s["load"])
    speed_down = round(random.uniform(80, 950), 1)
    speed_up   = round(random.uniform(40, 500), 1)
    text = (
        f"{s['flag']} *{s['country']}* — {s['city']}\n\n"
        f"⚡️ *Пинг:* {ping} мс\n"
        f"📶 *Скорость:* ↓ {speed_down} · ↑ {speed_up} Мбит/с\n"
        f"💻 *Загрузка:*\n{_load_bar(load)}\n\n"
        f"🔐 *Протокол:* WireGuard\n"
        f"🛡 *Шифрование:* AES-256-GCM\n\n"
        f"_Нажми «Подключиться» после покупки доступа_"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💳 Подключиться", callback_data="buy"),
        types.InlineKeyboardButton("🔙 Серверы",      callback_data="servers"),
    )
    try:
        await call.message.edit_caption(caption=text, reply_markup=kb)
    except Exception:
        await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "status")
async def cb_status(call: types.CallbackQuery):
    s     = random.choice(SERVERS)
    ping  = _rand_ping(*s["ping"])
    down  = round(random.uniform(100, 800), 1)
    up    = round(random.uniform(50, 400), 1)
    traf  = random.randint(50, 2000)
    text  = STATUS_CONNECTED.format(
        flag=s["flag"], country=s["country"], city=s["city"],
        ping=ping, down=down, up=up, traffic=traf
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Обновить",      callback_data="status"),
        types.InlineKeyboardButton("🌐 Сменить сервер", callback_data="servers"),
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="main"))
    try:
        await call.message.edit_caption(caption=text, reply_markup=kb)
    except Exception:
        await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "buy")
async def cb_buy(call: types.CallbackQuery):
    text = (
        "💳 *Тарифные планы ShadowVPN*\n\n"
        "✅ Безлимитный трафик\n"
        "✅ Все серверы включены\n"
        "✅ До 5 устройств\n"
        "✅ Kill Switch + No-log\n\n"
        "Выбери тариф:"
    )
    try:
        await call.message.edit_caption(caption=text, reply_markup=buy_menu())
    except Exception:
        await call.message.edit_text(text, reply_markup=buy_menu())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("plan_"))
async def cb_plan(call: types.CallbackQuery):
    idx  = int(call.data.split("_")[1])
    plan = PLANS[idx]
    text = (
        f"{plan['emoji']} *{plan['name']}* — {plan['price']} ₽\n\n"
        "Выберите способ оплаты:"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💳 Банковская карта (₽)", callback_data=f"pay_card_{idx}"),
        types.InlineKeyboardButton("₿ Криптовалюта (USDT)",   callback_data=f"pay_crypto_{idx}"),
        types.InlineKeyboardButton("🔙 Назад",                 callback_data="buy"),
    )
    try:
        await call.message.edit_caption(caption=text, reply_markup=kb)
    except Exception:
        await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("pay_card_"))
async def cb_pay_card(call: types.CallbackQuery):
    await call.answer(
        "⏳ Оплата картой временно недоступна.\nМы уже подключаем платёжную систему — скоро!",
        show_alert=True
    )


@dp.callback_query_handler(lambda c: c.data.startswith("pay_crypto_"))
async def cb_pay_crypto(call: types.CallbackQuery):
    await call.answer(
        "⏳ Оплата криптовалютой временно недоступна.\nМы уже подключаем платёжную систему — скоро!",
        show_alert=True
    )


@dp.callback_query_handler(lambda c: c.data == "profile")
async def cb_profile(call: types.CallbackQuery):
    uid  = call.from_user.id
    name = call.from_user.first_name or "Пользователь"
    text = (
        f"👤 *Профиль*\n\n"
        f"*Имя:* {name}\n"
        f"*ID:* `{uid}`\n\n"
        f"📦 *Подписка:* не активна\n"
        f"⏰ *Истекает:* —\n"
        f"🌐 *Устройств:* 0 / 5\n\n"
        f"_Купи доступ чтобы активировать VPN_"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💳 Купить доступ", callback_data="buy"),
        types.InlineKeyboardButton("🔙 Назад",         callback_data="main"),
    )
    try:
        await call.message.edit_caption(caption=text, reply_markup=kb)
    except Exception:
        await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "about")
async def cb_about(call: types.CallbackQuery):
    try:
        await call.message.edit_caption(caption=ABOUT, reply_markup=back_main())
    except Exception:
        await call.message.edit_text(ABOUT, reply_markup=back_main())
    await call.answer()


# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🛡 ShadowVPN Bot запущен")
    executor.start_polling(dp, skip_updates=True)
