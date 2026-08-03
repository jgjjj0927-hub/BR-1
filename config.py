import os

TOKEN = os.environ.get("TOKEN", "")
CRYPTO = os.environ.get("CRYPTO", "")
ADMINS = list(map(int, os.environ.get("ADMINS", "8316051968,60693380").split(",")))

bot_logs = int(os.environ.get("BOT_LOGS", "8316051968"))
bot_channel_link = os.environ.get("CHANNEL_LINK", "https://t.me/+3u8scLryHxdmNDUy")
bot_channel2_link = os.environ.get("CHANNEL2_LINK", "https://t.me/ChannelKoTik2k8")
bot_admin = os.environ.get("BOT_ADMIN", "@KoTik2k8")
channel_id = os.environ.get("CHANNEL_ID", "-1002847743793")
channel2_id = os.environ.get("CHANNEL2_ID", "-1002847743793")
NO_KD = list(map(int, os.environ.get("NO_KD", "1403537093").split(",")))
