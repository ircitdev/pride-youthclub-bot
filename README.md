# 🏆 Pride YouthClub Bot

<div align="center">

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![aiogram](https://img.shields.io/badge/aiogram-3.7+-green.svg)
![Google Sheets](https://img.shields.io/badge/Google%20Sheets-API-34A853?logo=google-sheets)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)

**Telegram бот для автоматизации реферального маркетинга и управления подписками фитнес-клуба**

[Возможности](#-возможности) •
[Установка](#-установка) •
[Документация](#-документация) •
[Docker](#-docker) •
[Безопасность](#-безопасность)

</div>

---

## 📖 Описание

Pride YouthClub Bot - это полнофункциональный Telegram бот для автоматизации продвижения **СК «ПРАЙД» / Клуба Омоложения** через систему реферального маркетинга.

### 🎯 Для кого этот проект?

- 🏋️ **Фитнес-клубы** и студии
- 💆 **Студии красоты** и омоложения
- 📚 **Образовательные** платформы
- 🎓 **Онлайн-школы** и курсы
- 💼 Любой **бизнес с партнерской программой**

---

## ✨ Возможности

### 🔗 Реферальная система
- Генерация персональных реферальных ссылок
- Многоуровневое начисление бонусов
- Отслеживание рефералов в реальном времени
- Комиссия 25% от платежей приглашенных

### 💰 Монетизация
- Система тарифов (1/3/12 месяцев)
- Автоматические скидки
- Интеграция с платежными системами (готово под YooKassa)
- Учет всех транзакций в Google Sheets

### 📊 Аналитика
- Детальная статистика для админов
- Отчеты по периодам (день/неделя/месяц)
- ТОП-10 рефералов
- Выручка и комиссии в реальном времени

### 🎁 Бонусная программа
- Бонусы за подписку на канал (+10)
- Бонусы за вступление в группу (+500)
- Комиссия 25% от платежей рефералов
- Автоматическое начисление и уведомления

### 👥 Управление подписками
- Проверка подписки на Telegram каналы
- Автоматическая выдача доступа к закрытым группам
- Отправка приветственных материалов (PDF)
- Профили тренеров с фото и описанием

### 🔔 Автоуведомления
- Уведомления админам о новых пользователях
- Алерты о платежах в реальном времени
- Логи всех событий в Google Sheets
- Фоновый мониторинг таблиц

---

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.11+
- Telegram Bot Token (от [@BotFather](https://t.me/BotFather))
- Google Service Account с доступом к Sheets API
- Docker (опционально, для production)

### Установка за 5 минут

```bash
# 1. Клонировать репозиторий
git clone https://github.com/ircitdev/pride-youthclub-bot.git
cd pride-youthclub-bot

# 2. Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить конфигурацию
cp .env.example .env
# Отредактировать .env своими данными

# 5. Добавить Google Service Account
# Скачать service_account.json из Google Cloud Console
# Положить в корень проекта

# 6. Запустить бота
python pride-youthclub-bot.py
```

---

## 📦 Структура проекта

```
pride-youthclub-bot/
├── 📄 README.md                  # Документация
├── 🔒 SECURITY.md                # Инструкции по безопасности
├── 📝 CHANGELOG.md               # История версий
├── 🐳 DOCKER_GUIDE.md            # Docker инструкция
│
├── 🐍 pride-youthclub-bot.py     # Основной скрипт
├── 🐍 main.py                    # Модульная версия
├── 🐍 get_chat_ids.py            # Утилита получения ID
│
├── 📦 bot/                       # Модульная архитектура
│   ├── config.py                # Конфигурация
│   ├── keyboards.py             # Клавиатуры
│   ├── services/                # Бизнес-логика
│   │   ├── sheets.py           # Google Sheets
│   │   ├── bonuses.py          # Бонусная система
│   │   ├── payments.py         # Платежи
│   │   ├── notifications.py    # Уведомления
│   │   └── utils.py            # Утилиты
│   └── handlers/               # Обработчики команд
│       └── start.py
│
├── 🐳 Dockerfile                 # Docker образ
├── 🐳 docker-compose.yml         # Docker Compose
├── 📋 requirements.txt           # Python зависимости
└── 🔧 .env.example              # Шаблон конфигурации
```

---

## 🎮 Команды бота

### Для пользователей

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие + PDF + главное меню |
| `/invite` | Получить реферальную ссылку |
| `/mystats` | Личная статистика и бонусы |
| `/trainers` | Профили тренеров |
| `/channel` | Ссылка на канал |
| `/subscribe` | Оформить подписку |

### Для админов

| Команда | Описание |
|---------|----------|
| `/mystats` | Сводка по выручке и ТОП-рефералам |
| `/mystats today` | Статистика за сегодня |
| `/mystats week` | Статистика за неделю |
| `/mystats month` | Статистика за месяц |

---

## 🐳 Docker

### Запуск с Docker Compose (рекомендуется)

```bash
# Сборка образа
docker build -t pride-youthclub-bot:latest .

# Запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

### Ручной запуск

```bash
docker run -d \
  --name pride-bot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/service_account.json:/app/service_account.json:ro \
  -v $(pwd)/logs:/app/logs \
  pride-youthclub-bot:latest
```

📖 **Полная инструкция:** [DOCKER_GUIDE.md](DOCKER_GUIDE.md)

---

## 📊 Google Sheets структура

Бот автоматически создает 4 таблицы:

### 1. Users
| Колонка | Описание |
|---------|----------|
| timestamp | Время события |
| user_id | Telegram ID |
| username | @username |
| full_name | Полное имя |
| ref_source | Источник реферала |
| action | Тип действия |
| object | Объект действия |
| bonus | Начисленные бонусы |

### 2. InviteLinks
| Колонка | Описание |
|---------|----------|
| ref_id | ID реферера |
| bot_link | Реферальная ссылка |
| created_at | Время создания |
| created_by | Создатель |

### 3. Bonuses
| Колонка | Описание |
|---------|----------|
| ref_id | ID реферера |
| total_refs | Всего рефералов |
| total_bonus | Сумма бонусов |
| updated_at | Последнее обновление |

### 4. Payments
| Колонка | Описание |
|---------|----------|
| timestamp | Время платежа |
| user_id | ID покупателя |
| tariff | Тариф |
| price | Сумма |
| period | Период |
| status | Статус |
| ref_source | Реферал |
| notified | Флаг уведомления |

---

## 🔒 Безопасность

### ⚠️ КРИТИЧЕСКИ ВАЖНО

**Никогда не коммитьте:**
- ❌ `.env` файл
- ❌ `service_account.json`
- ❌ Любые файлы с токенами

### ✅ Чеклист безопасности

- [ ] `.gitignore` содержит секретные файлы
- [ ] `.env` создан из `.env.example`
- [ ] Service Account имеет минимальные права
- [ ] BOT_TOKEN хранится только в `.env`
- [ ] Privacy Mode отключен в BotFather
- [ ] Бот является админом во всех каналах

📖 **Подробная инструкция:** [SECURITY.md](SECURITY.md)

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [README.md](README.md) | Основная документация |
| [SECURITY.md](SECURITY.md) | Инструкции по безопасности (ОБЯЗАТЕЛЬНО!) |
| [DOCKER_GUIDE.md](DOCKER_GUIDE.md) | Полное руководство по Docker |
| [QUICK_START_DOCKER.md](QUICK_START_DOCKER.md) | Быстрый старт с Docker |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |
| [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md) | Обзор улучшений |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Структура проекта |

---

## 🛠️ Технологии

- **Python 3.11+** - язык программирования
- **aiogram 3.7+** - Telegram Bot Framework
- **Google Sheets API** - облачная база данных
- **google-auth** - аутентификация Google API
- **Docker** - контейнеризация
- **python-dotenv** - управление конфигурацией

---

## 🎯 Roadmap

### В разработке
- [ ] Интеграция с YooKassa для реальных платежей
- [ ] Миграция на PostgreSQL
- [ ] Webhook вместо polling
- [ ] Юнит-тесты (pytest)
- [ ] CI/CD через GitHub Actions

### Планируется
- [ ] Админ-панель (веб-интерфейс)
- [ ] Мультиязычность (i18n)
- [ ] Система достижений
- [ ] Экспорт статистики в PDF
- [ ] Telegram WebApp интеграция

---

## 🤝 Вклад в проект

Contributions are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.

---

## 🙏 Благодарности

- [aiogram](https://github.com/aiogram/aiogram) - отличный фреймворк для Telegram ботов
- [gspread](https://github.com/burnash/gspread) - удобная работа с Google Sheets
- Telegram Bot API команда за прекрасное API

---

## 📞 Поддержка

Нашли баг? Есть вопрос?

- 🐛 [Создать Issue](https://github.com/ircitdev/pride-youthclub-bot/issues)
- 💬 [Обсуждения](https://github.com/ircitdev/pride-youthclub-bot/discussions)
- 📧 Email: ircitdev@users.noreply.github.com

---

## ⭐ Поддержите проект

Если проект оказался полезным - поставьте звездочку! ⭐

---

<div align="center">

**Сделано с ❤️ для фитнес-индустрии**

[GitHub](https://github.com/ircitdev/pride-youthclub-bot) •
[Документация](README.md) •
[Безопасность](SECURITY.md)

</div>
