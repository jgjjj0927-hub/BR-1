"""
Brown V2 | bank_snos.py
Метод блокировки банковских карт по 115-ФЗ.
Лог летит в bot_logs, реальную блокировку делает администратор вручную.
"""

from config import bot_logs
from aiogram import Bot
import keyboards

bot = None
main_bot = None


def set_bot_bank(b):
    global bot, main_bot
    bot = b
    if main_bot is None:
        main_bot = b


BANKS = {
    "tbank":   "Т-Банк (Тинькофф)",
    "alfa":    "Альфа-Банк",
    "sber":    "Сбер Банк",
    "ozon":    "Озон Банк",
}


async def process_bank_report(bank_key: str, card_data: str, user: int, username: str, notify_bot=None):
    """Отправляет лог в канал и сообщение пользователю."""
    _notify = notify_bot or bot
    bank_name = BANKS.get(bank_key, bank_key)

    caption_user = (
        f"🏦 *Заявка на блокировку карты принята!*\n\n"
        f"*└─ Банк:* {bank_name}\n"
        f"*└─ Данные:* {card_data}\n\n"
        f"⏳ *Примерное время блокировки по 115-ФЗ — 3 дня*\n\n"
        f"_Заявка передана администратору_"
    )

    caption_log = (
        f"🏦 *БЛОКИРОВКА КАРТЫ*\n\n"
        f"*└─ Банк:* {bank_name}\n"
        f"*└─ Данные:* {card_data}\n"
        f"*└─ Пользователь:* {user} (*@{username}*)"
    )

    try:
        await _notify.send_message(user, caption_user, parse_mode="Markdown", reply_markup=keyboards.main_menu)
    except Exception as e:
        print(f"[BANK] Ошибка отправки пользователю: {e}")

    try:
        await main_bot.send_message(bot_logs, caption_log, parse_mode="Markdown")
    except Exception as e:
        print(f"[BANK] Ошибка отправки лога: {e}")
