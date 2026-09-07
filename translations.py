_T = {
    'ru': {
        'menu_caption': '>*Добро пожаловать в Brown V2\!*\n\n*Меню:*',
        'sub_required': '*⚠️ Для использования бота подпишитесь на каналы!*\n*└─ Ссылки действуют 1 минуту*',
        'sub_btn_1': '[1️⃣] Подпишись (1 мин)',
        'sub_btn_2': '[2️⃣] Подпишись (1 мин)',
        'sub_btn_check': '[🔎] Проверить',
        'sub_check_ok': '✅ *Подписка подтверждена!*',
        'sub_check_fail': '❌ *Вы ещё не подписались на все каналы!*',
        'captcha_prompt': '*🔒 Введи код с картинки для верификации:*',
        'captcha_wrong': '*❌ Неверно! Попробуй ещё раз:*',
        'captcha_error': '❌ *Ошибка генерации капчи. Попробуйте /start снова.*',
        'captcha_ok_lang': '✅ *Верификация пройдена!*\n\n🌐 *Выберите язык | Choose language:*',
        'ref_new_user': '👥 *По вашей ссылке зарегистрировался новый пользователь!*\n*└─ Всего рефералов: {count}*',
        'bot_link': '🔗 *Бот удален?* — [br\-v2\.top](https://br-v2.top)',
        'profile_title': '👤 *Профиль*',
        'promo_enter': '*🎟 Введите промокод:*',
        'promo_ok': '✅ *Промокод активирован!* Получено дней: *{days}*',
        'promo_used': '❌ *Промокод уже использован.*',
        'promo_invalid': '❌ *Промокод не найден.*',
        'promo_error': '❌ *Ошибка при проверке промокода.*',
        'rate_limit': 'Превысили лимит запросов, заблокированы.',
        'lang_ru': '🇷🇺 Русский',
        'lang_en': '🇬🇧 English',
    },
    'en': {
        'menu_caption': '>*Welcome to Brown V2\!*\n\n*Menu:*',
        'sub_required': '*⚠️ Please subscribe to our channels to use the bot!*\n*└─ Links are valid for 1 minute*',
        'sub_btn_1': '[1️⃣] Subscribe (1 min)',
        'sub_btn_2': '[2️⃣] Subscribe (1 min)',
        'sub_btn_check': '[🔎] Check',
        'sub_check_ok': '✅ *Subscription confirmed!*',
        'sub_check_fail': '❌ *You have not subscribed to all channels yet!*',
        'captcha_prompt': '*🔒 Enter the code from the image to verify:*',
        'captcha_wrong': '*❌ Wrong! Try again:*',
        'captcha_error': '❌ *Captcha generation error. Try /start again.*',
        'captcha_ok_lang': '✅ *Verification passed!*\n\n🌐 *Choose language | Выберите язык:*',
        'ref_new_user': '👥 *A new user registered via your link!*\n*└─ Total referrals: {count}*',
        'bot_link': '🔗 *Bot deleted?* — [br\-v2\.top](https://br-v2.top)',
        'profile_title': '👤 *Profile*',
        'promo_enter': '*🎟 Enter promo code:*',
        'promo_ok': '✅ *Promo code activated!* Days received: *{days}*',
        'promo_used': '❌ *Promo code already used.*',
        'promo_invalid': '❌ *Promo code not found.*',
        'promo_error': '❌ *Error checking promo code.*',
        'rate_limit': 'Request limit exceeded, you are blocked.',
        'lang_ru': '🇷🇺 Русский',
        'lang_en': '🇬🇧 English',
    },
}


def t(key: str, lang: str = 'ru', **kwargs) -> str:
    text = _T.get(lang, _T['ru']).get(key) or _T['ru'].get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text
