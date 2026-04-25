import os
import json
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application
import threading
import time
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://herozvz07_db_user:iXi80aUXy9qUtPcP@cluster0.bb0wzws.mongodb.net/?appName=Cluster0")
GUILD_URL = "https://www.rucoyonline.com/guild/Imperia%20Of%20Titans"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-render-app.onrender.com")

# MongoDB подключение
try:
    mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ping')
    db = mongo_client['guild_bot_db']
    print("✅ MongoDB подключена успешно")
except Exception as e:
    print(f"❌ Ошибка подключения к MongoDB: {e}")
    exit(1)

# Collections
config_collection = db['config']
members_collection = db['members']

# Flask приложение
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)

# ==================== ПАРСИНГ ГИЛЬДИИ ====================

def parse_guild_members():
    """Парсит страницу гильдии и возвращает список членов"""
    try:
        response = requests.get(GUILD_URL, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        members = []
        
        # Ищем таблицу с членами
        table = soup.find('table')
        if not table:
            print("❌ Таблица членов не найдена")
            return members
        
        rows = table.find_all('tr')[1:]  # Пропускаем заголовок
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:
                name = cols[0].get_text(strip=True)
                status = cols[1].get_text(strip=True)
                level = cols[2].get_text(strip=True)
                
                # Проверяем онлайн статус
                is_online = 'online' in status.lower()
                is_leader = 'leader' in status.lower()
                
                member = {
                    'name': name,
                    'level': int(level) if level.isdigit() else 0,
                    'status': status,
                    'is_online': is_online,
                    'is_leader': is_leader
                }
                members.append(member)
        
        return members
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return []

# ==================== ФУНКЦИИ БД ====================

def get_last_members():
    """Получить последний снимок членов из БД"""
    doc = members_collection.find_one({"_id": "current"})
    if doc:
        return doc.get('members', [])
    return []

def update_members(members):
    """Обновить снимок членов в БД"""
    members_collection.update_one(
        {"_id": "current"},
        {"$set": {"members": members, "updated_at": datetime.now()}},
        upsert=True
    )

def get_config():
    """Получить конфигурацию бота"""
    doc = config_collection.find_one({"_id": "main"})
    return doc if doc else {}

def set_config(chat_id, topic_id=None):
    """Установить конфигурацию (чат для уведомлений)"""
    config_collection.update_one(
        {"_id": "main"},
        {"$set": {"chat_id": chat_id, "topic_id": topic_id, "updated_at": datetime.now()}},
        upsert=True
    )

def get_admin_id():
    """Получить ID админа (вас)"""
    return 6395348885

# ==================== ФУНКЦИИ ОТПРАВКИ СООБЩЕНИЙ ====================

async def send_notification(message_text):
    """Отправить уведомление в установленный чат"""
    config = get_config()
    chat_id = config.get('chat_id')
    topic_id = config.get('topic_id')
    
    if not chat_id:
        print("⚠️ Чат для уведомлений не установлен")
        return
    
    try:
        if topic_id:
            await bot.send_message(chat_id=chat_id, text=message_text, message_thread_id=topic_id, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="HTML")
        print(f"✅ Сообщение отправлено: {message_text[:50]}...")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

async def send_reply(chat_id, message_text, topic_id=None):
    """Отправить ответ пользователю"""
    try:
        if topic_id:
            await bot.send_message(chat_id=chat_id, text=message_text, message_thread_id=topic_id, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="HTML")
    except Exception as e:
        print(f"❌ Ошибка отправки ответа: {e}")

# ==================== КОМАНДЫ БОТА ====================

async def handle_botguild(chat_id, message_id, topic_id=None):
    """Установить чат для уведомлений (только для админа)"""
    user_id = 6395348885  # Вы будете админом
    
    if chat_id != user_id and chat_id > 0:  # Проверка в личке
        await send_reply(chat_id, "❌ Эта команда доступна только админу гильдии!")
        return
    
    set_config(chat_id, topic_id)
    await send_reply(chat_id, "✅ <b>Бот настроен!</b>\n\nУведомления о новых/ушедших членах будут отправляться в этот чат.")

async def handle_online(chat_id, topic_id=None):
    """Показать онлайн членов гильдии"""
    members = parse_guild_members()
    online_members = [m for m in members if m['is_online']]
    
    if not online_members:
        msg = "❌ Сейчас никого нет онлайн"
    else:
        msg = "<b>🟢 Онлайн члены гильдии:</b>\n\n"
        for member in online_members:
            emoji = "👑" if member['is_leader'] else "⚔️"
            msg += f"{emoji} <b>{member['name']}</b> - Уровень {member['level']}\n"
    
    await send_reply(chat_id, msg, topic_id)

async def handle_lvl(chat_id, topic_id=None):
    """Показать топ-5 по уровню"""
    members = parse_guild_members()
    sorted_members = sorted(members, key=lambda x: x['level'], reverse=True)[:5]
    
    msg = "<b>🏆 Топ-5 по уровню:</b>\n\n"
    for i, member in enumerate(sorted_members, 1):
        emoji = "👑" if member['is_leader'] else "⚔️"
        msg += f"{i}. {emoji} <b>{member['name']}</b> - Уровень <b>{member['level']}</b>\n"
    
    await send_reply(chat_id, msg, topic_id)

# ==================== ПЕРИОДИЧЕСКАЯ ПРОВЕРКА ====================

async def check_guild_changes():
    """Проверять изменения в гильдии каждые 5 минут"""
    while True:
        try:
            time.sleep(300)  # 5 минут
            
            current_members = parse_guild_members()
            last_members = get_last_members()
            
            # Сравниваем список
            current_names = {m['name'] for m in current_members}
            last_names = {m['name'] for m in last_members}
            
            # Новые члены
            new_members = current_names - last_names
            for name in new_members:
                member = next(m for m in current_members if m['name'] == name)
                msg = f"🎉 <b>Новый член гильдии!</b>\n\n⚔️ {name}\n📊 Уровень: {member['level']}"
                await send_notification(msg)
            
            # Ушедшие члены
            left_members = last_names - current_names
            for name in left_members:
                msg = f"😢 <b>Член гильдии ушел</b>\n\n⚔️ {name}"
                await send_notification(msg)
            
            # Обновляем список
            update_members(current_members)
            
        except Exception as e:
            print(f"❌ Ошибка в check_guild_changes: {e}")

# ==================== ВЕБХУК FLASK ====================

@app.route('/', methods=['POST'])
async def webhook():
    """Вебхук Telegram"""
    try:
        data = request.get_json()
        update = Update.de_json(data, bot)
        
        if update.message:
            chat_id = update.message.chat_id
            user_id = update.message.from_user.id
            topic_id = update.message.message_thread_id
            text = update.message.text or ""
            
            # /botguild - установить чат (только админу)
            if text.startswith('/botguild'):
                if user_id == get_admin_id():
                    await handle_botguild(chat_id, update.message.message_id, topic_id)
                else:
                    await send_reply(chat_id, "❌ Эта команда только для админа!", topic_id)
            
            # /online - список онлайн
            elif text.startswith('/online'):
                await handle_online(chat_id, topic_id)
            
            # /lvl - топ-5
            elif text.startswith('/lvl'):
                await handle_lvl(chat_id, topic_id)
            
            # /start
            elif text.startswith('/start'):
                msg = "👋 <b>Добро пожаловать!</b>\n\n"
                msg += "Доступные команды:\n"
                msg += "📋 /online - онлайн члены\n"
                msg += "🏆 /lvl - топ-5 по уровню\n"
                msg += "⚙️ /botguild - установить канал уведомлений (админ)"
                await send_reply(chat_id, msg, topic_id)
        
        return 'OK', 200
    except Exception as e:
        print(f"❌ Ошибка вебхука: {e}")
        return 'ERROR', 500

@app.route('/health', methods=['GET'])
def health():
    """Health check для Render"""
    return 'OK', 200

# ==================== ЗАПУСК ====================

def run_background_task():
    """Запустить фоновую проверку в отдельном потоке"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_guild_changes())

if __name__ == '__main__':
    # Инициализируем начальный список членов
    members = parse_guild_members()
    update_members(members)
    print(f"✅ Загружено {len(members)} членов гильдии")
    
    # Запускаем фоновую проверку
    bg_thread = threading.Thread(target=run_background_task, daemon=True)
    bg_thread.start()
    
    # Запускаем Flask
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
