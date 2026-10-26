import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from keyboards import get_admin_keyboard


DB_PATH = os.getenv("ADMIN_DB_PATH", "admin_data.db")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "8286")

# Укажи свой Telegram ID в переменной окружения ADMIN_IDS.
# Пример: ADMIN_IDS=123456789,987654321
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}

# Авторизованные в текущем процессе администраторы.
AUTHORIZED_ADMINS = set()


class AdminStates(StatesGroup):
    password = State()
    user_id = State()
    amount = State()


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_admin_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                user_id INTEGER PRIMARY KEY,
                subscription_until TEXT,
                premium_until TEXT,
                reports INTEGER NOT NULL DEFAULT 0,
                banned INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_settings (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO admin_settings (name, value)
            VALUES ('maintenance', '0')
        """)


def get_user(user_id):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM admin_users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        return dict(row) if row else None


def ensure_user(user_id):
    with connect_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO admin_users (user_id) VALUES (?)",
            (user_id,),
        )


def get_setting(name, default="0"):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT value FROM admin_settings WHERE name = ?",
            (name,),
        ).fetchone()

    return row["value"] if row else default


def set_setting(name, value):
    with connect_db() as conn:
        conn.execute("""
            INSERT INTO admin_settings (name, value)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET value = excluded.value
        """, (name, str(value)))


def admin_allowed(user_id):
    return user_id in ADMIN_IDS and user_id in AUTHORIZED_ADMINS


def register_admin_handlers(dp: Dispatcher):
    init_admin_db()

    @dp.message_handler(commands=["admin"], state="*")
    async def admin_command(message: types.Message, state):
        uid = message.from_user.id

        if uid not in ADMIN_IDS:
            await message.answer("⛔ У тебя нет доступа к админ-панели.")
            return

        await state.finish()
        await AdminStates.password.set()
        await message.answer("🔐 Введи пароль администратора:")

    @dp.message_handler(state=AdminStates.password)
    async def check_password(message: types.Message, state):
        uid = message.from_user.id

        if uid not in ADMIN_IDS:
            await state.finish()
            return

        if message.text != ADMIN_PASSWORD:
            await state.finish()
            await message.answer("❌ Неверный пароль.")
            return

        AUTHORIZED_ADMINS.add(uid)
        await state.finish()

        maintenance = get_setting("maintenance") == "1"
        await message.answer(
            "⚙️ Админ-панель открыта.",
            reply_markup=get_admin_keyboard(maintenance),
        )

    @dp.callback_query_handler(Text(startswith="adm:"), state="*")
    async def admin_callback(call: types.CallbackQuery, state):
        uid = call.from_user.id

        if not admin_allowed(uid):
            await call.answer("Нет доступа.", show_alert=True)
            return

        action = call.data.split(":", 1)[1]

        if action == "maintenance":
            new_value = "0" if get_setting("maintenance") == "1" else "1"
            set_setting("maintenance", new_value)

            await call.message.edit_reply_markup(
                reply_markup=get_admin_keyboard(new_value == "1")
            )
            await call.answer(
                "Техработы включены." if new_value == "1"
                else "Техработы выключены."
            )
            return

        prompts = {
            "sub": ("Введи Telegram ID пользователя для выдачи подписки:", "subscription_add"),
            "unsub": ("Введи Telegram ID пользователя для снятия подписки:", "subscription_remove"),
            "prem": ("Введи Telegram ID пользователя для выдачи премиума:", "premium_add"),
            "unprem": ("Введи Telegram ID пользователя для снятия премиума:", "premium_remove"),
            "reports_add": ("Введи Telegram ID пользователя для добавления репортов:", "reports_add"),
            "reports_remove": ("Введи Telegram ID пользователя для снятия репортов:", "reports_remove"),
            "ban": ("Введи Telegram ID пользователя для блокировки в системе админки:", "ban"),
            "unban": ("Введи Telegram ID пользователя для разблокировки:", "unban"),
        }

        if action not in prompts:
            await call.answer("Неизвестное действие.", show_alert=True)
            return

        prompt, operation = prompts[action]
        await state.finish()
        await state.update_data(operation=operation)
        await AdminStates.user_id.set()

        await call.message.answer(prompt)
        await call.answer()

    @dp.message_handler(state=AdminStates.user_id)
    async def receive_user_id(message: types.Message, state):
        if not admin_allowed(message.from_user.id):
            await state.finish()
            return

        try:
            target_id = int(message.text.strip())
            if target_id <= 0:
                raise ValueError
        except (ValueError, AttributeError):
            await message.answer("❌ Нужен числовой Telegram ID. Попробуй ещё раз.")
            return

        data = await state.get_data()
        operation = data.get("operation")

        if operation in ("subscription_add", "premium_add", "reports_add", "reports_remove"):
            await state.update_data(target_id=target_id)
            await AdminStates.amount.set()

            if operation in ("subscription_add", "premium_add"):
                await message.answer("На сколько дней выдать доступ? Введи целое число больше нуля:")
            else:
                await message.answer("Сколько репортов добавить или убрать? Введи целое число больше нуля:")
            return

        ensure_user(target_id)

        if operation == "subscription_remove":
            with connect_db() as conn:
                conn.execute(
                    "UPDATE admin_users SET subscription_until = NULL WHERE user_id = ?",
                    (target_id,),
                )
            result = "Подписка снята."

        elif operation == "premium_remove":
            with connect_db() as conn:
                conn.execute(
                    "UPDATE admin_users SET premium_until = NULL WHERE user_id = ?",
                    (target_id,),
                )
            result = "Премиум снят."

        elif operation == "ban":
            with connect_db() as conn:
                conn.execute(
                    "UPDATE admin_users SET banned = 1 WHERE user_id = ?",
                    (target_id,),
                )
            result = "Пользователь отмечен как заблокированный в базе админки."

        elif operation == "unban":
            with connect_db() as conn:
                conn.execute(
                    "UPDATE admin_users SET banned = 0 WHERE user_id = ?",
                    (target_id,),
                )
            result = "Блокировка в базе админки снята."

        else:
            result = "Неизвестная операция."

        await state.finish()
        await message.answer(f"✅ {result}")

    @dp.message_handler(state=AdminStates.amount)
    async def receive_amount(message: types.Message, state):
        if not admin_allowed(message.from_user.id):
            await state.finish()
            return

        try:
            amount = int(message.text.strip())
            if amount <= 0:
                raise ValueError
        except (ValueError, AttributeError):
            await message.answer("❌ Введи целое число больше нуля.")
            return

        data = await state.get_data()
        operation = data["operation"]
        target_id = data["target_id"]
        ensure_user(target_id)

        with connect_db() as conn:
            if operation in ("subscription_add", "premium_add"):
                column = (
                    "subscription_until"
                    if operation == "subscription_add"
                    else "premium_until"
                )

                row = conn.execute(
                    f"SELECT {column} FROM admin_users WHERE user_id = ?",
                    (target_id,),
                ).fetchone()

                current_value = row[column]
                now = datetime.utcnow()

                if current_value:
                    try:
                        existing = datetime.fromisoformat(current_value)
                        if existing > now:
                            now = existing
                    except ValueError:
                        pass

                until = (now + timedelta(days=amount)).isoformat(timespec="seconds")
                conn.execute(
                    f"UPDATE admin_users SET {column} = ? WHERE user_id = ?",
                    (until, target_id),
                )
                result = f"Доступ выдан до {until} UTC."

            elif operation == "reports_add":
                conn.execute(
                    "UPDATE admin_users SET reports = reports + ? WHERE user_id = ?",
                    (amount, target_id),
                )
                result = f"Добавлено репортов: {amount}."

            elif operation == "reports_remove":
                conn.execute(
                    """UPDATE admin_users
                       SET reports = MAX(0, reports - ?)
                       WHERE user_id = ?""",
                    (amount, target_id),
                )
                result = f"Убрано репортов: {amount}."

            else:
                result = "Неизвестная операция."

        await state.finish()
        await message.answer(f"✅ {result}")

    @dp.message_handler(commands=["admin_cancel"], state="*")
    async def cancel_admin(message: types.Message, state):
        await state.finish()
        await message.answer("Действие отменено.")
