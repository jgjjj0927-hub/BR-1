# coding: utf-8
"""
Brown V2 | dsa_snos.py
DSA Report метод — жалобы через telegram.org/dsa-report
Капча: Cloudflare Turnstile через CapMonster Cloud API
Браузер: Playwright headless (Chromium)
"""

import asyncio
import random
import os
import logging
import aiohttp
from pathlib import Path
from playwright.async_api import async_playwright, Page

import config
from config import bot_logs
import keyboards
from utils import now_msk

logger = logging.getLogger(__name__)

# ─── Конфиг ──────────────────────────────────────────────────────────────────
CAPMONSTER_KEY = os.environ.get("CAPMONSTER_KEY", config.CAPMONSTER_KEY)
TURNSTILE_SITEKEY = "0x4AAAAAAADnPIDROrmt1Wwj"  # sitekey telegram.org/dsa-report
TARGET_URL = "https://telegram.org/dsa-report"

DSA_DIR = os.path.join(os.path.dirname(__file__), "dsa_data")

bot = None
main_bot = None


def set_bot_dsa(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b


def _get_random_line(filename: str) -> str:
    path = os.path.join(DSA_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        return random.choice(lines) if lines else ""
    except FileNotFoundError:
        logger.warning(f"[DSA] файл не найден: {path}")
        return ""


# ─── CapMonster — решение Turnstile ──────────────────────────────────────────
async def _solve_turnstile(page_url: str) -> str | None:
    """Отправляет задачу в CapMonster, возвращает токен или None."""
    async with aiohttp.ClientSession() as session:
        # Создаём задачу
        payload = {
            "clientKey": CAPMONSTER_KEY,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": TURNSTILE_SITEKEY,
            }
        }
        try:
            async with session.post(
                "https://api.capmonster.cloud/createTask",
                json=payload, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                data = await resp.json()
        except Exception as e:
            logger.error(f"[DSA] CapMonster createTask error: {e}")
            return None

        if data.get("errorId") != 0:
            logger.error(f"[DSA] CapMonster error: {data.get('errorDescription')}")
            return None

        task_id = data.get("taskId")
        logger.info(f"[DSA] CapMonster taskId={task_id}, ждём решения...")

        # Ждём результат
        for _ in range(60):
            await asyncio.sleep(3)
            try:
                async with session.post(
                    "https://api.capmonster.cloud/getTaskResult",
                    json={"clientKey": CAPMONSTER_KEY, "taskId": task_id},
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    result = await resp.json()
            except Exception as e:
                logger.warning(f"[DSA] CapMonster getTaskResult error: {e}")
                continue

            if result.get("status") == "ready":
                token = result.get("solution", {}).get("token")
                logger.info(f"[DSA] Turnstile токен получен")
                return token
            elif result.get("errorId") != 0:
                logger.error(f"[DSA] CapMonster task error: {result.get('errorDescription')}")
                return None

    logger.error("[DSA] CapMonster timeout — токен не получен за 3 мин")
    return None


# ─── Вспомогательные функции для заполнения формы ────────────────────────────
async def _wait_element(page: Page, selector: str, timeout: float = 30.0) -> bool:
    try:
        await page.wait_for_selector(selector, timeout=timeout * 1000)
        return True
    except Exception:
        return False


def _xpath_text(text: str) -> str:
    if "'" not in text:
        return f"//*[text()='{text}']"
    parts = text.split("'")
    concat_args = ", \"'\", ".join(f"'{p}'" for p in parts)
    return f"//*[text()=concat({concat_args})]"


async def _click_radio(page: Page, text: str, timeout: int = 15000) -> bool:
    xpath = _xpath_text(text)
    try:
        await page.wait_for_selector(xpath, timeout=timeout)
    except Exception:
        logger.warning(f"[DSA] radio '{text}' не появился")
        return False

    for attempt_selector in [
        f"span.radio-label >> text={text}",
        f"label.radio-item >> text={text}",
        xpath,
    ]:
        try:
            el = page.locator(attempt_selector).first
            if await el.is_visible(timeout=2000):
                await el.click(force=True)
                logger.info(f"[DSA] radio клик: '{text}'")
                return True
        except Exception:
            continue

    logger.warning(f"[DSA] не удалось кликнуть radio '{text}'")
    return False


async def _type_text(page: Page, text: str):
    """Вводит текст с человеческой скоростью."""
    for ch in text:
        await page.keyboard.type(ch, delay=random.randint(30, 80))


async def _fill_input_and_send(page: Page, text: str) -> bool:
    """Ждёт поле ввода, вводит текст, нажимает Send."""
    if not await _wait_element(page, ".cd-comment-input", timeout=30):
        logger.warning("[DSA] поле ввода не найдено")
        return False
    await asyncio.sleep(random.uniform(0.3, 0.6))
    await page.locator(".cd-comment-input").first.click()
    await asyncio.sleep(0.1)
    await _type_text(page, text)
    await asyncio.sleep(random.uniform(0.2, 0.4))
    await page.locator(".cd-submit-comment-btn").first.click()
    return True


# ─── Основной флоу одного репорта ────────────────────────────────────────────
async def _run_single_report(target_link: str) -> bool:
    """Запускает один DSA репорт. Возвращает True если успешно."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1920,1080",
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="en-US",
        )

        # Антидетект
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        page = await context.new_page()

        try:
            logger.info(f"[DSA] открываем {TARGET_URL}")
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # ─── Решаем Turnstile через CapMonster ───────────────────────────
            logger.info("[DSA] запрашиваем решение Turnstile у CapMonster...")
            token = await _solve_turnstile(TARGET_URL)
            if not token:
                logger.error("[DSA] не получили токен капчи")
                return False

            # Вставляем токен в страницу и активируем кнопку
            await page.evaluate(f"""
                (token) => {{
                    // Вставляем токен в скрытое поле Turnstile
                    const inputs = document.querySelectorAll('input[name="cf-turnstile-response"], input[id*="cf-chl-widget"]');
                    inputs.forEach(el => {{ el.value = token; }});
                    // Вызываем callback если есть
                    if (window.onTurnstileSuccess) window.onTurnstileSuccess(token);
                    if (window.turnstileCallback) window.turnstileCallback(token);
                    // Активируем кнопку напрямую
                    const btn = document.querySelector('.js-report-start-btn');
                    if (btn) {{
                        btn.removeAttribute('disabled');
                        btn.classList.remove('disabled');
                    }}
                }}
            """, token)

            await asyncio.sleep(1)

            # ─── Кликаем Report без логина ───────────────────────────────────
            logger.info("[DSA] кликаем Report button...")
            btn = await page.query_selector(".js-report-start-btn")
            if btn:
                # Ждём popup с login
                try:
                    async with page.expect_popup(timeout=8000) as popup_info:
                        await btn.click()
                    oauth_page = await popup_info.value
                    await oauth_page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await asyncio.sleep(1)

                    # Кликаем "without logging in"
                    for sel in ["a[href*='unauth=1']", ".login_footer_text a",
                                "a:has-text('without logging in')"]:
                        try:
                            el = await oauth_page.wait_for_selector(sel, timeout=3000, state="visible")
                            if el:
                                await el.click()
                                logger.info("[DSA] кликнули 'without logging in'")
                                await asyncio.sleep(2)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"[DSA] popup не открылся: {e}, пробуем прямой клик")
                    await btn.click()
                    await asyncio.sleep(2)

            # ─── Заполняем форму ─────────────────────────────────────────────
            # Ждём поле ввода ссылки
            if not await _wait_element(page, ".cd-comment-input", timeout=20):
                logger.error("[DSA] форма не загрузилась")
                return False

            # Шаг 1: вставляем ссылку
            logger.info("[DSA] шаг 1: вставляем ссылку")
            await _fill_input_and_send(page, target_link)
            await asyncio.sleep(1)

            # Шаг 2: выбираем категорию
            logger.info("[DSA] шаг 2: Personal data")
            await _click_radio(page, "Personal data")
            await asyncio.sleep(0.8)
            await _click_radio(page, "Other personal information")
            await asyncio.sleep(0.8)

            # Шаг 3: текст жалобы
            logger.info("[DSA] шаг 3: текст жалобы")
            reptext = _get_random_line("reptexts.txt")
            await _fill_input_and_send(page, reptext)
            await asyncio.sleep(1)

            # Шаг 4: ссылка повторно
            logger.info("[DSA] шаг 4: ссылка повторно")
            await _fill_input_and_send(page, target_link)
            await asyncio.sleep(1)

            # Шаг 5: страна
            logger.info("[DSA] шаг 5: Germany")
            await _wait_element(page, ".radio-item, span.radio-label", timeout=15)
            await _click_radio(page, "Germany")
            await asyncio.sleep(0.8)

            # Шаг 6: без документов
            await _click_radio(page, "Proceed without documentation")
            await asyncio.sleep(0.8)

            # Шаг 7: от своего имени
            await _click_radio(page, "My own behalf")
            await asyncio.sleep(0.8)

            # Шаг 8: имя
            logger.info("[DSA] шаг 8: имя")
            name = _get_random_line("names.txt")
            famili = _get_random_line("familis.txt")
            fullname = f"{name} {famili}"
            await _fill_input_and_send(page, fullname)
            await asyncio.sleep(0.8)

            # Шаг 9: адрес
            logger.info("[DSA] шаг 9: адрес")
            address = _get_random_line("adreses.txt")
            await _fill_input_and_send(page, address)
            await asyncio.sleep(0.8)

            # Шаг 10: email
            logger.info("[DSA] шаг 10: email")
            email = _get_random_line("emails.txt")
            await _fill_input_and_send(page, email)
            await asyncio.sleep(0.8)

            # Шаг 11: телефон
            logger.info("[DSA] шаг 11: телефон")
            phone = _get_random_line("numbers.txt")
            await _fill_input_and_send(page, phone)
            await asyncio.sleep(0.8)

            # Шаг 12: нет судебного приказа
            await _click_radio(page, "I don't have a court order")
            await asyncio.sleep(0.8)

            # Шаг 13: Confirm
            await _click_radio(page, "Confirm")
            await asyncio.sleep(0.8)

            # Шаг 14: подпись
            logger.info("[DSA] шаг 14: подпись")
            await _fill_input_and_send(page, fullname)
            await asyncio.sleep(2)

            logger.info("[DSA] ✅ репорт завершён успешно")
            return True

        except Exception as e:
            logger.error(f"[DSA] ошибка в репорте: {e}")
            return False
        finally:
            await browser.close()


# ─── Главная функция для бота ─────────────────────────────────────────────────
async def main_dsa_snos(target_link: str, user: int, username: str, count: int = 1):
    """
    Запускает DSA репорты.
    count — количество репортов (каждый = 1 решение капчи).
    """
    from aiogram import types as aiogram_types

    # Нормализуем ссылку
    target = target_link.strip()
    if not target.startswith("https://"):
        target = "https://" + target.lstrip("@").replace("t.me/", "https://t.me/", 1)

    logger.info(f"[DSA] запуск | цель: {target} | кол-во: {count} | пользователь: {user}")

    successful = 0
    failed = 0

    for i in range(count):
        logger.info(f"[DSA] репорт {i+1}/{count}...")
        result = await _run_single_report(target)
        if result:
            successful += 1
        else:
            failed += 1
        if i + 1 < count:
            await asyncio.sleep(random.uniform(3, 6))

    now_str = now_msk().strftime("%d.%m.%Y %H:%M:%S")
    target_escaped = target.replace('_', '\\_')

    caption_user = (
        f"🇪🇺 *DSA Report завершён!*\n\n"
        f"🎯 *Цель:* {target_escaped}\n"
        f"🕐 *Время:* {now_str}\n\n"
        f"🟢 *Успешно: {successful}*\n"
        f"🔴 *Не удалось: {failed}*"
    )
    caption_log = (
        f"🇪🇺 *DSA Report*\n\n"
        f"🎯 *Цель:* {target_escaped}\n"
        f"👤 *Пользователь:* {user} (@{username})\n"
        f"🕐 *Время:* {now_str}\n\n"
        f"🟢 *Успешно: {successful}*\n"
        f"🔴 *Не удалось: {failed}*"
    )

    try:
        await bot.send_message(user, caption_user, parse_mode="Markdown",
                               reply_markup=keyboards.main_menu)
        await main_bot.send_message(bot_logs, caption_log, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"[DSA] ошибка отправки результата: {e}")
