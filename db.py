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
            ("manual_confirmed", "INT DEFAULT 0"),
            ("lang", "TEXT DEFAULT 'ru'"),
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
    await init_target_whitelist_table()
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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS probiv_usage (
                user_id BIGINT PRIMARY KEY,
                last_request_at TIMESTAMPTZ DEFAULT '1999-01-01 00:00:00+00',
                hour_count INT DEFAULT 0,
                hour_window_start TIMESTAMPTZ DEFAULT '1999-01-01 00:00:00+00'
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
        # Сначала вставляем без username (совместимость со старой схемой)
        await conn.execute(
            "INSERT INTO users (user_id, subscribe, premium, verified) VALUES ($1, $2, 0, 0) ON CONFLICT DO NOTHING",
            user_id, datetime(1999, 1, 1, 20, 0, 0)
        )
        # Обновляем username отдельно (колонка может не существовать на старых БД)
        if username:
            try:
                await conn.execute(
                    "UPDATE users SET username = $1 WHERE user_id = $2",
                    username, user_id
                )
            except Exception:
                pass


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


async def get_lang(user_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT lang FROM users WHERE user_id = $1", user_id)
        if not row:
            return 'ru'
        return row['lang'] or 'ru'


async def set_lang(user_id: int, lang: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("UPDATE users SET lang = $1 WHERE user_id = $2", lang, user_id)
        except Exception:
            pass


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
        # COALESCE защищает от NULL — NULL + N = NULL в PostgreSQL
        await conn.execute(
            "UPDATE users SET free_reports = COALESCE(free_reports, 0) + $1 WHERE user_id = $2",
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


async def is_manual_confirmed(user_id: int) -> bool:
    """Проверяет подтвердил ли пользователь прочтение мануала."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow("SELECT manual_confirmed FROM users WHERE user_id = $1", user_id)
            return bool(row["manual_confirmed"] or 0) if row else False
        except Exception:
            return False


async def set_manual_confirmed(user_id: int):
    """Помечает что пользователь прочитал мануал."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("UPDATE users SET manual_confirmed = 1 WHERE user_id = $1", user_id)
        except Exception:
            pass


# ─── Белый список целей (username/channel) ────────────────────────────────────

async def init_target_whitelist_table():
    """Создаёт таблицу белого списка целей."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS target_whitelist (
                pattern TEXT PRIMARY KEY,
                added_by BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)


async def add_target_whitelist(pattern: str, added_by: int = 0):
    """Добавляет паттерн в белый список целей. Паттерн — username без @, строчными."""
    pattern = pattern.strip().lstrip('@').lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO target_whitelist (pattern, added_by) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            pattern, added_by
        )


async def remove_target_whitelist(pattern: str):
    """Удаляет паттерн из белого списка."""
    pattern = pattern.strip().lstrip('@').lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM target_whitelist WHERE pattern = $1", pattern)


async def get_target_whitelist() -> list[str]:
    """Возвращает все паттерны белого списка."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT pattern FROM target_whitelist ORDER BY created_at")
        return [r["pattern"] for r in rows]


# ─── Кейсы ───────────────────────────────────────────────────────────────────

async def init_cases_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                invoice_id TEXT UNIQUE NOT NULL,
                opened BOOLEAN DEFAULT FALSE,
                prize TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)


async def add_case(user_id: int, invoice_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO cases (user_id, invoice_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            user_id, invoice_id
        )


async def get_unopened_cases(user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM cases WHERE user_id = $1 AND opened = FALSE",
            user_id
        ) or 0


async def open_case(user_id: int) -> str | None:
    """Открывает один кейс, возвращает invoice_id или None если нет кейсов."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM cases WHERE user_id = $1 AND opened = FALSE ORDER BY created_at LIMIT 1",
            user_id
        )
        if not row:
            return None
        await conn.execute(
            "UPDATE cases SET opened = TRUE WHERE id = $1",
            row["id"]
        )
        return str(row["id"])


async def set_case_prize(case_id: str, prize: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE cases SET prize = $1 WHERE id = $2",
            prize, int(case_id)
        )


async def is_target_whitelisted(target: str) -> bool:
    """
    Проверяет — находится ли цель в белом списке.
    target — username без @, строчными.
    Сравниваем: если паттерн совпадает с началом username (первые N символов) или полностью.
    """
    target = target.strip().lstrip('@').lower()
    patterns = await get_target_whitelist()
    for p in patterns:
        # Точное совпадение ИЛИ username начинается с паттерна
        if target == p or target.startswith(p):
            return True
    return False


# ─── Кейсы ────────────────────────────────────────────────────────────────────

async def init_cases_table():
    """Создаёт таблицу кейсов."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                opened BOOLEAN DEFAULT FALSE,
                invoice_id TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)


async def add_case(user_id: int, invoice_id: str = None) -> int:
    """Добавляет кейс пользователю. Возвращает id кейса."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO cases (user_id, invoice_id) VALUES ($1, $2) RETURNING id",
            user_id, invoice_id
        )
        return row["id"]


async def get_unopened_cases(user_id: int) -> int:
    """Возвращает количество неоткрытых кейсов у пользователя."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM cases WHERE user_id = $1 AND opened = FALSE",
            user_id
        )


async def open_case(user_id: int) -> bool:
    """Открывает один кейс (помечает как opened). Возвращает True если был кейс."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE cases SET opened = TRUE
               WHERE id = (
                   SELECT id FROM cases WHERE user_id = $1 AND opened = FALSE
                   ORDER BY created_at ASC LIMIT 1
               ) RETURNING id""",
            user_id
        )
        return row is not None


async def is_case_invoice_used(invoice_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM cases WHERE invoice_id = $1", invoice_id
        )
        return row is not None


# ─── Мониторинг ───────────────────────────────────────────────────────────────

async def init_monitors_table():
    """Создаёт таблицу мониторов."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS monitors (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                target TEXT NOT NULL,
                status TEXT DEFAULT 'alive',
                active BOOLEAN DEFAULT TRUE,
                notified BOOLEAN DEFAULT FALSE,
                notify_silent BOOLEAN DEFAULT FALSE,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                last_check TIMESTAMP DEFAULT NOW()
            )
        """)
        # Добавляем колонку если её нет (для существующих БД)
        await conn.execute("""
            ALTER TABLE monitors ADD COLUMN IF NOT EXISTS notify_silent BOOLEAN DEFAULT FALSE
        """)


async def add_monitor(user_id: int, target: str, expires_at: datetime) -> int:
    """Добавляет монитор. Возвращает id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO monitors (user_id, target, expires_at)
               VALUES ($1, $2, $3) RETURNING id""",
            user_id, target, expires_at
        )
        return row["id"]


async def get_active_monitors() -> list[dict]:
    """Возвращает все активные мониторы."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM monitors WHERE active = TRUE ORDER BY created_at"
        )
        return [dict(r) for r in rows]


async def get_user_monitors(user_id: int) -> list[dict]:
    """Возвращает все мониторы пользователя (включая неактивные)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM monitors WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )
        return [dict(r) for r in rows]


async def get_user_active_monitors_count(user_id: int) -> int:
    """Количество активных мониторов пользователя."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM monitors WHERE user_id = $1 AND active = TRUE",
            user_id
        ) or 0


async def is_target_already_monitored(user_id: int, target: str) -> bool:
    """Проверяет — мониторит ли пользователь уже эту цель."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM monitors WHERE user_id = $1 AND target = $2 AND active = TRUE",
            user_id, target
        )
        return row is not None


async def was_target_monitored_before(user_id: int, target: str) -> bool:
    """Проверяет — мониторил ли пользователь эту цель раньше (нельзя дважды)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM monitors WHERE user_id = $1 AND target = $2",
            user_id, target
        )
        return row is not None


async def update_monitor_check(monitor_id: int, new_status: str):
    """Обновляет статус и время последней проверки."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE monitors SET status = $1, last_check = NOW() WHERE id = $2",
            new_status, monitor_id
        )


async def mark_monitor_notified(monitor_id: int):
    """Помечает монитор как уведомлённый."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE monitors SET notified = TRUE WHERE id = $1",
            monitor_id
        )


async def deactivate_monitor(monitor_id: int):
    """Деактивирует монитор."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE monitors SET active = FALSE WHERE id = $1",
            monitor_id
        )


async def set_monitor_silent(monitor_id: int, user_id: int, silent: bool) -> bool:
    """Включает/выключает тихий режим (без периодических уведомлений). Возвращает True если найден."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE monitors SET notify_silent = $1 WHERE id = $2 AND user_id = $3 RETURNING id",
            silent, monitor_id, user_id
        )
        return row is not None


async def delete_monitor(monitor_id: int, user_id: int) -> bool:
    """Удаляет монитор пользователя. Возвращает True если удалён."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM monitors WHERE id = $1 AND user_id = $2 RETURNING id",
            monitor_id, user_id
        )
        return row is not None


# ─── История атак ─────────────────────────────────────────────────────────────

async def init_attack_log_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS attack_log (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                target_url TEXT NOT NULL,
                method TEXT NOT NULL,
                success_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS attack_log_user_idx ON attack_log(user_id, created_at DESC)")


async def log_attack(user_id: int, target_url: str, method: str, success_count: int = 0):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO attack_log (user_id, target_url, method, success_count) VALUES ($1, $2, $3, $4)",
            user_id, target_url[:500], method, success_count
        )


async def get_attack_history(user_id: int, limit: int = 15) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT target_url, method, success_count, created_at FROM attack_log WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id, limit
        )
        return [dict(r) for r in rows]


# ─── Пробив — лимиты ──────────────────────────────────────────────────────────

async def get_probiv_usage(user_id: int) -> dict:
    """Возвращает данные использования пробива для пользователя."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT last_request_at, hour_count, hour_window_start FROM probiv_usage WHERE user_id = $1",
            user_id
        )
        if not row:
            return {"last_request_at": None, "hour_count": 0, "hour_window_start": None}
        return dict(row)


async def record_probiv_request(user_id: int, now_dt):
    """Записывает новый запрос пробива. Сбрасывает счётчик если прошёл час."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT hour_count, hour_window_start FROM probiv_usage WHERE user_id = $1",
            user_id
        )
        if row is None:
            await conn.execute(
                """INSERT INTO probiv_usage (user_id, last_request_at, hour_count, hour_window_start)
                   VALUES ($1, $2, 1, $2)""",
                user_id, now_dt
            )
        else:
            window = row["hour_window_start"]
            count = row["hour_count"]
            window_cmp = window.replace(tzinfo=None) if (window and getattr(window, "tzinfo", None)) else window
            if window_cmp and (now_dt - window_cmp).total_seconds() < 3600:
                new_count = count + 1
                new_window = window
            else:
                new_count = 1
                new_window = now_dt
            await conn.execute(
                """INSERT INTO probiv_usage (user_id, last_request_at, hour_count, hour_window_start)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (user_id) DO UPDATE
                   SET last_request_at = $2, hour_count = $3, hour_window_start = $4""",
                user_id, now_dt, new_count, new_window
            )
