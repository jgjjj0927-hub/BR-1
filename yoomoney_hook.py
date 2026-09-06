"""
Brown V2 | yoomoney_hook.py
Принимает HTTP-уведомления от ЮМани, начисляет подписку.

Запуск: python yoomoney_hook.py
Порт:  8081 (должен быть открыт в firewall)

Настройка ЮМани:
  yoomoney.ru → Настройки → Переводы и платежи → HTTP-уведомления
  URL:          http://ВАШ_IP:8081/hook
  Секретное слово: то что в YOOMONEY_SECRET (env или config.py)
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timedelta

from aiohttp import web

import config

logger = logging.getLogger(__name__)

YOOMONEY_WALLET = config.YOOMONEY_WALLET
YOOMONEY_SECRET = config.YOOMONEY_SECRET

# label формат: sub_{user_id}_{plan}
# plan: 1 / 3 / 7 / 30 / forever / premupgrade
PLAN_CONFIG = {
    "1":          {"days": 1,   "amount": 100, "premium": False},
    "3":          {"days": 3,   "amount": 175, "premium": False},
    "7":          {"days": 7,   "amount": 350, "premium": False},
    "30":         {"days": 30,  "amount": 700, "premium": False},
    "forever":    {"days": 999, "amount": 500, "premium": False},
    "premupgrade":{"days": 0,   "amount": 400, "premium": True},
}

_bot_token: str = ""
_bot_logs: int = 0


def _sha1(parts: list[str]) -> str:
    raw = "&".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _verify(data: dict) -> bool:
    if not YOOMONEY_SECRET:
        logger.warning("[YM-HOOK] YOOMONEY_SECRET не задан — пропускаем проверку подписи")
        return True
    expected = _sha1([
        data.get("notification_type", ""),
        data.get("operation_id", ""),
        data.get("amount", ""),
        data.get("currency", ""),
        data.get("datetime", ""),
        data.get("sender", ""),
        data.get("codepro", ""),
        YOOMONEY_SECRET,
        data.get("label", ""),
    ])
    got = data.get("sha1_hash", "")
    ok = expected == got
    if not ok:
        logger.warning(f"[YM-HOOK] SHA1 mismatch: expected={expected} got={got}")
    return ok


async def _notify_user(uid: int, text: str):
    import aiohttp as _aio
    url = f"https://api.telegram.org/bot{_bot_token}/sendMessage"
    payload = {"chat_id": uid, "text": text, "parse_mode": "Markdown"}
    try:
        async with _aio.ClientSession() as s:
            async with s.post(url, json=payload, timeout=_aio.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    logger.warning(f"[YM-HOOK] notify {uid}: HTTP {r.status}")
    except Exception as e:
        logger.warning(f"[YM-HOOK] notify error: {e}")


async def handle_hook(request: web.Request) -> web.Response:
    try:
        data = dict(await request.post())
        logger.info(f"[YM-HOOK] received: {data}")

        if not _verify(data):
            return web.Response(status=403, text="bad sig")

        label = data.get("label", "")
        amount_str = data.get("amount", "0")

        if not label.startswith("sub_"):
            logger.info(f"[YM-HOOK] label not sub_*: {label!r} — ignore")
            return web.Response(text="ok")

        parts = label.split("_")
        if len(parts) < 3:
            logger.warning(f"[YM-HOOK] bad label: {label!r}")
            return web.Response(text="ok")

        uid_str = parts[1]
        plan = "_".join(parts[2:])

        try:
            uid = int(uid_str)
        except ValueError:
            logger.warning(f"[YM-HOOK] bad uid in label: {label!r}")
            return web.Response(text="ok")

        plan_cfg = PLAN_CONFIG.get(plan)
        if plan_cfg is None:
            logger.warning(f"[YM-HOOK] unknown plan: {plan!r}")
            return web.Response(text="ok")

        try:
            paid = float(amount_str)
        except ValueError:
            paid = 0.0

        if paid < plan_cfg["amount"] * 0.95:
            logger.warning(f"[YM-HOOK] amount too low: {paid} < {plan_cfg['amount']}")
            await _notify_user(uid,
                f"⚠️ *Оплата не засчитана*\n"
                f"Сумма {paid}₽ меньше требуемой {plan_cfg['amount']}₽.\n"
                f"Напишите @BR_V2_support"
            )
            return web.Response(text="ok")

        # Начисляем подписку
        import db as db_module
        operation_id = data.get("operation_id", label)

        # Защита от дублей
        if await db_module.is_invoice_used(operation_id):
            logger.info(f"[YM-HOOK] duplicate op_id={operation_id}")
            return web.Response(text="ok")
        await db_module.mark_invoice_used(operation_id, uid)

        if plan_cfg["premium"]:
            await db_module.set_premium(uid, 1)
            await _notify_user(uid,
                "👑 *Премиум активирован!*\n"
                "Все премиум-функции теперь доступны."
            )
            import aiohttp as _aio
            url = f"https://api.telegram.org/bot{_bot_token}/sendMessage"
            async with _aio.ClientSession() as s:
                await s.post(url, json={
                    "chat_id": _bot_logs,
                    "text": f"💳 *YooMoney Premium* `{uid}` — {paid}₽",
                    "parse_mode": "Markdown"
                }, timeout=_aio.ClientTimeout(total=10))
        else:
            days = plan_cfg["days"]
            new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            await db_module.set_subscribe(uid, new_date)

            plan_labels = {
                "1": "1 день", "3": "3 дня", "7": "7 дней",
                "30": "30 дней", "forever": "навсегда"
            }
            plan_name = plan_labels.get(plan, plan)

            await _notify_user(uid,
                f"✅ *Подписка активирована!*\n"
                f"*└─ Тариф:* {plan_name}\n"
                f"*└─ До:* `{new_date}`\n\n"
                f"_Приятного использования!_"
            )

            # Реферальный бонус
            try:
                referrer_id = await db_module.get_referrer_id(uid)
                if referrer_id and days < 900:
                    bonus = max(1, int(days * 0.1))
                    ref_date = (datetime.now() + timedelta(days=bonus)).strftime("%Y-%m-%d %H:%M:%S")
                    await db_module.set_subscribe(referrer_id, ref_date)
                    await _notify_user(referrer_id,
                        f"💰 *Реферальный бонус!*\n"
                        f"*└─ Ваш реферал купил подписку*\n"
                        f"*└─ Вам начислено: +{bonus} день подписки*"
                    )
            except Exception:
                pass

            import aiohttp as _aio
            url = f"https://api.telegram.org/bot{_bot_token}/sendMessage"
            async with _aio.ClientSession() as s:
                await s.post(url, json={
                    "chat_id": _bot_logs,
                    "text": f"💳 *YooMoney* `{uid}` *{plan_name}* — {paid}₽ до `{new_date}`",
                    "parse_mode": "Markdown"
                }, timeout=_aio.ClientTimeout(total=10))

        logger.info(f"[YM-HOOK] ✅ uid={uid} plan={plan} amount={paid}")
        return web.Response(text="ok")

    except Exception as e:
        logger.exception(f"[YM-HOOK] error: {e}")
        return web.Response(status=500, text="error")


def run_hook_server(bot_token: str, bot_logs_id: int, port: int = 8081):
    global _bot_token, _bot_logs
    _bot_token = bot_token
    _bot_logs = bot_logs_id

    logging.basicConfig(level=logging.INFO)
    app = web.Application()
    app.router.add_post("/hook", handle_hook)
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run_hook_server(
        bot_token=config.TOKEN,
        bot_logs_id=config.bot_logs,
        port=8081,
    )
