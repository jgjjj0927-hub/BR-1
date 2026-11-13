import os

TOKEN = os.environ.get("TOKEN", "8642013882:AAFdDVh_PVp73BK_wRottcRkMKUU73rohUI")
CRYPTO = os.environ.get("CRYPTO", "no")
ADMINS = list(map(int, os.environ.get("ADMINS", "8224529558").split(",")))

bot_logs = int(os.environ.get("BOT_LOGS", "8224529558"))
bot_channel_link = os.environ.get("CHANNEL_LINK", "https://t.me/brv2op")
bot_channel2_link = os.environ.get("CHANNEL2_LINK", "https://t.me/xxxxx33hz")
bot_admin = os.environ.get("BOT_ADMIN", "@id8224529558")
channel_id = os.environ.get("CHANNEL_ID", "-1004489653566")
channel2_id = os.environ.get("CHANNEL2_ID", "-1004337279021")
NO_KD = list(map(int, os.environ.get("NO_KD", "8312194811").split(",")))

# ─── AU Report / TIDA ────────────────────────────────────────────────────────
# API для сессий aureport_sessions/ и tida_sessions/
# Можно использовать те же что и для основного ботнета или свои
AUREPORT_API_ID = os.environ.get("AUREPORT_API_ID", "24565698")
AUREPORT_API_HASH = os.environ.get("AUREPORT_API_HASH", "5a084b434f8505ace703485b9da85040")

TIDA_API_ID = os.environ.get("TIDA_API_ID", "24565698")
TIDA_API_HASH = os.environ.get("TIDA_API_HASH", "5a084b434f8505ace703485b9da85040")

# TIDA прокси (SOCKS5 обязателен для TIDA)
# Задаётся через env: TIDA_PROXY_HOST, TIDA_PROXY_PORT, TIDA_PROXY_USER, TIDA_PROXY_PASS

# ─── DSA Report ───────────────────────────────────────────────────────────────
CAPMONSTER_KEY = os.environ.get("CAPMONSTER_KEY", "499a750d9f2078ada5a786586f0a22f1")
GROQ_KEY = os.environ.get("GROQ_KEY", "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")
