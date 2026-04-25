"""
Imperia Of Titans — Guild Bot
Flask + python-telegram-bot (webhook mode) + APScheduler
Designed to run on Render.com free tier via gunicorn.
"""

import os
import logging
import asyncio
import threading
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask, request as flask_request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler

# ─────────────────────────── CONFIG ────────────────────────────────
TOKEN       = os.environ["BOT_TOKEN"]
MONGO_URI   = os.environ["MONGO_URI"]
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
GUILD_URL   = "https://www.rucoyonline.com/guild/Imperia%20Of%20Titans"
ADMIN_ID    = 6395348885

# ─────────────────────────── LOGGING ───────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ─────────────────────────── MONGO ─────────────────────────────────
_mongo       = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
_db          = _mongo["guild_bot"]
col_members  = _db["members"]
col_settings = _db["settings"]


def get_setting(key):
    doc = col_settings.find_one({"key": key})
    return doc["value"] if doc else None


def set_setting(key, value):
    col_settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)


# ─────────────────────────── SCRAPER ───────────────────────────────
def fetch_guild() -> list:
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
        name_text = cols[0].get_text(separator=" ", strip=True)
        date_text = cols[2].get_text(strip=True)
        status = ""
        name_clean = name_text
        for badge in ("Leader", "Supporter", "Online", "Moderator", "Member"):
            if badge in name_text:
                status = badge
                name_clean = name_text.replace(badge, "").strip()
                break
        members.append({
            "name":      name_clean,
            "level":     int(level_text),
            "join_date": date_text,
            "status":    status,
        })
    return members


# ─────────────────────────── ASYNC LOOP ────────────────────────────
_loop = None
_app  = None


def _run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _submit(coro):
    if _loop is None:
        raise RuntimeError("Event loop not started")
    return asyncio.run_coroutine_threadsafe(coro, _loop)


# ─────────────────────────── GUILD CHECK ───────────────────────────
def guild_check_sync():
    _submit(_guild_check_async()).result(timeout=60)


async def _guild_check_async():
    chat_id   = get_setting("chat_id")
    thread_id = get_setting("thread_id")
    if not chat_id:
        log.info("No target chat set — skipping.")
        return
    try:
        current = fetch_guild()
    except Exception as exc:
        log.error(f"Scrape error: {exc}")
        return

    current_names = {m["name"] for m in current}
    stored        = list(col_members.find({}, {"_id": 0}))
    stored_names  = {m["name"] for m in stored}

    for m in current:
        if m["name"] not in stored_names:
            col_members.insert_one({**m, "first_seen": datetime.utcnow().isoformat()})
            rank = (
                "👑 Лидер"          if m["status"] == "Leader"  else
                "🟢 Онлайн"        if m["status"] == "Online"  else
                f"🛡 {m['status']}" if m["status"]               else
                "⚔️ Новобранец"
            )
            text = (
                f"🎉 *Новый участник\\!*\n\n"
                f"⚔️ *{m['name']}*\n"
                f"📊 Уровень: `{m['level']}`\n"
                f"🏷 Статус: {rank}\n"
                f"📅 Вступил: {m['join_date']}\n\n"
                f"Добро пожаловать в *Imperia Of Titans\\!* 🏰"
            )
            kw = dict(chat_id=chat_id, text=text, parse_mode="MarkdownV2")
            if thread_id:
                kw["message_thread_id"] = int(thread_id)
            await _app.bot.send_message(**kw)
            log.info(f"Welcomed: {m['name']}")

    for m in stored:
        if m["name"] not in current_names:
            col_members.delete_one({"name": m["name"]})
            text = (
                f"👋 *Участник покинул гильдию*\n\n"
                f"⚔️ *{m['name']}*\n"
                f"📊 Уровень: `{m['level']}`\n\n"
                f"Удачи на просторах Rucoy\\! ⚔️"
            )
            kw = dict(chat_id=chat_id, text=text, parse_mode="MarkdownV2")
            if thread_id:
                kw["message_thread_id"] = int(thread_id)
            await _app.bot.send_message(**kw)
            log.info(f"Left: {m['name']}")

    for m in current:
        col_members.update_one(
            {"name": m["name"]},
            {"$set": {"level": m["level"], "status": m["status"], "join_date": m["join_date"]}},
        )


# ─────────────────────────── BOT COMMANDS ──────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏰 *Imperia Of Titans — Гильдейский Бот*\n\n"
        "Команды:\n"
        "• /online — кто сейчас онлайн\n"
        "• /lvl — топ\\-5 по уровню\n"
        "• /botguild — настроить этот чат _(только для админа)_\n\n"
        "Бот автоматически уведомляет о входе и выходе участников\\! ⚔️",
        parse_mode="MarkdownV2",
    )


async def cmd_botguild(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Только администратор может настроить бота.")
        return
    chat_id   = update.effective_chat.id
    thread_id = update.message.message_thread_id
    set_setting("chat_id",   chat_id)
    set_setting("thread_id", thread_id)
    topic = f" \\(топик \\#{thread_id}\\)" if thread_id else ""
    await update.message.reply_text(
        f"✅ *Настройки сохранены\\!*\n"
        f"Чат: `{chat_id}`{topic}\n\n"
        f"Уведомления гильдии будут приходить сюда\\. 🏰",
        parse_mode="MarkdownV2",
    )
    log.info(f"Target set: chat={chat_id}, thread={thread_id}")


async def cmd_online(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        members = fetch_guild()
    except Exception as exc:
        await update.message.reply_text(f"❌ Ошибка: {exc}")
        return
    online = [m for m in members if m["status"] == "Online"]
    if not online:
        await update.message.reply_text(
            "🔴 *Онлайн участников нет*\n\nВсе офлайн\\.",
            parse_mode="MarkdownV2",
        )
        return
    lines = [f"🟢 *{m['name']}* — Lvl `{m['level']}`" for m in online]
    await update.message.reply_text(
        f"🟢 *Онлайн сейчас \\({len(online)}\\):*\n\n" + "\n".join(lines),
        parse_mode="MarkdownV2",
    )


async def cmd_lvl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    stored = list(col_members.find({}, {"_id": 0}).sort("level", -1).limit(5))
    if not stored:
        try:
            members = fetch_guild()
            members.sort(key=lambda x: x["level"], reverse=True)
            stored = members[:5]
        except Exception as exc:
            await update.message.reply_text(f"❌ Ошибка: {exc}")
            return
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = []
    for i, m in enumerate(stored):
        crown = " 👑" if m.get("status") == "Leader" else ""
        lines.append(f"{medals[i]} *{m['name']}*{crown} — Lvl `{m['level']}`")
    await update.message.reply_text(
        "🏆 *Топ\\-5 игроков Imperia Of Titans:*\n\n" + "\n".join(lines),
        parse_mode="MarkdownV2",
    )


# ─────────────────────────── FLASK APP ─────────────────────────────
flask_app = Flask(__name__)


@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Imperia Of Titans"})


@flask_app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    data   = flask_request.get_json(force=True)
    update = Update.de_json(data, _app.bot)
    _submit(_app.process_update(update)).result(timeout=30)
    return jsonify({"ok": True})


# ─────────────────────────── STARTUP ───────────────────────────────
def start_background_services():
    global _loop, _app

    _loop = asyncio.new_event_loop()
    threading.Thread(target=_run_loop, args=(_loop,), daemon=True).start()
    log.info("Background async loop started.")

    async def _build():
        app = (
            Application.builder()
            .token(TOKEN)
            .updater(None)
            .build()
        )
        app.add_handler(CommandHandler("start",    cmd_start))
        app.add_handler(CommandHandler("botguild", cmd_botguild))
        app.add_handler(CommandHandler("online",   cmd_online))
        app.add_handler(CommandHandler("lvl",      cmd_lvl))
        await app.initialize()
        return app

    _app = _submit(_build()).result(timeout=30)
    log.info("Telegram Application initialized.")

    if WEBHOOK_URL:
        wh_url = f"{WEBHOOK_URL}/webhook/{TOKEN}"
        async def _set_wh():
            await _app.bot.set_webhook(wh_url)
            log.info(f"Webhook set: {wh_url}")
        _submit(_set_wh()).result(timeout=15)
    else:
        log.warning("WEBHOOK_URL not set — webhook not registered!")

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        guild_check_sync,
        "interval",
        minutes=5,
        id="guild_check",
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.start()
    log.info("Scheduler started — guild check every 5 min.")


start_background_services()
