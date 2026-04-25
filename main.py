import os
import logging
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify
from pymongo import MongoClient
from telegram import Update, Bot
from telegram.ext import Application
from telegram.error import TelegramError
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)

# Переменные окружения
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
MONGO_URL = 'mongodb+srv://herozvz07_db_user:iXi80aUXy9qUtPcP@cluster0.bb0wzws.mongodb.net/?appName=Cluster0'
GUILD_URL = 'https://www.rucoyonline.com/guild/Imperia%20Of%20Titans'
ADMIN_ID = 6395348885
PORT = int(os.environ.get('PORT', 10000))

if not TELEGRAM_TOKEN:
    logger.error('TELEGRAM_TOKEN not set!')
    raise ValueError('TELEGRAM_TOKEN environment variable not found')

# MongoDB подключение
try:
    mongo_client = MongoClient(MONGO_URL)
    mongo_client.admin.command('ping')
    logger.info('✅ MongoDB connected successfully')
except Exception as e:
    logger.error(f'❌ MongoDB connection failed: {e}')
    raise

db = mongo_client['guild_bot']
config_collection = db['config']
members_collection = db['members']

# Инициализация Telegram Bot
bot = Bot(token=TELEGRAM_TOKEN)

# Глобальные переменные для отслеживания
last_members = {}
current_chat_id = None
current_thread_id = None


def get_guild_members():
    """
    Парсит страницу гильдии и возвращает список членов
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(GUILD_URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            logger.warning(f'Failed to fetch guild page: {response.status_code}')
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Поиск таблицы с членами
        members = []
        
        # Находим все строки таблицы с членами
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    # Извлекаем имя, статус, уровень и дату присоединения
                    name_col = cols[0].text.strip()
                    level_col = cols[1].text.strip()
                    date_col = cols[2].text.strip()
                    
                    # Проверяем лидера (содержит "Leader")
                    is_leader = 'Leader' in name_col or 'Leader' in str(cols[0])
                    
                    # Очищаем имя от статуса
                    name = name_col.replace('(Leader)', '').replace('Supporter', '').replace('online', '').strip()
                    
                    if name and level_col.isdigit():
                        members.append({
                            'name': name,
                            'level': int(level_col),
                            'join_date': date_col,
                            'is_leader': is_leader,
                            'status': 'online' if 'online' in name_col.lower() else 'offline'
                        })
        
        logger.info(f'✅ Fetched {len(members)} members from guild')
        return members
    
    except Exception as e:
        logger.error(f'❌ Error parsing guild page: {e}')
        return []


def check_guild_changes():
    """
    Проверяет изменения в составе гильдии и отправляет уведомления
    """
    global last_members, current_chat_id, current_thread_id
    
    try:
        # Получаем текущих членов
        current_members = get_guild_members()
        
        if not current_members:
            logger.warning('No members found on guild page')
            return
        
        # Получаем конфиг из БД
        config = config_collection.find_one({'_id': 'main'})
        if not config or not config.get('chat_id'):
            logger.info('Bot not configured yet')
            return
        
        chat_id = config['chat_id']
        thread_id = config.get('thread_id', None)
        
        # Преобразуем членов в словарь для сравнения
        current_names = {m['name']: m for m in current_members}
        
        # Получаем последних членов из БД
        members_doc = members_collection.find_one({'_id': 'current'})
        if members_doc and members_doc.get('members'):
            last_names = {m['name']: m for m in members_doc['members']}
        else:
            last_names = {}
        
        # Проверяем новых членов
        new_members = [name for name in current_names if name not in last_names]
        
        # Проверяем ушедших членов
        left_members = [name for name in last_names if name not in current_names]
        
        # Отправляем уведомления о новых членах
        for member_name in new_members:
            member = current_names[member_name]
            level = member['level']
            message = f"🎉 **Новый член гильдии!**\n\n👤 {member_name}\n⚔️ Уровень: {level}"
            
            try:
                if thread_id:
                    bot.send_message(chat_id=chat_id, text=message, message_thread_id=thread_id, parse_mode='Markdown')
                else:
                    bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
                logger.info(f'✅ Sent welcome message for {member_name}')
            except TelegramError as e:
                logger.error(f'Failed to send welcome message: {e}')
        
        # Отправляем уведомления об ушедших членах
        for member_name in left_members:
            message = f"👋 **Член гильдии покинул нас!**\n\n👤 {member_name}"
            
            try:
                if thread_id:
                    bot.send_message(chat_id=chat_id, text=message, message_thread_id=thread_id, parse_mode='Markdown')
                else:
                    bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
                logger.info(f'✅ Sent goodbye message for {member_name}')
            except TelegramError as e:
                logger.error(f'Failed to send goodbye message: {e}')
        
        # Обновляем членов в БД
        members_collection.update_one(
            {'_id': 'current'},
            {'$set': {'members': current_members, 'updated': datetime.now()}},
            upsert=True
        )
        
        logger.info(f'✅ Guild check completed. New: {len(new_members)}, Left: {len(left_members)}')
    
    except Exception as e:
        logger.error(f'❌ Error in check_guild_changes: {e}')


def background_guild_checker():
    """
    Фоновый поток для проверки гильдии каждые 5 минут
    """
    logger.info('🔄 Background guild checker started')
    
    while True:
        try:
            check_guild_changes()
            time.sleep(300)  # 5 минут
        except Exception as e:
            logger.error(f'❌ Error in background checker: {e}')
            time.sleep(300)


@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Обработчик вебхука от Telegram
    """
    try:
        update_data = request.get_json()
        if not update_data:
            return jsonify({'ok': False}), 200
        
        update = Update.de_json(update_data, bot)
        
        if not update.message:
            return jsonify({'ok': True}), 200
        
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        text = update.message.text or ''
        message_thread_id = update.message.message_thread_id
        
        logger.info(f'📨 Message from {user_id} in chat {chat_id}: {text}')
        
        # Команда /botguild - установка конфига (только для админа)
        if text == '/botguild':
            if user_id != ADMIN_ID:
                bot.send_message(chat_id=chat_id, text='❌ Только администратор может это делать!')
                return jsonify({'ok': True}), 200
            
            # Сохраняем конфиг
            config_collection.update_one(
                {'_id': 'main'},
                {'$set': {
                    'chat_id': chat_id,
                    'thread_id': message_thread_id,
                    'updated': datetime.now()
                }},
                upsert=True
            )
            
            thread_info = f"в теме #{message_thread_id}" if message_thread_id else "в чате"
            bot.send_message(
                chat_id=chat_id,
                text=f'✅ Бот настроен! Уведомления будут отправляться {thread_info}\n\n'
                     f'Команды:\n'
                     f'/online - показать онлайн-участников\n'
                     f'/lvl - топ-5 сильнейших членов',
                message_thread_id=message_thread_id
            )
            logger.info(f'✅ Bot configured for chat {chat_id}, thread {message_thread_id}')
            return jsonify({'ok': True}), 200
        
        # Команда /online - показать онлайн
        elif text == '/online':
            members = get_guild_members()
            online_members = [m for m in members if m['status'] == 'online']
            
            if not online_members:
                bot.send_message(chat_id=chat_id, text='😴 Сейчас никого нет онлайн')
            else:
                message = '🟢 **Онлайн-участники:**\n\n'
                for member in online_members:
                    leader_badge = '👑' if member['is_leader'] else ''
                    message += f"{leader_badge} {member['name']} - Уровень {member['level']}\n"
                
                bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            
            return jsonify({'ok': True}), 200
        
        # Команда /lvl - топ-5
        elif text == '/lvl':
            members = get_guild_members()
            sorted_members = sorted(members, key=lambda x: x['level'], reverse=True)[:5]
            
            message = '🏆 **Топ-5 сильнейших членов гильдии:**\n\n'
            for i, member in enumerate(sorted_members, 1):
                leader_badge = '👑' if member['is_leader'] else ''
                message += f"{i}. {leader_badge} {member['name']} - Уровень {member['level']}\n"
            
            bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            return jsonify({'ok': True}), 200
        
        # Команда /start
        elif text == '/start':
            bot.send_message(
                chat_id=chat_id,
                text='👋 Привет! Я бот для гильдии **Imperia Of Titans**\n\n'
                     '📋 Команды:\n'
                     '/online - показать онлайн-участников\n'
                     '/lvl - топ-5 сильнейших членов\n'
                     '/botguild - настроить оповещения (только админ)',
                parse_mode='Markdown'
            )
            return jsonify({'ok': True}), 200
        
        return jsonify({'ok': True}), 200
    
    except Exception as e:
        logger.error(f'❌ Error in webhook: {e}')
        return jsonify({'ok': False}), 500


@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья приложения"""
    try:
        # Проверяем MongoDB
        mongo_client.admin.command('ping')
        return jsonify({'status': 'ok', 'mongo': 'connected'}), 200
    except Exception as e:
        logger.error(f'Health check failed: {e}')
        return jsonify({'status': 'error', 'mongo': 'disconnected'}), 500


@app.route('/', methods=['GET'])
def index():
    """Главная страница"""
    return jsonify({
        'bot': 'Imperia Of Titans Guild Bot',
        'version': '1.0.0',
        'status': 'running',
        'webhook': '/webhook',
        'health': '/health'
    }), 200


if __name__ == '__main__':
    logger.info('🚀 Starting Guild Bot...')
    
    # Запускаем фоновый поток для проверки гильдии
    background_thread = threading.Thread(target=background_guild_checker, daemon=True)
    background_thread.start()
    logger.info('✅ Background checker thread started')
    
    # Запускаем Flask приложение
    logger.info(f'🌐 Running Flask app on 0.0.0.0:{PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=False)
