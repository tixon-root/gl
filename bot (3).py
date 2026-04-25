"""
Imperia Of Titans — Guild Bot
"""
import os, logging, asyncio, threading
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask, request as freq, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler

# ── CONFIG ──────────────────────────────────────────────────────────
TOKEN       = os.environ.get("BOT_TOKEN", "")
MONGO_URI   = os.environ.get("MONGO_URI", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
GUILD_URL   = "https://www.rucoyonline.com/guild/Imperia%20Of%20Titans"
ADMIN_ID    = 6395348885

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── MONGO ────────────────────────────────────────────────────────────
_mongo       = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
_db          = _mongo["guild_bot"]
col_members  = _db["members"]
col_settings = _db["settings"]

def get_setting(key):
    doc = col_settings.find_one({"key": key})
    return doc["value"] if doc else None

def set_setting(key, value):
    col_settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

# ── SCRAPER ──────────────────────────────────────────────────────────
def fetch_guild():
    headers = {"User-Agent": "Mozilla/5.0 (compatible; GuildBot/1.0)"}
    resp = requests.get(GUILD_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    members = []
    for row in soup.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        level_text = cols[1].get_text(strip=True)
        if not level_text.isdigit():
            continue
        name_text  = cols[0].get_text(separator=" ", strip=True)
        date_text  = cols[2].get_text(strip=True)
        status, name_clean = "", name_text
        for badge in ("Leader", "Supporter", "Online", "Moderator", "Member"):
            if badge in name_text:
                status     = badge
                name_clean = name_text.replace(badge, "").strip()
                break
        members.append({"name": name_clean, "level": int(level_text),
                        "join_date": date_text, "status": status})
    return members

# ── ASYNC LOOP ───────────────────────────────────────────────────────
_loop = None
_app  = None

def _run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def _submit(coro):
    return asyncio.run_coroutine_threadsafe(coro, _loop)

# ── GUILD CHECK ──────────────────────────────────────────────────────
def guild_check_sync():
    try:
        _submit(_guild_check_async()).result(timeout=60)
    except Exception as e:
        log.error(f"guild_check_sync error: {e}")

async def _guild_check_async():
    chat_id   = get_setting("chat_id")
    thread_id = get_setting("thread_id")
    if not chat_id:
        return
    try:
        current = fetch_guild()
    except Exception as e:
        log.error(f"Scrape error: {e}")
        return

    current_names = {m["name"] for m in current}
    stored        = list(col_members.find({}, {"_id": 0}))
    stored_names  = {m["name"] for m in stored}

    for m in current:
        if m["name"] not in stored_names:
            col_members.insert_one({**m, "first_seen": datetime.utcnow().isoformat()})
            rank = ("👑 Лидер"     if m["status"] == "Leader"  else
                    "🟢 Онлайн"   if m["status"] == "Online"  else
                    f"🛡 {m['status']}" if m["status"] else "⚔️ Новобранец")
            text = (f"🎉 Новый участник!\n\n⚔️ {m['name']}\n"
                    f"📊 Уровень: {m['level']}\n🏷 Статус: {rank}\n"
                    f"📅 Вступил: {m['join_date']}\n\nДобро пожаловать в Imperia Of Titans! 🏰")
            kw = dict(chat_id=chat_id, text=text)
            if thread_id:
                kw["message_thread_id"] = int(thread_id)
            await _app.bot.send_message(**kw)
            log.info(f"Welcomed: {m['name']}")

    for m in stored:
        if m["name"] not in current_names:
            col_members.delete_one({"name": m["name"]})
            text = (f"👋 Участник покинул гильдию\n\n⚔️ {m['name']}\n"
                    f"📊 Уровень: {m['level']}\n\nУдачи на просторах Rucoy! ⚔️")
            kw = dict(chat_id=chat_id, text=text)
            if thread_id:
                kw["message_thread_id"] = int(thread_id)
            await _app.bot.send_message(**kw)
            log.info(f"Left: {m['name']}")

    for m in current:
        col_members.update_one({"name": m["name"]},
            {"$set": {"level": m["level"], "status": m["status"],
                      "join_date": m["join_date"]}})

# ── COMMANDS ─────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏰 Imperia Of Titans — Гильдейский Бот\n\n"
        "Команды:\n"
        "• /online — кто сейчас онлайн\n"
        "• /lvl — топ-5 по уровню\n"
        "• /botguild — настроить этот чат (только для админа)\n\n"
        "Бот автоматически уведомляет о входе и выходе участников! ⚔️"
    )

async def cmd_botguild(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Только администратор может настроить бота.")
        return
    chat_id   = update.effective_chat.id
    thread_id = update.message.message_thread_id
    set_setting("chat_id",   chat_id)
    set_setting("thread_id", thread_id)
    topic = f" (топик #{thread_id})" if thread_id else ""
    await update.message.reply_text(
        f"✅ Настройки сохранены!\nЧат: {chat_id}{topic}\n\n"
        f"Уведомления гильдии будут приходить сюда. 🏰"
    )
    log.info(f"Target set: chat={chat_id}, thread={thread_id}")

async def cmd_online(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        members = fetch_guild()
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return
    online = [m for m in members if m["status"] == "Online"]
    if not online:
        await update.message.reply_text("🔴 Онлайн участников нет. Все офлайн.")
        return
    lines = [f"🟢 {m['name']} — Lvl {m['level']}" for m in online]
    await update.message.reply_text(f"🟢 Онлайн сейчас ({len(online)}):\n\n" + "\n".join(lines))

async def cmd_lvl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    stored = list(col_members.find({}, {"_id": 0}).sort("level", -1).limit(5))
    if not stored:
        try:
            members = fetch_guild()
            members.sort(key=lambda x: x["level"], reverse=True)
            stored = members[:5]
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            return
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = [f"{medals[i]} {m['name']}{'👑' if m.get('status')=='Leader' else ''} — Lvl {m['level']}"
             for i, m in enumerate(stored)]
    await update.message.reply_text("🏆 Топ-5 игроков Imperia Of Titans:\n\n" + "\n".join(lines))

# ── FLASK ─────────────────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.get("/")
def health():
    return jsonify({"status": "ok"})

@flask_app.post(f"/webhook/{TOKEN}")
def webhook():
    data   = freq.get_json(force=True)
    update = Update.de_json(data, _app.bot)
    _submit(_app.process_update(update)).result(timeout=30)
    return jsonify({"ok": True})

# ── STARTUP (called by gunicorn post_fork) ───────────────────────────
def init_services():
    global _loop, _app
    if _loop is not None:
        return  # already started

    log.info("=== Initialising background services ===")

    _loop = asyncio.new_event_loop()
    threading.Thread(target=_run_loop, args=(_loop,), daemon=True).start()

    async def _build():
        app = Application.builder().token(TOKEN).updater(None).build()
        app.add_handler(CommandHandler("start",    cmd_start))
        app.add_handler(CommandHandler("botguild", cmd_botguild))
        app.add_handler(CommandHandler("online",   cmd_online))
        app.add_handler(CommandHandler("lvl",      cmd_lvl))
        await app.initialize()
        return app

    _app = _submit(_build()).result(timeout=30)
    log.info("PTB Application ready.")

    if WEBHOOK_URL:
        wh = f"{WEBHOOK_URL}/webhook/{TOKEN}"
        _submit(_app.bot.set_webhook(wh)).result(timeout=15)
        log.info(f"Webhook → {wh}")
    else:
        log.warning("WEBHOOK_URL not set!")

    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(guild_check_sync, "interval", minutes=5,
                  id="gc", max_instances=1, misfire_grace_time=60)
    sched.start()
    log.info("Scheduler started.")

# Gunicorn calls this after forking each worker
def post_fork(server, worker):
    init_services()

# Also run when executed directly (local dev)
init_services()
