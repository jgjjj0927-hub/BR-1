from aiogram import types
import config

menu = types.InlineKeyboardMarkup(row_width=2)
profile = types.InlineKeyboardButton("📕 Профиль", callback_data='profile')
information = types.InlineKeyboardButton("❓ Информация", callback_data='information')
shop = types.InlineKeyboardButton("🛍 Цены", callback_data='shop')
snoser = types.InlineKeyboardButton("🔥 Открыть панель", callback_data='functions')
promo = types.InlineKeyboardButton("🎁 Промокод", callback_data='promo')
referral_btn = types.InlineKeyboardButton("👥 Рефералы", callback_data='referral')
wheel_btn = types.InlineKeyboardButton("🎡 Колесо репортов", callback_data='wheel')
free_btn = types.InlineKeyboardButton("🆓 Бесплатно", callback_data='free_menu')
mirrors_pub_btn = types.InlineKeyboardButton("🪞 Зеркала", callback_data='public_mirrors')
support_btn = types.InlineKeyboardButton("🆘 Поддержка", url='https://t.me/BR_V2_support')
menu.add(snoser)
menu.add(information, profile)
menu.add(shop, promo)
menu.add(referral_btn, wheel_btn)
menu.add(mirrors_pub_btn, free_btn)
menu.add(support_btn)

# ─── Меню Бесплатно ───────────────────────────────────────────────────────────
free_menu_markup = types.InlineKeyboardMarkup(row_width=1)
free_menu_markup.add(
    types.InlineKeyboardButton("🪞 Создать зеркало", callback_data='mirror_create'),
    types.InlineKeyboardButton("📋 Мои зеркала (5 рандомных)", callback_data='mirror_list'),
    types.InlineKeyboardButton("[🔙] Назад", callback_data='back')
)


back_markup = types.InlineKeyboardMarkup(row_width=2)
back = types.InlineKeyboardButton("[🔙] Назад", callback_data='back')
back_markup.add(back)

functions = types.InlineKeyboardMarkup(row_width=2)
web_method = types.InlineKeyboardButton("🌐 Web", callback_data='web_method')
mail_method = types.InlineKeyboardButton("✉️ Mail", callback_data='mail_method')
botnet_method = types.InlineKeyboardButton("🤖 Обычная Отправка", callback_data='botnet_method')
prem_botnet_method = types.InlineKeyboardButton("👑 Премиальная отправка", callback_data='prem_botnet_method')
bot_method_btn = types.InlineKeyboardButton("🤖 Бот", callback_data='bot_method')
channel_method_btn = types.InlineKeyboardButton("📢 Канал", callback_data='channel_method')
code_method_btn = types.InlineKeyboardButton("📱 Спам кодами", callback_data='code_method')
functions.add(botnet_method)
functions.add(web_method, mail_method)
functions.add(prem_botnet_method)
functions.add(bot_method_btn, channel_method_btn)
functions.add(code_method_btn)
manual_method_btn = types.InlineKeyboardButton("👤 Заказать удаление", callback_data='manual_method')
functions.add(manual_method_btn)
aureport_method_btn = types.InlineKeyboardButton("🇦🇺 AU Report", callback_data='aureport_method')
tida_method_btn = types.InlineKeyboardButton("🟣 TIDA", callback_data='tida_method')
functions.add(aureport_method_btn, tida_method_btn)
bank_method_btn = types.InlineKeyboardButton("🏦 Блокировка карты", callback_data='bank_method')
functions.add(bank_method_btn)
dsa_method_btn = types.InlineKeyboardButton("🇪🇺 DSA Report", callback_data='dsa_method')
functions.add(dsa_method_btn)
logger_method_btn = types.InlineKeyboardButton("🔗 Логгер", callback_data='logger_method')
functions.add(logger_method_btn)

# ─── TIDA тип цели ────────────────────────────────────────────────────────────
tida_target_markup = types.InlineKeyboardMarkup(row_width=1)
tida_target_markup.add(
    types.InlineKeyboardButton("👤 Аккаунт", callback_data='tida_target_account'),
    types.InlineKeyboardButton("🤖 Бот", callback_data='tida_target_bot'),
    types.InlineKeyboardButton("💬 Чат", callback_data='tida_target_chat'),
    types.InlineKeyboardButton("📢 Канал", callback_data='tida_target_channel'),
    types.InlineKeyboardButton("[🔙] Назад", callback_data='back'),
)

# ─── TIDA метод генерации текста ──────────────────────────────────────────────
def tida_text_method_markup(target_type: str) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 ИИ-анализ по ссылке", callback_data=f'tida_ai_link_{target_type}'),
        types.InlineKeyboardButton("📝 Описать нарушение", callback_data=f'tida_ai_desc_{target_type}'),
        types.InlineKeyboardButton("✏️ Написать свой текст", callback_data=f'tida_manual_{target_type}'),
        types.InlineKeyboardButton("[🔙] Назад", callback_data='back'),
    )
    return markup

# ─── TIDA подтверждение текста ────────────────────────────────────────────────
def tida_text_confirm_markup() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✅ Использовать этот текст", callback_data='tida_text_confirm'),
        types.InlineKeyboardButton("✏️ Изменить текст", callback_data='tida_text_change'),
        types.InlineKeyboardButton("[🔙] Назад", callback_data='back'),
    )
    return markup

# ─── DSA причины ──────────────────────────────────────────────────────────────
dsa_reason_markup = types.InlineKeyboardMarkup(row_width=1)
dsa_reason_markup.add(
    types.InlineKeyboardButton("👶 Child abuse", callback_data='dsa_r_child_abuse'),
    types.InlineKeyboardButton("💥 Violence", callback_data='dsa_r_violence'),
    types.InlineKeyboardButton("🔫 Illegal goods", callback_data='dsa_r_illegal_goods'),
    types.InlineKeyboardButton("🔞 Illegal adult content", callback_data='dsa_r_illegal_adult'),
    types.InlineKeyboardButton("🔐 Personal data", callback_data='dsa_r_personal_data'),
    types.InlineKeyboardButton("💣 Terrorism", callback_data='dsa_r_terrorism'),
    types.InlineKeyboardButton("📢 Scam or spam", callback_data='dsa_r_scam'),
    types.InlineKeyboardButton("📝 Other", callback_data='dsa_r_other'),
    types.InlineKeyboardButton("[🔙] Назад", callback_data='back'),
)

# ─── DSA подкатегории ─────────────────────────────────────────────────────────
dsa_sub_illegal_goods = types.InlineKeyboardMarkup(row_width=1)
dsa_sub_illegal_goods.add(
    types.InlineKeyboardButton("🔫 Weapons", callback_data='dsa_s_weapons'),
    types.InlineKeyboardButton("💊 Drugs", callback_data='dsa_s_drugs'),
    types.InlineKeyboardButton("📄 Fake documents", callback_data='dsa_s_fake_docs'),
    types.InlineKeyboardButton("💵 Counterfeit money", callback_data='dsa_s_counterfeit'),
    types.InlineKeyboardButton("📦 Other goods", callback_data='dsa_s_other_goods'),
    types.InlineKeyboardButton("[🔙] Назад", callback_data='dsa_method'),
)

dsa_sub_illegal_adult = types.InlineKeyboardMarkup(row_width=1)
dsa_sub_illegal_adult.add(
    types.InlineKeyboardButton("👶 Child abuse", callback_data='dsa_s_child_abuse_adult'),
    types.InlineKeyboardButton("📸 Non-consensual sexual imagery", callback_data='dsa_s_nonconsensual'),
    types.InlineKeyboardButton("🔞 Other illegal sexual content", callback_data='dsa_s_other_sexual'),
    types.InlineKeyboardButton("[🔙] Назад", callback_data='dsa_method'),
)

dsa_sub_personal_data = types.InlineKeyboardMarkup(row_width=1)
dsa_sub_personal_data.add(
    types.InlineKeyboardButton("🖼 Private images", callback_data='dsa_s_private_images'),
    types.InlineKeyboardButton("📱 Phone number", callback_data='dsa_s_phone'),
    types.InlineKeyboardButton("🏠 Address", callback_data='dsa_s_address'),
    types.InlineKeyboardButton("📋 Other personal information", callback_data='dsa_s_other_personal'),
    types.InlineKeyboardButton("[🔙] Назад", callback_data='dsa_method'),
)

dsa_sub_scam = types.InlineKeyboardMarkup(row_width=1)
dsa_sub_scam.add(
    types.InlineKeyboardButton("🎣 Phishing", callback_data='dsa_s_phishing'),
    types.InlineKeyboardButton("🎭 Impersonation", callback_data='dsa_s_impersonation'),
    types.InlineKeyboardButton("💸 Fraudulent sales", callback_data='dsa_s_fraud_sales'),
    types.InlineKeyboardButton("[🔙] Назад", callback_data='dsa_method'),
)

def dsa_text_confirm_markup(text_preview: str) -> types.InlineKeyboardMarkup:
    """Клавиатура подтверждения текста жалобы."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✅ Использовать этот текст", callback_data='dsa_text_confirm'),
        types.InlineKeyboardButton("✏️ Ввести свой текст", callback_data='dsa_text_custom'),
        types.InlineKeyboardButton("[🔙] Назад", callback_data='back'),
    )
    return markup
# stress_method_btn скрыт — в разработке
functions.add(back)

# ─── Под-меню канал-метода ────────────────────────────────────────────────────
promo_type_markup = types.InlineKeyboardMarkup(row_width=1)
promo_type_markup.add(
    types.InlineKeyboardButton("📅 Обычный (с днями)", callback_data='promo_type_normal'),
    types.InlineKeyboardButton("👑 Премиум (навсегда)", callback_data='promo_type_premium'),
    types.InlineKeyboardButton("🎯 Репорты", callback_data='promo_type_reports'),
    back
)

channel_reason_markup = types.InlineKeyboardMarkup(row_width=1)
channel_reason_markup.add(
    types.InlineKeyboardButton("🔐 Персональные данные", callback_data='ch_reason_personal'),
    types.InlineKeyboardButton("📢 Спам / Мошенничество", callback_data='ch_reason_spam'),
    types.InlineKeyboardButton("🔞 18+ Контент", callback_data='ch_reason_adult'),
    types.InlineKeyboardButton("👶 Детский Контент", callback_data='ch_reason_children'),
    types.InlineKeyboardButton("💥 Насилие / Экстремизм", callback_data='ch_reason_violence'),
    types.InlineKeyboardButton("📝 Прочее", callback_data='ch_reason_other'),
    back
)

# ─── Под-меню бот-метода ───────────────────────────────────────────────────────
bot_reason_markup = types.InlineKeyboardMarkup(row_width=1)
bot_reason_markup.add(
    types.InlineKeyboardButton("🔐 Персональные данные", callback_data='bot_reason_personal'),
    types.InlineKeyboardButton("💊 Наркотики", callback_data='bot_reason_drugs'),
    types.InlineKeyboardButton("📝 Прочее", callback_data='bot_reason_other'),
    back
)

pay_method = types.InlineKeyboardMarkup(row_width=1)
yoomoney = types.InlineKeyboardButton("🇷🇺 ЮMoney (Юмани)", callback_data='yoomoney')
pay_method.add(yoomoney, back)

info_markup = types.InlineKeyboardMarkup(row_width=1)
manual = types.InlineKeyboardButton("📖 Мануал", url='https://br-v2.online/manual')
info_markup.add(manual, back)

del_message = types.InlineKeyboardMarkup(row_width=1)
close = types.InlineKeyboardButton("🔻 Прочитано", callback_data='close')
kotik = types.InlineKeyboardButton("🔥 Подпишись", url=config.bot_channel_link)
del_message.add(close, kotik)

del_message2 = types.InlineKeyboardMarkup(row_width=2)
close2 = types.InlineKeyboardButton("Закрыть", callback_data='close')
del_message2.add(close2)

main_menu = types.InlineKeyboardMarkup(row_width=2)
go_to_main_menu = types.InlineKeyboardButton("[🔙] Главное меню", callback_data='go_to_main_menu')
main_menu.add(go_to_main_menu)

admin_markup = types.InlineKeyboardMarkup(row_width=2)
add_subsribe = types.InlineKeyboardButton("[+] Выдать подписку", callback_data='add_subsribe')
clear_subscribe = types.InlineKeyboardButton("[-] Забрать подписку", callback_data='clear_subscribe')
add_prem = types.InlineKeyboardButton("[+] Выдать премиум", callback_data='add_prem')
clear_prem = types.InlineKeyboardButton("[-] Забрать премиум", callback_data='clear_prem')
send_all = types.InlineKeyboardButton("[📢] Рассылка", callback_data='send_all')
block_user_btn = types.InlineKeyboardButton("[🚫] Заблокировать", callback_data='block_user_admin')
unblock_user_btn = types.InlineKeyboardButton("[✅] Разблокировать", callback_data='unblock_user_admin')
delete_user_btn = types.InlineKeyboardButton("[🗑] Удалить из БД", callback_data='delete_user_admin')
users_list_btn = types.InlineKeyboardButton("[👥] Список пользователей", callback_data='users_list_0')
mirrors_list_btn = types.InlineKeyboardButton("[🪞] Зеркала", callback_data='admin_mirrors_0')
add_reports_btn = types.InlineKeyboardButton("[🎯+] Выдать репорты", callback_data='admin_add_reports')
remove_reports_btn = types.InlineKeyboardButton("[🎯-] Забрать репорты", callback_data='admin_remove_reports')
create_promo_btn = types.InlineKeyboardButton("[💎] Создать промокод", callback_data='admin_create_promo')
admin_markup.add(add_subsribe, clear_subscribe)
admin_markup.add(add_prem, clear_prem)
admin_markup.add(send_all)
admin_markup.add(block_user_btn, unblock_user_btn)
admin_markup.add(delete_user_btn)
admin_markup.add(users_list_btn)
admin_markup.add(mirrors_list_btn)
admin_markup.add(add_reports_btn, remove_reports_btn)
admin_markup.add(create_promo_btn)
maintenance_btn = types.InlineKeyboardButton("🔧 Включить тех. работы", callback_data='toggle_maintenance')
admin_markup.add(maintenance_btn)

shop_markup = types.InlineKeyboardMarkup(row_width=2)
sub1 = types.InlineKeyboardButton("⚡️ 1 день — 1$ / 100₽", callback_data='sub_1')
sub3 = types.InlineKeyboardButton("⚡️ 3 дня — 2$ / 175₽", callback_data='sub_3')
sub7 = types.InlineKeyboardButton("⚡️ 7 дней — 4$ / 350₽", callback_data='sub_7')
sub30 = types.InlineKeyboardButton("⚡️ 30 дней — 8$ / 700₽", callback_data='sub_30')
subforever = types.InlineKeyboardButton("⚡️ Навсегда — 6$ / 500₽ [-70%]", callback_data='sub_forever')
premupgrade = types.InlineKeyboardButton("⭐️ Premium — 5$ / 400₽ [-50%]", callback_data='sub_premupgrade')
buyforadmins = types.InlineKeyboardButton("💳 Оплата картой", callback_data='buyforadmins')
preminfo = types.InlineKeyboardButton("👑 Что такое премиум?", callback_data='preminfo')
shop_markup.add(sub1, sub3)
shop_markup.add(sub7, sub30)
shop_markup.add(subforever)
shop_markup.add(premupgrade)
shop_markup.add(buyforadmins, preminfo)
shop_markup.add(back)

check_markup = types.InlineKeyboardMarkup(row_width=1)
channel = types.InlineKeyboardButton("[1️⃣] Подпишись", url=config.bot_channel_link)
channel2 = types.InlineKeyboardButton("[2️⃣] Подпишись", url=config.bot_channel2_link)
check_sub = types.InlineKeyboardButton("[🔎] Проверить", callback_data='back')
check_markup.add(channel, channel2, check_sub)

# ─── Рефералы ─────────────────────────────────────────────────────────────────
referral_markup = types.InlineKeyboardMarkup(row_width=1)
exchange_refs_btn = types.InlineKeyboardButton("🔄 Обменять 10 рефералов → 1 день", callback_data='exchange_refs')
referral_markup.add(exchange_refs_btn, back)

# ─── Колесо удачи ─────────────────────────────────────────────────────────────
wheel_markup = types.InlineKeyboardMarkup(row_width=1)
spin_btn = types.InlineKeyboardButton("🎡 Крутить!", callback_data='spin_wheel')
wheel_markup.add(spin_btn, back)

# ─── Выбор банка ──────────────────────────────────────────────────────────────
bank_select_markup = types.InlineKeyboardMarkup(row_width=1)
bank_select_markup.add(
    types.InlineKeyboardButton("🟡 Т-Банк (Тинькофф)", callback_data='bank_tbank'),
    types.InlineKeyboardButton("🔴 Альфа-Банк", callback_data='bank_alfa'),
    types.InlineKeyboardButton("🟢 Сбер Банк", callback_data='bank_sber'),
    types.InlineKeyboardButton("🔵 Озон Банк", callback_data='bank_ozon'),
    back
)

# ─── Подтверждение мануала ────────────────────────────────────────────────────
def manual_confirm_step1(method: str) -> types.InlineKeyboardMarkup:
    """Первый шаг: ознакомлен"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📄 Читать мануал", url='https://br-v2.online/manual'),
        types.InlineKeyboardButton("✅ Ознакомлен", callback_data=f'manual_step2_{method}'),
        types.InlineKeyboardButton("[🔙] Назад", callback_data='back')
    )
    return markup


def manual_confirm_step2(method: str) -> types.InlineKeyboardMarkup:
    """Второй шаг: 100% прочитал"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💯 100% прочитал", callback_data=f'manual_confirm_{method}'),
        types.InlineKeyboardButton("[🔙] Назад", callback_data='functions')
    )
    return markup
