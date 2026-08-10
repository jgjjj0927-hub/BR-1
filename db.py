"""
Модуль для работы с PostgreSQL (Supabase) через asyncpg.
Все таблицы создаются автоматически при первом запуске.
"""
import asyncpg
import asyncio
import os
from datetime import datetime

# Connection string берётся из переменной окружения DATABASE_URL
# На сервере (Render) задаётся через Environment Variables
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:Alishka2010@@db.oaisjipniprzcyugxndj.supabase.co:5432/postgres"
)

_pool: asyncpg.Pool = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:  # double-check
                _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool


async def init_db():
    """Создаёт все таблицы если их нет."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                subscribe TIMESTAMP DEFAULT '1999-01-01 20:00:00',
                premium INT DEFAULT 0,
                verified INT DEFAULT 0,
                referrer_id BIGINT DEFAULT NULL,
                referral_count INT DEFAULT 0,
                free_reports INT DEFAULT 0,
                wheel_last_spin TIMESTAMP DEFAULT '1999-01-01 00:00:00'
            )
        """)
        # Добавляем новые колонки если их нет (для существующих БД)
        for col, definition in [
            ("referrer_id", "BIGINT DEFAULT NULL"),
            ("referral_count", "INT DEFAULT 0"),
            ("free_reports", "INT DEFAULT 0"),
            ("wheel_last_spin", "TIMESTAMP DEFAULT '1999-01-01 00:00:00'"),
            ("wheel_prize", "TEXT DEFAULT ''"),
            ("username", "TEXT DEFAULT ''"),
        ]:
            try:
                await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {definition}")
            except Exception:
                pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS promocode (
                code TEXT UNIQUE,
                days INT,
                activations INT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                user_id BIGINT PRIMARY KEY
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blocked (
                user_id BIGINT PRIMARY KEY
            )
        """)
    await init_mirrors_table()
    await _init_paid_invoices_table()
    # Создаём таблицу использований промокодов
    pool_db = await get_pool()
    async with pool_db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS promo_uses (
                code TEXT NOT NULL,
                user_id BIGINT NOT NULL,
                PRIMARY KEY (code, user_id)
            )
        """)
        # Фикс NULL значений для старых пользователей
        await conn.execute("UPDATE users SET premium = 0 WHERE premium IS NULL")
        await conn.execute("UPDATE users SET free_reports = 0 WHERE free_reports IS NULL")
        await conn.execute("UPDATE users SET referral_count = 0 WHERE referral_count IS NULL")
        await conn.execute("UPDATE users SET verified = 0 WHERE verified IS NULL")
        await conn.execute("UPDATE users SET mirror_bonus_given = 0 WHERE mirror_bonus_given IS NULL")


# ─── Users ────────────────────────────────────────────────────────────────────

async def user_exists(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1", user_id)
        return row is not None


async def add_user(user_id: int, username: str = ''):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO users (user_id, subscribe, premium, verified, username)
               VALUES ($1, $2, 0, 0, $3)
               ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username""",
            user_id, datetime(1999, 1, 1, 20, 0, 0), username or ''
        )


async def get_user(user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not row:
            return None
        d = dict(row)
        # Заменяем None на дефолтные значения для колонок добавленных позже
        d['premium'] = d.get('premium') or 0
        d['free_reports'] = d.get('free_reports') or 0
        d['referral_count'] = d.get('referral_count') or 0
        d['verified'] = d.get('verified') or 0
        d['mirror_bonus_given'] = d.get('mirror_bonus_given') or 0
        return d


async def set_subscribe(user_id: int, new_date, force: bool = False):
    pool = await get_pool()
    # asyncpg требует datetime объект, не строку
    if isinstance(new_date, str):
        new_date = datetime.strptime(new_date[:19], "%Y-%m-%d %H:%M:%S")
    async with pool.acquire() as conn:
        if not force:
            # Продлеваем подписку: если текущая в будущем — прибавляем к ней, иначе к now()
            current = await conn.fetchval("SELECT subscribe FROM users WHERE user_id = $1", user_id)
            if current and current > datetime.now():
                delta = new_date - datetime.now()
                new_date = current + delta
        await conn.execute(
            "UPDATE users SET subscribe = $1 WHERE user_id = $2",
            new_date, user_id
        )


async def set_premium(user_id: int, value: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET premium = $1 WHERE user_id = $2",
            value, user_id
        )


async def set_verified(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET verified = 1 WHERE user_id = $1",
            user_id
        )


async def is_verified(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT verified FROM users WHERE user_id = $1", user_id)
        return bool(row["verified"]) if row else False


async def get_all_user_ids() -> list[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [r["user_id"] for r in rows]


async def get_users_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")


# ─── Blocked ──────────────────────────────────────────────────────────────────

async def is_blocked(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM blocked WHERE user_id = $1", user_id)
        return row is not None


async def block_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO blocked (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id
        )

async def unblock_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM blocked WHERE user_id = $1", user_id)


async def delete_user(user_id: int):
    """Полностью удаляет пользователя из БД (users + blocked + зеркала)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM blocked WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM mirrors WHERE user_id = $1", user_id)


# ─── Whitelist ────────────────────────────────────────────────────────────────

async def get_whitelist() -> list[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM whitelist")
        return [r["user_id"] for r in rows]


async def add_to_whitelist(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO whitelist (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id
        )


# ─── Promocodes ───────────────────────────────────────────────────────────────

async def get_promo(code: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM promocode WHERE code = $1", code)
        return dict(row) if row else None


async def create_promo(code: str, days: int, activations: int, promo_type: str = 'normal'):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Добавляем колонку promo_type если нет
        try:
            await conn.execute("ALTER TABLE promocode ADD COLUMN IF NOT EXISTS promo_type TEXT DEFAULT 'normal'")
        except Exception:
            pass
        await conn.execute(
            "INSERT INTO promocode (code, days, activations, promo_type) VALUES ($1, $2, $3, $4)",
            code, days, activations, promo_type
        )


async def use_promo(code: str, user_id: int, new_date):
    if isinstance(new_date, str):
        new_date = datetime.strptime(new_date[:19], "%Y-%m-%d %H:%M:%S")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE promocode SET activations = activations - 1 WHERE code = $1",
            code
        )
        # Промокод всегда продлевает относительно текущей даты (force=False через set_subscribe)
        await conn.execute(
            "UPDATE users SET subscribe = $1 WHERE user_id = $2",
            new_date, user_id
        )


async def is_promo_used_by(code: str, user_id: int) -> bool:
    """Проверяет — активировал ли пользователь уже этот промокод."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM promo_uses WHERE code = $1 AND user_id = $2",
            code, user_id
        )
        return row is not None


async def mark_promo_used(code: str, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO promo_uses (code, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            code, user_id
        )


# ─── Рефералы ─────────────────────────────────────────────────────────────────

async def set_referrer(user_id: int, referrer_id: int):
    """Устанавливает реферера для нового пользователя."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET referrer_id = $1 WHERE user_id = $2 AND referrer_id IS NULL",
            referrer_id, user_id
        )


async def increment_referral_count(referrer_id: int) -> int:
    """Увеличивает счётчик рефералов и возвращает новое значение."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE users SET referral_count = referral_count + 1 WHERE user_id = $1 RETURNING referral_count",
            referrer_id
        )
        return row["referral_count"] if row else 0


async def get_referral_count(user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT referral_count FROM users WHERE user_id = $1", user_id)
        return int(row["referral_count"] or 0) if row else 0


async def spend_referrals(user_id: int, amount: int = 10):
    """Снимает amount рефералов у пользователя. Возвращает True если успешно."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE users SET referral_count = referral_count - $1 WHERE user_id = $2 AND referral_count >= $1 RETURNING referral_count",
            amount, user_id
        )
        return row is not None


async def get_referrer_id(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT referrer_id FROM users WHERE user_id = $1", user_id)
        return row["referrer_id"] if row else None


# ─── Бесплатные репорты ───────────────────────────────────────────────────────

async def get_free_reports(user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT free_reports FROM users WHERE user_id = $1", user_id)
        return int(row["free_reports"] or 0) if row else 0


async def add_free_reports(user_id: int, amount: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET free_reports = free_reports + $1 WHERE user_id = $2",
            amount, user_id
        )


async def use_free_report(user_id: int) -> bool:
    """Использует 1 бесплатный репорт. Возвращает True если успешно."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE users SET free_reports = free_reports - 1 WHERE user_id = $1 AND free_reports > 0 RETURNING free_reports",
            user_id
        )
        return row is not None


# ─── Колесо удачи ─────────────────────────────────────────────────────────────

async def get_wheel_last_spin(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT wheel_last_spin FROM users WHERE user_id = $1", user_id)
        return row["wheel_last_spin"] if row else None


async def set_wheel_last_spin(user_id: int, dt):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET wheel_last_spin = $1 WHERE user_id = $2",
            dt, user_id
        )


async def get_wheel_prize(user_id: int) -> str:
    """Возвращает последний выигрыш колеса (чтобы знать, заблокирован ли спин)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow("SELECT wheel_prize FROM users WHERE user_id = $1", user_id)
            return row["wheel_prize"] if row and row["wheel_prize"] else ""
        except Exception:
            return ""


async def set_wheel_prize(user_id: int, prize: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "UPDATE users SET wheel_prize = $1 WHERE user_id = $2",
                prize, user_id
            )
        except Exception:
            pass


# ─── Зеркала ──────────────────────────────────────────────────────────────────

async def init_mirrors_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mirrors (
                token TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                bot_username TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Флаг что бонус за зеркало уже выдан
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS mirror_bonus_given INT DEFAULT 0")
        except Exception:
            pass


async def _init_paid_invoices_table():
    """Таблица для защиты от повторного начисления по одному инвойсу."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS paid_invoices (
                invoice_id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)


async def is_invoice_used(invoice_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM paid_invoices WHERE invoice_id = $1", invoice_id)
        return row is not None


async def mark_invoice_used(invoice_id: str, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO paid_invoices (invoice_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            invoice_id, user_id
        )


async def add_mirror(user_id: int, token: str, bot_username: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO mirrors (token, user_id, bot_username) VALUES ($1, $2, $3)",
            token, user_id, bot_username
        )


async def get_user_mirrors(user_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT token, bot_username, created_at FROM mirrors WHERE user_id = $1 ORDER BY created_at",
            user_id
        )
        return [dict(r) for r in rows]


async def count_user_mirrors(user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM mirrors WHERE user_id = $1", user_id)


async def token_exists(token: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM mirrors WHERE token = $1", token)
        return row is not None


async def get_all_mirror_tokens() -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT token FROM mirrors")
        return [r["token"] for r in rows]


async def remove_mirror_by_token(token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM mirrors WHERE token = $1", token)


async def get_mirror_bonus_given(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT mirror_bonus_given FROM users WHERE user_id = $1", user_id)
        return bool(row["mirror_bonus_given"] or 0) if row else False


async def set_mirror_bonus_given(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET mirror_bonus_given = 1 WHERE user_id = $1", user_id)


async def get_all_mirrors() -> list[dict]:
    """Возвращает все зеркала для админ-панели."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT token, user_id, bot_username, created_at FROM mirrors ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]


async def set_free_reports(user_id: int, amount: int):
    """Устанавливает точное количество бесплатных репортов."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET free_reports = $1 WHERE user_id = $2", amount, user_id)


async def get_users_page(offset: int = 0, limit: int = 10) -> list[dict]:
    """Возвращает страницу пользователей с основными данными."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, subscribe, premium, free_reports FROM users ORDER BY user_id DESC LIMIT $1 OFFSET $2",
            limit, offset
        )
        return [dict(r) for r in rows]


async def get_subscribers_count() -> int:
    """Количество пользователей с активной подпиской."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE subscribe > NOW()"
        )


async def get_users_with_reports_count() -> int:
    """Количество пользователей у которых есть бесплатные репорты."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE free_reports > 0"
        )


async def get_mirrors_count() -> int:
    """Общее количество зеркал."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM mirrors")


async def resolve_user(input_str: str) -> int | None:
    """
    Принимает ID (число) или @username.
    Возвращает user_id или None если не найден.
    """
    input_str = input_str.strip().lstrip('@')
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Если число — ищем по ID
        if input_str.isdigit():
            uid = int(input_str)
            row = await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1", uid)
            return uid if row else None
        # Иначе ищем по username (без @)
        row = await conn.fetchrow(
            "SELECT user_id FROM users WHERE LOWER(username) = LOWER($1)", input_str
        )
        return row["user_id"] if row else None
