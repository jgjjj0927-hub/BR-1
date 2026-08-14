from aiogram import types
import config

menu = types.InlineKeyboardMarkup(row_width=2)
profile = types.InlineKeyboardButton("📕 Профиль", callback_data='profile')
information = types.InlineKeyboardButton("❓ Информация", callback_data='information')
shop = types.InlineKeyboardButton("🛍 Цены", callback_data='shop')
snoser = types.InlineKeyboardButton("🔥 Открыть редактор", callback_data='functions')
promo = types.InlineKeyboardButton("🎁 Промокод", callback_data='promo')
referral_btn = types.InlineKeyboardButton("👥 Рефералы", callback_data='referral')
wheel_btn = types.InlineKeyboardButton("🎡 Колесо удачи", callback_data='wheel')
free_btn = types.InlineKeyboardButton("🆓 Бесплатно", callback_data='free_menu')
menu.add(snoser)
menu.add(information, profile)
menu.add(shop, promo)
menu.add(referral_btn, wheel_btn)
menu.add(free_btn)

# ─── Меню Бесплатно ───────────────────────────────────────────────────────────
free_menu_markup = types.InlineKeyboardMarkup(row_width=1)
free_menu_markup.add(
    types.InlineKeyboardButton("🪞 Создать зеркало", callback_data='mirror_create'),
    types.InlineKeyboardButton("📋 Мои зеркала", callback_data='mirror_list'),
    types.InlineKeyboardButton("[🔙] Назад", callback_data='back')
)


back_markup = types.InlineKeyboardMarkup(row_width=2)
back = types.InlineKeyboardButton("[🔙] Назад", callback_data='back')
back_markup.add(back)

functions = types.InlineKeyboardMarkup(row_width=2)
web_method = types.InlineKeyboardButton("🌐 Веб", callback_data='web_method')
mail_method = types.InlineKeyboardButton("✉️ Почты", callback_data='mail_method')
botnet_method = types.InlineKeyboardButton("🤖 Обычный", callback_data='botnet_method')
prem_botnet_method = types.InlineKeyboardButton("👑 Премиальная отправка", callback_data='prem_botnet_method')
bot_method_btn = types.InlineKeyboardButton("🤖 Бот", callback_data='bot_method')
channel_method_btn = types.InlineKeyboardButton("📢 Канал", callback_data='channel_method')
code_method_btn = types.InlineKeyboardButton("📱 Коды", callback_data='code_method')
functions.add(botnet_method)
functions.add(web_method, mail_method)
functions.add(prem_botnet_method)
functions.add(bot_method_btn, channel_method_btn)
functions.add(code_method_btn)
manual_method_btn = types.InlineKeyboardButton("👤 Ручной метод", callback_data='manual_method')
functions.add(manual_method_btn)
aureport_method_btn = types.InlineKeyboardButton("🇦🇺 AU Report", callback_data='aureport_method')
tida_method_btn = types.InlineKeyboardButton("🟣 TIDA", callback_data='tida_method')
functions.add(aureport_method_btn, tida_method_btn)
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
    types.InlineKeyboardButton("🔐 Персональные Данные", callback_data='bot_reason_personal'),
    types.InlineKeyboardButton("🔞 18+ Контент", callback_data='bot_reason_adult'),
    types.InlineKeyboardButton("👶 Детский Контент", callback_data='bot_reason_children'),
    types.InlineKeyboardButton("💥 Сносер", callback_data='bot_reason_snoser'),
    types.InlineKeyboardButton("📊 FunStat (парсинг)", callback_data='bot_reason_funstat'),
    types.InlineKeyboardButton("📝 Прочее", callback_data='bot_reason_other'),
    back
)

pay_method = types.InlineKeyboardMarkup(row_width=1)
yoomoney = types.InlineKeyboardButton("🇷🇺 ЮMoney (Юмани)", callback_data='yoomoney')
pay_method.add(yoomoney, back)

info_markup = types.InlineKeyboardMarkup(row_width=1)
manual = types.InlineKeyboardButton("� Мануал", url='https://teletype.in/@brownv2/manual')
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
