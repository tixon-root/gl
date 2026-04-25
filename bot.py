import os
import logging
import asyncio
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ───────────────────────── CONFIG ──────────────────────────
TOKEN       = os.environ["BOT_TOKEN"]
MONGO_URI   = os.environ["MONGO_URI"]
GUILD_URL   = "https://www.rucoyonline.com/guild/Imperia%20Of%20Titans"
ADMIN_ID    = 6395348885          # твой Telegram ID
PORT        = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # https://your-app.onrender.com

# ─────────────────────── LOGGING ───────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ─────────────────────── MONGO ─────────────────────────────
mongo  = MongoClient(MONGO_URI)
db     = mongo["guild_bot"]
col_members  = db["members"]        # {name, level, join_date, status, first_seen}
col_settings = db["settings"]       # {chat_id, thread_id}

def get_setting(key):
    doc = col_settings.find_one({"key": key})
    return doc["value"] if doc else None

def set_setting(key, value):
    col_settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

# ───────────────────── SCRAPER ──────────────────────────────
def fetch_guild() -> list[dict]:
    """
    Returns list of dicts:
      {name, level, join_date, status}
    status: 'Leader' | 'Supporter' | 'Online' | 'Member' | ''
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(GUILD_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    members = []
    # Find the members table — rows with Name/Level/Join date
    rows = soup.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        # Name cell may contain status badge
        name_cell = cols[0].get_text(separator=" ", strip=True)
        level_cell = cols[1].get_text(strip=True)
        date_cell  = cols[2].get_text(strip=True)

        if not level_cell.isdigit():
            continue  # header or unrelated row

        # Parse status from name_cell
        status = ""
        for s in ["Leader", "Supporter", "Online", "Moderator", "Member"]:
            if s in name_cell:
                status = s
                name_clean = name_cell.replace(s, "").strip()
                break
        else:
            name_clean = name_cell.strip()

        members.append({
            "name":      name_clean,
            "level":     int(level_cell),
            "join_date": date_cell,
            "status":    status,
        })

    return members

# ─────────────────── CHECK & NOTIFY ────────────────────────
async def check_guild(app: Application):
    """Called by scheduler every 5 minutes."""
    chat_id   = get_setting("chat_id")
    thread_id = get_setting("thread_id")
    if not chat_id:
        log.info("No chat configured yet — skipping check.")
        return

    try:
        current = fetch_guild()
    except Exception as e:
        log.error(f"Scrape error: {e}")
        return

    current_names = {m["name"] for m in current}
    stored        = list(col_members.find({}, {"_id": 0}))
    stored_names  = {m["name"] for m in stored}

    # ── New members ──────────────────────────────────────
    for m in current:
        if m["name"] not in stored_names:
            col_members.insert_one({**m, "first_seen": datetime.utcnow().isoformat()})
            rank = "👑 Лидер" if m["status"] == "Leader" else (
                   "🟢 Онлайн" if m["status"] == "Online" else
                   f"🛡 {m['status']}" if m["status"] else "⚔️ Новобранец")
            text = (
                f"🎉 *Новый участник!*\n\n"
                f"⚔️ *{m['name']}*\n"
                f"📊 Уровень: `{m['level']}`\n"
                f"🏷 Статус: {rank}\n"
                f"📅 Вступил: {m['join_date']}\n\n"
                f"Добро пожаловать в *Imperia Of Titans!* 🏰"
            )
            kwargs = dict(chat_id=chat_id, text=text, parse_mode="Markdown")
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            await app.bot.send_message(**kwargs)
            log.info(f"Welcomed new member: {m['name']}")

    # ── Left members ─────────────────────────────────────
    for m in stored:
        if m["name"] not in current_names:
            col_members.delete_one({"name": m["name"]})
            text = (
                f"👋 *Участник покинул гильдию*\n\n"
                f"⚔️ *{m['name']}*\n"
                f"📊 Уровень: `{m['level']}`\n\n"
                f"Удачи на просторах Rucoy! ⚔️"
            )
            kwargs = dict(chat_id=chat_id, text=text, parse_mode="Markdown")
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            await app.bot.send_message(**kwargs)
            log.info(f"Member left: {m['name']}")

    # Update levels / statuses for existing
    for m in current:
        col_members.update_one(
            {"name": m["name"]},
            {"$set": {"level": m["level"], "status": m["status"], "join_date": m["join_date"]}}
        )

# ─────────────────── BOT COMMANDS ──────────────────────────
async def cmd_botguild(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Only admin can call this — sets the target chat/topic."""
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Только администратор может настроить бота.")
        return

    chat_id   = update.effective_chat.id
    thread_id = update.message.message_thread_id  # None if no topic

    set_setting("chat_id",   chat_id)
    set_setting("thread_id", thread_id)

    topic_info = f" (топик #{thread_id})" if thread_id else ""
    await update.message.reply_text(
        f"✅ *Настройки сохранены!*\n"
        f"Чат: `{chat_id}`{topic_info}\n\n"
        f"Теперь все уведомления гильдии будут приходить сюда. 🏰",
        parse_mode="Markdown"
    )
    log.info(f"Admin set target chat={chat_id}, thread={thread_id}")


async def cmd_online(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Shows online members."""
    try:
        members = fetch_guild()
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при получении данных: {e}")
        return

    online = [m for m in members if m["status"] == "Online"]

    if not online:
        await update.message.reply_text(
            "🔴 *Онлайн участников нет*\n\nВсе офлайн в данный момент.",
            parse_mode="Markdown"
        )
        return

    lines = [f"🟢 *{m['name']}* — Lvl `{m['level']}`" for m in online]
    text = f"🟢 *Онлайн сейчас ({len(online)}):*\n\n" + "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_lvl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Shows top-5 members by level."""
    stored = list(col_members.find({}, {"_id": 0}).sort("level", -1).limit(5))

    if not stored:
        # fallback: fetch live
        try:
            members = fetch_guild()
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            return
        members.sort(key=lambda x: x["level"], reverse=True)
        stored = members[:5]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = []
    for i, m in enumerate(stored):
        rank_label = " 👑" if m.get("status") == "Leader" else ""
        lines.append(f"{medals[i]} *{m['name']}*{rank_label} — Lvl `{m['level']}`")

    text = "🏆 *Топ-5 игроков Imperia Of Titans:*\n\n" + "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏰 *Imperia Of Titans — Гильдейский Бот*\n\n"
        "Доступные команды:\n"
        "• /online — список онлайн участников\n"
        "• /lvl — топ-5 игроков по уровню\n"
        "• /botguild — установить этот чат как целевой _(только для админа)_\n\n"
        "Бот автоматически уведомляет о входе и выходе участников! ⚔️",
        parse_mode="Markdown"
    )

# ─────────────────────── FLASK ─────────────────────────────
flask_app = Flask(__name__)
application: Application = None   # будет заполнено в main()

@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Imperia Of Titans"})

@flask_app.route(f"/webhook/{TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return jsonify({"ok": True})

# ──────────────────────── MAIN ─────────────────────────────
async def main():
    global application

    application = (
        Application.builder()
        .token(TOKEN)
        .updater(None)          # Webhook mode — no polling
        .build()
    )

    # Register handlers
    application.add_handler(CommandHandler("start",    cmd_start))
    application.add_handler(CommandHandler("botguild", cmd_botguild))
    application.add_handler(CommandHandler("online",   cmd_online))
    application.add_handler(CommandHandler("lvl",      cmd_lvl))

    # Set webhook
    await application.initialize()
    wh = f"{WEBHOOK_URL.rstrip('/')}/webhook/{TOKEN}"
    await application.bot.set_webhook(wh)
    log.info(f"Webhook set: {wh}")

    # Scheduler for guild checks every 5 minutes
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_guild,
        "interval",
        minutes=5,
        args=[application],
        id="guild_check",
        max_instances=1,
    )
    scheduler.start()
    log.info("Scheduler started — checking guild every 5 minutes.")

    # Start Flask (blocking)
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{PORT}"]
    await serve(flask_app, config)


if __name__ == "__main__":
    asyncio.run(main())
