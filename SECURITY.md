# 🔒 Инструкции по безопасности

## ⚠️ КРИТИЧЕСКИ ВАЖНО

### 1. Защита секретных данных

**НИКОГДА не коммитьте в Git следующие файлы:**
- `.env` - содержит токен бота и все настройки
- `service_account.json` - ключи Google API
- Любые файлы с расширением `.key`, `.pem`

**Проверьте .gitignore:**
```bash
# Убедитесь, что .gitignore содержит:
.env
service_account.json
*.key
*.pem
```

### 2. Настройка .env файла

**Создайте файл `.env` из шаблона:**

```bash
cp .env.example .env  # если есть шаблон
# или создайте вручную
```

**Пример безопасного .env:**
```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here

# Google Sheets
SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_SERVICE_ACCOUNT_JSON=service_account.json

# Каналы/Группы
OPEN_CHANNEL_ID=-1001234567890
CLOSED_GROUP_ID=-1001234567890
CLOSED_CHAT_LINK=https://t.me/+xxxxxxxxx

# Бонусы
CHANNEL_BONUS=10
GROUP_BONUS=500

# Администрирование
ADMIN_CHAT_ID=-1001234567890
ADMIN_THREAD_ID=0
ADMINS=your_user_id,username

DM_DELAY_MINUTES=15
```

### 3. Получение Bot Token

1. Найдите **@BotFather** в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен в `.env` как `BOT_TOKEN`
5. **ВАЖНО:** Отключите Privacy Mode командой `/setprivacy` → Disable

### 4. Настройка Google Service Account

#### Шаг 1: Создание проекта в Google Cloud

1. Перейдите на https://console.cloud.google.com
2. Создайте новый проект или выберите существующий
3. Включите **Google Sheets API** и **Google Drive API**

#### Шаг 2: Создание Service Account

1. Перейдите в **IAM & Admin** → **Service Accounts**
2. Нажмите **Create Service Account**
3. Укажите имя (например, `pride-bot`)
4. Нажмите **Create and Continue**
5. Пропустите роли (опционально)
6. Нажмите **Done**

#### Шаг 3: Создание ключа

1. Кликните на созданный Service Account
2. Перейдите в **Keys** → **Add Key** → **Create new key**
3. Выберите формат **JSON**
4. Сохраните файл как `service_account.json` в корне проекта
5. **Убедитесь**, что он есть в `.gitignore`!

#### Шаг 4: Настройка доступа к таблице

1. Откройте `service_account.json`
2. Скопируйте email (формат: `name@project-id.iam.gserviceaccount.com`)
3. Откройте вашу Google Sheets таблицу
4. Нажмите **Share** (Поделиться)
5. Вставьте скопированный email
6. Выберите роль **Editor** (Редактор)
7. Снимите галочку "Notify people" (чтобы не отправлять email)
8. Нажмите **Share**

### 5. Получение ID каналов/групп

Используйте вспомогательный скрипт:

```bash
python get_chat_ids.py
```

Или вручную:
1. Добавьте бота в канал/группу как **администратора**
2. Используйте бота [@userinfobot](https://t.me/userinfobot) в группе
3. Скопируйте ID (формат `-100xxxxxxxxxxxx`)

### 6. Права доступа бота

**Бот ДОЛЖЕН быть администратором в:**
- Открытом канале (`OPEN_CHANNEL_ID`)
- Закрытой группе (`CLOSED_GROUP_ID`)
- Админ-чате (`ADMIN_CHAT_ID`)

**Минимальные права:**
- ✅ Read Messages
- ✅ Send Messages
- ✅ Delete Messages (опционально)

### 7. Безопасность в production

#### Используйте переменные окружения

**Для Docker:**
```bash
docker run --env-file .env pride-bot
```

**Для systemd (Linux):**
```ini
[Service]
EnvironmentFile=/path/to/.env
ExecStart=/path/to/venv/bin/python /path/to/main.py
```

#### Ограничьте права файлов

```bash
chmod 600 .env
chmod 600 service_account.json
```

#### Регулярно обновляйте зависимости

```bash
pip list --outdated
pip install --upgrade aiogram gspread google-auth
```

### 8. Мониторинг и логи

**Логи содержат важную информацию, но НЕ секретные данные:**
```python
# ✅ Безопасно
log.info(f"Новый пользователь: {user_id}")

# ❌ ОПАСНО
log.info(f"BOT_TOKEN: {BOT_TOKEN}")
```

**Настройка ротации логов:**
```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'bot.log',
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5
)
```

### 9. Что делать при утечке токена

**Если BOT_TOKEN скомпрометирован:**

1. Немедленно зайдите в @BotFather
2. Найдите бота: `/mybots` → выберите бота
3. Нажмите **API Token** → **Revoke current token**
4. Получите новый токен
5. Обновите `.env`
6. Перезапустите бота
7. Проверьте логи на подозрительную активность

**Если service_account.json скомпрометирован:**

1. Зайдите в Google Cloud Console
2. **IAM & Admin** → **Service Accounts**
3. Найдите аккаунт → **Keys**
4. Удалите старый ключ (**Delete**)
5. Создайте новый ключ
6. Обновите `service_account.json`
7. Перезапустите бота

### 10. Проверка безопасности

**Чеклист перед деплоем:**

- [ ] `.gitignore` содержит `.env` и `service_account.json`
- [ ] Файлы с секретами не закоммичены в Git
- [ ] Privacy Mode отключен в BotFather
- [ ] Бот является админом во всех нужных чатах
- [ ] Service Account имеет доступ к Google Sheets
- [ ] Права на файлы установлены как `600`
- [ ] Все зависимости обновлены
- [ ] Логирование настроено корректно
- [ ] Тестовый запуск успешен

### 11. Резервное копирование

**Регулярно делайте бэкапы Google Sheets:**
```bash
# Через Google Sheets UI:
File → Download → Microsoft Excel (.xlsx)
```

**Или используйте автоматический экспорт:**
```python
import gspread
# Код экспорта в CSV/Excel
```

### 12. Контакты при проблемах

**Если обнаружили уязвимость:**
- НЕ публикуйте в открытых issue
- Свяжитесь с разработчиком напрямую
- Опишите проблему детально

---

## 📚 Дополнительные ресурсы

- [Безопасность Telegram Bot API](https://core.telegram.org/bots/api#using-a-local-bot-api-server)
- [Google Cloud Security Best Practices](https://cloud.google.com/security/best-practices)
- [OWASP Security Principles](https://owasp.org/www-project-top-ten/)

---

**Помните:** Безопасность - это процесс, а не одноразовое действие!
