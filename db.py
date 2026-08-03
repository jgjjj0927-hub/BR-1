"""
Модуль для работы с PostgreSQL (Supabase) через asyncpg.
Все таблицы создаются автоматически при первом запуске.
"""
import asyncpg
import os

# Connection string берётся из переменной окружения DATABASE_URL
# На сервере (Render) задаётся через Environment Variables
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:Alishka2010@@db.oaisjipniprzcyugxndj.supabase.co:5432/postgres"
)

_pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
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
                verified INT DEFAULT 0
            )
        """)
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


# ─── Users ────────────────────────────────────────────────────────────────────

async def user_exists(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1", user_id)
        return row is not None


async def add_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id
        )


async def get_user(user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None


async def set_subscribe(user_id: int, new_date: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
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


async def create_promo(code: str, days: int, activations: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO promocode (code, days, activations) VALUES ($1, $2, $3)",
            code, days, activations
        )


async def use_promo(code: str, user_id: int, new_date: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE promocode SET activations = activations - 1 WHERE code = $1",
            code
        )
        await conn.execute(
            "UPDATE users SET subscribe = $1 WHERE user_id = $2",
            new_date, user_id
        )
