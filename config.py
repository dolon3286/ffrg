import os
from os import getenv


def _get_int(name, default=0):
    value = os.environ.get(name, str(default)).strip()
    return int(value) if value else int(default)


API_ID = _get_int("API_ID")
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")
OWNER_ID = _get_int("OWNER_ID")
SUDO_USERS = [
    int(user_id)
    for user_id in getenv("SUDO_USERS", str(OWNER_ID)).replace(",", " ").split()
    if user_id
]
CHANNEL_ID = _get_int("CHANNEL_ID")
MONGO_URL = os.environ.get("MONGO_URL") or os.environ.get("MONGO_DB", "mongodb://mongo:27017/extractor_bot")
PREMIUM_LOGS = _get_int("PREMIUM_LOGS", CHANNEL_ID)
