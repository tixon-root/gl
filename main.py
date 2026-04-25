import os
import threading
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import asyncio

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MONGO_URL = 'mongodb+srv://herozvz07_db_user:iXi80aUXy9qUtPcP@cluster0.bb0wzws.mongodb.net/?appName=Cluster0'
PORT = int(os.getenv('PORT', 10000))
ADMIN_ID = 6395348885  # Your Telegram ID
GUILD_URL = 'https://www.rucoyonline.com/guild/Imperia%20Of%20Titans'

# Initialize Flask
app = Flask(__name__)

# MongoDB connection
try:
    client = MongoClient(MONGO_URL)
    db = client['guild_bot']
    config_collection = db['config']
    members_collection = db['members']
    logger.info('✅ MongoDB connected successfully')
except Exception as e:
    logger.error(f'❌ MongoDB connection failed: {e}')
    config_collection = None
    members_collection = None

# Global variable for bot application
bot_application = None

# Initialize Telegram bot
async def init_bot():
    global bot_application
    try:
        bot_application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Add handlers
        bot_application.add_handler(CommandHandler('start', start_command))
        bot_application.add_handler(CommandHandler('botguild', botguild_command))
        bot_application.add_handler(CommandHandler('online', online_command))
        bot_application.add_handler(CommandHandler('lvl', lvl_command))
        
        await bot_application.bot.set_my_commands([
            ('start', 'Start the bot'),
            ('botguild', 'Set notification channel (admin only)'),
            ('online', 'Show online members'),
            ('lvl', 'Show top 5 members by level'),
        ])
        
        logger.info('✅ Telegram bot initialized')
    except Exception as e:
        logger.error(f'❌ Bot initialization failed: {e}')

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        '👋 Hello! I am a guild bot for Imperia Of Titans.\n\n'
        'Available commands:\n'
        '/botguild - Set notification channel (admin only)\n'
        '/online - Show online members\n'
        '/lvl - Show top 5 members by level'
    )

async def botguild_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set notification channel"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text('❌ Only admin can use this command')
        return
    
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id or 0
    
    try:
        config_collection.update_one(
            {'_id': 'main'},
            {'$set': {
                'chat_id': chat_id,
                'thread_id': thread_id,
                'updated': datetime.now()
            }},
            upsert=True
        )
        await update.message.reply_text(
            f'✅ Notifications will be sent to this channel/topic!\n'
            f'Chat ID: {chat_id}\n'
            f'Thread ID: {thread_id}'
        )
        logger.info(f'✅ Config updated: chat_id={chat_id}, thread_id={thread_id}')
    except Exception as e:
        logger.error(f'❌ Error setting config: {e}')
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def online_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show online members"""
    try:
        members_data = members_collection.find_one({'_id': 'current'})
        if not members_data or 'members' not in members_data:
            await update.message.reply_text('📊 No member data available')
            return
        
        members = members_data['members']
        online_members = [m for m in members if m.get('status') == 'online']
        
        if not online_members:
            await update.message.reply_text('📊 No members online')
            return
        
        message = '🟢 **Online Members:**\n\n'
        for member in online_members:
            message += f"👤 {member['name']} - Lvl {member['level']}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'❌ Error in /online: {e}')
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def lvl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 5 members by level"""
    try:
        members_data = members_collection.find_one({'_id': 'current'})
        if not members_data or 'members' not in members_data:
            await update.message.reply_text('📊 No member data available')
            return
        
        members = members_data['members']
        sorted_members = sorted(members, key=lambda x: int(x['level']), reverse=True)[:5]
        
        message = '🏆 **Top 5 Members by Level:**\n\n'
        for i, member in enumerate(sorted_members, 1):
            leader_badge = ' 👑' if member.get('status') == 'leader' else ''
            message += f"{i}. {member['name']} - Lvl {member['level']}{leader_badge}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'❌ Error in /lvl: {e}')
        await update.message.reply_text(f'❌ Error: {str(e)}')

# Parse guild website
def parse_guild_members():
    """Parse guild members from website"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(GUILD_URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        members = []
        rows = soup.find_all('tr')
        
        for row in rows[1:]:  # Skip header row
            cols = row.find_all('td')
            if len(cols) >= 3:
                name = cols[0].text.strip()
                status = cols[1].text.strip().lower()
                level = cols[2].text.strip()
                
                # Skip if empty
                if not name or not level:
                    continue
                
                # Normalize status
                if 'leader' in status.lower():
                    status = 'leader'
                elif 'online' in status.lower():
                    status = 'online'
                elif 'supporter' in status.lower() or 'supporter' in name.lower():
                    status = 'supporter'
                else:
                    status = 'offline'
                
                members.append({
                    'name': name,
                    'status': status,
                    'level': int(level) if level.isdigit() else 0
                })
        
        logger.info(f'✅ Parsed {len(members)} members from guild')
        return members
    except Exception as e:
        logger.error(f'❌ Error parsing guild: {e}')
        return None

# Check guild for changes
async def check_guild_changes():
    """Check for new/left members and send notifications"""
    try:
        new_members = parse_guild_members()
        if not new_members:
            return
        
        # Get current members from DB
        members_data = members_collection.find_one({'_id': 'current'})
        old_members = members_data.get('members', []) if members_data else []
        
        old_names = {m['name'] for m in old_members}
        new_names = {m['name'] for m in new_members}
        
        # Find new and left members
        joined = new_names - old_names
        left = old_names - new_names
        
        # Update database
        members_collection.update_one(
            {'_id': 'current'},
            {'$set': {
                'members': new_members,
                'updated': datetime.now()
            }},
            upsert=True
        )
        
        # Send notifications
        if joined or left:
            config_data = config_collection.find_one({'_id': 'main'})
            if config_data:
                chat_id = config_data.get('chat_id')
                thread_id = config_data.get('thread_id', 0)
                
                if joined:
                    for member_name in joined:
                        message = f'🎉 **New member joined:** {member_name}'
                        try:
                            if thread_id and thread_id != 0:
                                await bot_application.bot.send_message(
                                    chat_id=chat_id,
                                    text=message,
                                    message_thread_id=thread_id,
                                    parse_mode='Markdown'
                                )
                            else:
                                await bot_application.bot.send_message(
                                    chat_id=chat_id,
                                    text=message,
                                    parse_mode='Markdown'
                                )
                            logger.info(f'✅ Sent join notification for {member_name}')
                        except Exception as e:
                            logger.error(f'❌ Error sending join notification: {e}')
                
                if left:
                    for member_name in left:
                        message = f'👋 **Member left:** {member_name}'
                        try:
                            if thread_id and thread_id != 0:
                                await bot_application.bot.send_message(
                                    chat_id=chat_id,
                                    text=message,
                                    message_thread_id=thread_id,
                                    parse_mode='Markdown'
                                )
                            else:
                                await bot_application.bot.send_message(
                                    chat_id=chat_id,
                                    text=message,
                                    parse_mode='Markdown'
                                )
                            logger.info(f'✅ Sent leave notification for {member_name}')
                        except Exception as e:
                            logger.error(f'❌ Error sending leave notification: {e}')
    except Exception as e:
        logger.error(f'❌ Error checking guild changes: {e}')

# Background thread for guild checking
def background_guild_checker():
    """Background thread to check guild every 5 minutes"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            loop.run_until_complete(check_guild_changes())
        except Exception as e:
            logger.error(f'❌ Background checker error: {e}')
        
        # Wait 5 minutes
        import time
        time.sleep(300)

# Flask routes
@app.route('/', methods=['GET'])
def home():
    """Health check"""
    return jsonify({'status': 'ok', 'bot': 'Guild Bot is running'}), 200

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Telegram webhook handler"""
    try:
        update_data = request.get_json()
        update = Update.de_json(update_data, bot_application.bot)
        
        await bot_application.process_update(update)
        return jsonify({'ok': True}), 200
    except Exception as e:
        logger.error(f'❌ Webhook error: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

# Main
if __name__ == '__main__':
    # Initialize bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_bot())
    
    # Start background thread for guild checking
    checker_thread = threading.Thread(target=background_guild_checker, daemon=True)
    checker_thread.start()
    logger.info('✅ Background guild checker started')
    
    # Start Flask app
    logger.info(f'🚀 Starting Flask server on 0.0.0.0:{PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=False)