"""Конфигурация бота и загрузка переменных окружения."""
import os
import logging
from dotenv import load_dotenv

# Загрузка .env файла
load_dotenv()

# ================== Telegram Bot ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env файле!")

# ================== Google Sheets ==================
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")

if not SPREADSHEET_ID:
    raise ValueError("SPREADSHEET_ID не задан в .env файле!")

# ================== Telegram Channels/Groups ==================
OPEN_CHANNEL_ID = int(os.getenv("OPEN_CHANNEL_ID", "0"))
CLOSED_GROUP_ID = int(os.getenv("CLOSED_GROUP_ID", "0"))
CLOSED_CHAT_LINK = os.getenv("CLOSED_CHAT_LINK", "")

# ================== Бонусы ==================
CHANNEL_BONUS = int(os.getenv("CHANNEL_BONUS", "10"))
GROUP_BONUS = int(os.getenv("GROUP_BONUS", "500"))

# ================== Администрирование ==================
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_THREAD_ID = int(os.getenv("ADMIN_THREAD_ID", "0"))

# Парсинг списка админов (могут быть ID или username)
ADMINS_RAW = os.getenv("ADMINS", "")
ADMINS = set()
for adm in ADMINS_RAW.split(","):
    adm = adm.strip()
    if not adm:
        continue
    if adm.isdigit():
        ADMINS.add(int(adm))
    else:
        ADMINS.add(adm)

# ================== Логирование ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
log = logging.getLogger("pride-bot")
