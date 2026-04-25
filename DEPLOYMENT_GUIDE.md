# 🚀 Гайд развертывания на Render

## Шаг 1: Подготовка Telegram бота

1. Откройте Telegram и найдите **@BotFather**
2. Отправьте команду `/newbot`
3. Следуйте инструкциям:
   - Введите имя бота (например: `Imperia Guild Bot`)
   - Введите username (например: `imperia_guild_bot`)
4. Скопируйте полученный токен (выглядит так: `123456789:ABCDefGHiJKlmNoPqRsTuvWxYzABCDeFgHiJk`)

## Шаг 2: Создание сервиса на Render

1. Перейдите на https://render.com
2. Нажмите **"New +"** → **"Web Service"**
3. Выберите **"Connect a repository"**
4. Найдите и выберите репозиторий `tixon-root/gl`
5. Заполните данные:
   - **Name:** `guild-bot`
   - **Environment:** Python 3
   - **Build Command:** (оставьте пусто или `pip install -r requirements.txt`)
   - **Start Command:** `gunicorn main:app`
   - **Instance Type:** Free

## Шаг 3: Добавление переменных окружения

1. В Render Dashboard вашего сервиса перейдите в **"Environment"**
2. Нажмите **"Add Environment Variable"**
3. Добавьте:
   - **Key:** `TELEGRAM_TOKEN`
   - **Value:** (вставьте токен из шага 1)
4. Сохраните

## Шаг 4: Запуск деплоя

1. Render автоматически запустит деплой
2. Дождитесь успешного построения (Build successful ✅)
3. Сервис будет доступен по адресу: `https://guild-bot.onrender.com` (или похожему)

## Шаг 5: Установка Webhook

### Способ 1: Через cURL (рекомендуется)

```bash
curl -X POST https://api.telegram.org/bot{YOUR_TOKEN}/setWebhook \
  -d url=https://guild-bot.onrender.com/webhook
```

Замените:
- `{YOUR_TOKEN}` на ваш токен
- `guild-bot.onrender.com` на реальный URL вашего сервиса

### Способ 2: Через скрипт Python

```bash
python setup_webhook.py YOUR_TOKEN https://guild-bot.onrender.com
```

### Способ 3: Онлайн

Отправьте в браузер:
```
https://api.telegram.org/bot{YOUR_TOKEN}/setWebhook?url=https://guild-bot.onrender.com/webhook
```

## Шаг 6: Проверка вебхука

```bash
curl https://api.telegram.org/bot{YOUR_TOKEN}/getWebhookInfo
```

Должны увидеть:
```json
{
  "ok": true,
  "result": {
    "url": "https://guild-bot.onrender.com/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "...": "..."
  }
}
```

## Шаг 7: Тестирование бота

1. Откройте Telegram
2. Найдите вашего бота по username
3. Отправьте `/start` - должен ответить
4. Добавьте бота в групповой чат
5. Отправьте `/botguild` (если вы админ)
6. Отправьте `/online` или `/lvl` - должны работать

## 🔍 Troubleshooting

### Бот не отвечает

1. **Проверьте логи на Render:**
   - Dashboard → Logs → смотрите ошибки

2. **Проверьте вебхук:**
   ```bash
   curl https://api.telegram.org/bot{TOKEN}/getWebhookInfo
   ```

3. **Убедитесь, что токен правильный**

4. **Сервис спит на Render?**
   - Render может выключать free сервисы
   - Проверьте, что сервис активен

### Уведомления не приходят

1. **Убедитесь, что использовали `/botguild`**
2. **Проверьте MongoDB подключение в логах**
3. **Перезагрузите сервис**

### MongoDB ошибка

1. **Проверьте, что URL в коде правильный**
2. **Проверьте, что MongoDB кластер активен**
3. **Проверьте IP whitelist в MongoDB Atlas**

## 📊 Мониторинг

### Проверка здоровья бота

```bash
curl https://guild-bot.onrender.com/
```

Должен вернуть:
```json
{"status": "ok", "bot": "Guild Bot is running"}
```

### Просмотр логов

1. Render Dashboard → ваш сервис
2. Вкладка **"Logs"**
3. Смотрите в реальном времени

## 🎉 Готово!

Теперь ваш бот работает 24/7 на Render! 🚀

Если что-то не работает, смотрите логи и проверяйте каждый шаг выше.