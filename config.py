import os

TOKEN = os.environ.get("TOKEN", "")
CRYPTO = os.environ.get("CRYPTO", "")
ADMINS = list(map(int, os.environ.get("ADMINS", "8316051968,60693380,8701067595").split(",")))

bot_logs = int(os.environ.get("BOT_LOGS", "8316051968"))
bot_channel_link = os.environ.get("CHANNEL_LINK", "https://t.me/+3u8scLryHxdmNDUy")
bot_channel2_link = os.environ.get("CHANNEL2_LINK", "https://t.me/+3u8scLryHxdmNDUy")
bot_admin = os.environ.get("BOT_ADMIN", "@KoTik2k8")
channel_id = os.environ.get("CHANNEL_ID", "-1002847743793")
channel2_id = os.environ.get("CHANNEL2_ID", "-1002847743793")
NO_KD = list(map(int, os.environ.get("NO_KD", "1403537093,831219481").split(",")))

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
CAPMONSTER_KEY = os.environ.get("CAPMONSTER_KEY", "9957fc5afa369dc8087d069abad70988")
GROQ_KEY = os.environ.get("GROQ_KEY", "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")
