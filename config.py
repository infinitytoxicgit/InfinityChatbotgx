from os import getenv

from dotenv import load_dotenv

load_dotenv()

API_ID = "35218869"
# -------------------------------------------------------------
API_HASH = "80baadcfd00a39a0ff1f5f529d23156f"
# --------------------------------------------------------------
BOT_TOKEN = getenv("BOT_TOKEN", "")
STRING1 = getenv("STRING1", "")
MONGO_URL = getenv(
    "MONGO_URL",
    "mongodb+srv://knight4563:knight4563@cluster0.a5br0se.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
OWNER_ID = int(getenv("OWNER_ID", "8564072723"))
SUPPORT_GRP = "https://t.me/+xWR1TL_g_VMzZTcy"
UPDATE_CHNL = "@Roohi_Soul"
OWNER_USERNAME = "@Fuck_You_In_Hell"
