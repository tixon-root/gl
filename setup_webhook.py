import requests
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not WEBHOOK_URL:
    print("❌ WEBHOOK_URL не установлен в .env файле")
    exit(1)

webhook_endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
payload = {"url": f"{WEBHOOK_URL}/"}

print(f"📡 Устанавливаю вебхук на: {WEBHOOK_URL}")
response = requests.post(webhook_endpoint, json=payload)

if response.status_code == 200:
    print("✅ Вебхук установлен успешно!")
    print(f"📊 Ответ: {response.json()}")
else:
    print(f"❌ Ошибка: {response.status_code}")
    print(f"📊 Ответ: {response.text}")
