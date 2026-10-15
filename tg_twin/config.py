# Telegram API — получить на https://my.telegram.org (App api_id / api_hash)
API_ID   = 0           # int
API_HASH = ""          # str

# Номер телефона бот-аккаунта (отдельный аккаунт, не основной)
PHONE = "+7XXXXXXXXXX"

# Google Gemini API — бесплатно на https://aistudio.google.com → Get API key
GEMINI_API_KEY = ""

# Твой user ID на ОСНОВНОМ аккаунте (для команд .старт/.стоп)
# Узнать: написать @userinfobot с основного аккаунта
OWNER_ID = 0  # int, 0 = команды от всех (не рекомендую)

# Путь к папке с экспортом Telegram (Settings → Advanced → Export Telegram Data → Personal chats → JSON)
EXPORT_PATH = "./telegram_export"

# Модель Gemini
GEMINI_MODEL = "gemini-2.0-flash"

# Сколько сообщений истории передавать как контекст
CONTEXT_MESSAGES = 20

# Лимит сообщений для анализа персоны (0 = все)
PERSONA_MESSAGES_LIMIT = 15000
