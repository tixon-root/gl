# 🏰 Imperia Of Titans — Guild Bot

Telegram-бот для гильдии **Imperia Of Titans** в игре Rucoy Online.

## Функции
- 🎉 Автоматическое приветствие новых участников
- 👋 Уведомление об уходе участников
- `/online` — список онлайн-участников (доступно всем)
- `/lvl` — топ-5 игроков по уровню (доступно всем)
- `/botguild` — установить целевой чат/топик (только для тебя)
- `/start` — справка

---

## 🚀 Деплой: шаг за шагом

### Шаг 1 — Создай Telegram бота
1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`
3. Введи имя бота, например: `Imperia Guild Bot`
4. Введи username, например: `imperiaofguild_bot`
5. **Скопируй токен** — он нужен в переменных окружения

---

### Шаг 2 — Залей код на GitHub

```bash
# 1. Создай новый репозиторий на github.com (назови: guild-bot)
# 2. В папке с кодом выполни:

git init
git add .
git commit -m "Initial commit: Imperia Guild Bot"
git branch -M main
git remote add origin https://github.com/ТВО_ИМЯ_ПОЛЬЗОВАТЕЛЯ/guild-bot.git
git push -u origin main
```

> Если git не установлен: [скачай](https://git-scm.com/downloads)

---

### Шаг 3 — Деплой на Render.com

1. Зайди на [render.com](https://render.com) и войди через GitHub
2. Нажми **New → Web Service**
3. Выбери свой репозиторий `guild-bot`
4. Настройки:
   - **Name:** `imperia-guild-bot`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Plan:** `Free`
5. Нажми **Advanced → Add Environment Variable** и добавь:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | токен от BotFather |
| `MONGO_URI` | `mongodb+srv://herozvz07_db_user:iXi80aUXy9qUtPcP@cluster0.bb0wzws.mongodb.net/?appName=Cluster0` |
| `WEBHOOK_URL` | оставь пустым пока |
| `PORT` | `8080` |

6. Нажми **Create Web Service** и подожди пока задеплоится (~2 мин)

---

### Шаг 4 — Установи WEBHOOK_URL

1. После деплоя Render даст тебе URL вида:  
   `https://imperia-guild-bot.onrender.com`
2. Зайди в настройки сервиса → **Environment**
3. Добавь переменную:
   - `WEBHOOK_URL` = `https://imperia-guild-bot.onrender.com`
4. Нажми **Save** — сервис перезапустится автоматически

---

### Шаг 5 — Настрой целевой чат

1. Добавь бота в нужный Telegram-чат
2. Если чат с **топиками** — зайди в нужный топик
3. Отправь команду: `/botguild`
4. Бот ответит подтверждением — всё готово! 🏰

---

## ⚙️ Как работает проверка гильдии

Каждые **5 минут** бот заходит на сайт гильдии и сравнивает список участников с базой данных MongoDB.

- Новый участник → приветственное сообщение в чат
- Участник ушёл → уведомление об уходе

---

## 📝 Обновление кода

Если нужно изменить код:

```bash
git add .
git commit -m "Update bot"
git push
```

Render автоматически передеплоит бота при пуше в main.

---

## ❓ Частые проблемы

| Проблема | Решение |
|----------|---------|
| Бот не отвечает | Проверь BOT_TOKEN в переменных Render |
| Нет уведомлений | Выполни `/botguild` в нужном чате |
| Ошибка MongoDB | Проверь MONGO_URI — не должно быть пробелов |
| Render засыпает | Free план может засыпать, но webhook разбудит бота при следующем обновлении |
