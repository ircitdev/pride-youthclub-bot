# 📖 Pride YouthClub Bot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.7+](https://img.shields.io/badge/aiogram-3.7+-green.svg)](https://docs.aiogram.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Telegram бот для автоматизации реферального маркетинга и управления подписками фитнес-клуба

## 🚀 Описание

Pride YouthClub Bot автоматизирует продвижение **СК «ПРАЙД» / Клуба Омоложения** через реферальную систему.

### ✨ Основные возможности

- 🔗 **Реферальная система** с многоуровневыми бонусами
- 📊 **Google Sheets** как облачная база данных
- 💳 **Платежная система** (эмуляция/интеграция ЮKassa)
- 🎁 **Бонусная программа** за приглашения и платежи
- 👥 **Управление подписками** на каналы и группы
- 📈 **Аналитика для админов** с отчетами
- 🔔 **Автоуведомления** о событиях

### 📋 Документация

- 📖 **[SECURITY.md](SECURITY.md)** - Инструкции по безопасности (ОБЯЗАТЕЛЬНО К ПРОЧТЕНИЮ!)
- 📝 **[CHANGELOG.md](CHANGELOG.md)** - История изменений
- 🔧 **[.env.example](.env.example)** - Шаблон конфигурации

---

## ⚙️ Возможности бота
### Для обычных пользователей
- `/start` — приветствие + PDF `youthsecret.pdf` + меню:
  - 📢 **Перейти в канал** → ссылка на канал `PRIDEyouthClubChannel`
  - 🔒 **Закрытая группа** → выбор тарифа (оплата подписки)
  - 🤝 **Позвать подруг** → личная реферальная ссылка
  - 👩‍🏫 **О тренерах** → список тренеров (Мария Букина и др.)
- `/invite` — показать свои реферальные ссылки
- `/mystats` — список приглашённых и бонусов
- `/channel` — открыть канал Клуба Омоложения
- `/subscribe` — подписка на закрытую группу

### Для администраторов
- `/mystats today|week|month` — отчёт по выручке, комиссиям и ТОП-рефералам
- Автоматические уведомления в админ-чат:
  - новые пользователи
  - новые оплаты
  - начисления бонусов рефералам

---

## 📑 Google Sheets
Бот работает с таблицей, указанной в `.env` (`SHEET_URL`).  
Создаются вкладки:

- **Users**:  
  `timestamp | user_id | username | full_name | ref_source`

- **InviteLinks**:  
  `ref_id | bot_link | created_at | created_by`

- **Bonuses**:  
  `timestamp | ref_id | event | bonus`

- **Payments**:  
  `timestamp | user_id | username | full_name | tariff | price | period | status | ref_source`

---

## 🔑 Переменные окружения (.env)
Пример `.env`:

```env
BOT_TOKEN=8427...your_bot_token
ADMIN_CHAT_ID=-1003187490665       # чат или топик для админов
ADMIN_THREAD_ID=6                  # топик, если супергруппа
ADMINS=65876198,5956562518         # список админов (ID)

OPEN_CHANNEL_ID=-1003160140896     # ID открытого канала
CLOSED_GROUP_ID=-1003173420392     # ID закрытой группы
CLOSED_CHAT_LINK=https://t.me/+QlDchrC1cCFkMGMy

CHANNEL_BONUS=10
GROUP_BONUS=500

SHEET_URL=https://docs.google.com/spreadsheets/d/.../edit?usp=sharing
```

⚠️ Не забудь:
- выдать сервисному аккаунту доступ **Редактор** к Google Sheet;
- бот должен быть **админом** в канале и группе.

---

## 📦 Установка и запуск

### Быстрый старт

1. **Клонировать репозиторий**
   ```bash
   git clone <repository-url>
   cd pride-youthclub-bot
   ```

2. **Создать виртуальное окружение**
   ```bash
   python -m venv .venv

   # Linux/Mac
   source .venv/bin/activate

   # Windows
   .venv\Scripts\activate
   ```

3. **Установить зависимости**
   ```bash
   pip install -r requirements.txt
   ```

4. **Настроить конфигурацию**
   ```bash
   # Скопировать шаблон
   cp .env.example .env

   # Отредактировать .env своими данными
   nano .env  # или любой редактор
   ```

5. **Добавить Google Service Account**
   - Получите `service_account.json` (см. [SECURITY.md](SECURITY.md#4-настройка-google-service-account))
   - Поместите файл в корень проекта
   - Дайте доступ к Google Sheets (см. документацию)

6. **Запустить бота**

   **Вариант 1: Оригинальный скрипт**
   ```bash
   python pride-youthclub-bot.py
   ```

   **Вариант 2: Модульная версия (рекомендуется)**
   ```bash
   python main.py
   ```

   **Вариант 3: Docker (рекомендуется для production)**
   ```bash
   # Сборка
   docker build -t pride-youthclub-bot:latest .

   # Запуск с docker-compose
   docker-compose up -d

   # Или напрямую
   docker run -d --name pride-bot --env-file .env \
     -v $(pwd)/service_account.json:/app/service_account.json:ro \
     -v $(pwd)/logs:/app/logs \
     pride-youthclub-bot:latest
   ```

   📖 **Подробнее:** см. [DOCKER_GUIDE.md](DOCKER_GUIDE.md) и [QUICK_START_DOCKER.md](QUICK_START_DOCKER.md)

### ⚠️ Важные проверки перед запуском

- [ ] `.env` файл создан и заполнен
- [ ] `service_account.json` находится в корне проекта
- [ ] Service Account имеет доступ к Google Sheets
- [ ] Бот создан через @BotFather
- [ ] Privacy Mode ОТКЛЮЧЕН в BotFather (`/setprivacy` → Disable)
- [ ] Бот добавлен как **администратор** во все каналы/группы

📚 **Подробная инструкция:** [SECURITY.md](SECURITY.md)

---

## 📚 Зависимости
- [aiogram 3.7+](https://docs.aiogram.dev)
- [gspread](https://gspread.readthedocs.io/)
- [python-dotenv](https://pypi.org/project/python-dotenv/)
- Google API Service Account (ключ JSON)

---

## 👩‍🏫 Блок «О тренерах»
В корне проекта нужно держать фото тренеров, напр. `bukina.jpg`.  
При клике на «О тренерах» пользователь видит список тренеров.  
Выбор тренера → бот отправляет описание + фото.

---

## 💳 Оплата
Реализована эмуляция ЮKassa:
- тарифы: 1 мес = 990₽, 3 мес = 2673₽ (-10%), 12 мес = 8910₽ (-25%)
- после оплаты → пользователь получает ссылку на закрытую группу
- рефереру начисляется 25% от суммы оплаты (в бонусах)

---

## 🔒 Privacy Mode
- Для работы с рефералами и проверкой подписки **Privacy Mode должен быть выключен** в BotFather.  
  Это позволит боту видеть новых участников.

---

✍️ Автор: Александр Успешный
📆 2025  
