# 📁 Структура проекта Pride YouthClub Bot

```
pride-youthclub-bot/
│
├── 📄 README.md                      # Главная документация
├── 🔒 SECURITY.md                    # Инструкции по безопасности
├── 📝 CHANGELOG.md                   # История изменений
├── 📊 IMPROVEMENTS_SUMMARY.md        # Резюме улучшений
├── 📁 PROJECT_STRUCTURE.md           # Этот файл
│
├── 🔧 .env.example                   # Шаблон конфигурации
├── 🔧 .env                            # Конфигурация (НЕ коммитить!)
├── 🛡️ .gitignore                     # Исключения для Git
│
├── 📦 requirements.txt               # Python зависимости
├── 🐳 Dockerfile                     # Docker образ
├── 📋 .dockerignore                  # Исключения для Docker
│
├── 🔑 service_account.json           # Google API ключи (НЕ коммитить!)
│
├── 📄 bukina.jpg                     # Фото тренера
├── 📄 youthsecret.pdf                # PDF материалы
│
├── 🐍 pride-youthclub-bot.py         # ОРИГИНАЛЬНЫЙ скрипт (работает)
├── 🐍 main.py                        # НОВАЯ точка входа (модульная)
├── 🐍 get_chat_ids.py                # Утилита получения ID
│
├── 📦 bot/                           # ✨ НОВЫЙ модуль бота
│   ├── __init__.py
│   ├── config.py                    # Конфигурация и переменные окружения
│   ├── keyboards.py                 # Inline клавиатуры
│   │
│   ├── 📂 services/                 # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── sheets.py               # Google Sheets интеграция
│   │   ├── utils.py                # Вспомогательные функции
│   │   ├── bonuses.py              # Логика бонусов и рефералов
│   │   ├── payments.py             # Обработка платежей
│   │   └── notifications.py        # Уведомления админам
│   │
│   └── 📂 handlers/                # Обработчики команд
│       ├── __init__.py
│       └── start.py                # /start и начальное взаимодействие
│
├── 📂 .venv/                        # Виртуальное окружение (НЕ коммитить!)
└── 📂 node_modules/                 # Node.js зависимости (НЕ коммитить!)
```

---

## 📚 Описание файлов

### Документация
| Файл | Описание |
|------|----------|
| `README.md` | Главная документация проекта, установка, использование |
| `SECURITY.md` | **ВАЖНО!** Инструкции по безопасности, настройка токенов |
| `CHANGELOG.md` | История изменений и версионирование |
| `IMPROVEMENTS_SUMMARY.md` | Подробное описание всех улучшений |
| `PROJECT_STRUCTURE.md` | Структура проекта (этот файл) |

### Конфигурация
| Файл | Описание | Коммитить? |
|------|----------|------------|
| `.env.example` | Шаблон конфигурации | ✅ Да |
| `.env` | Реальная конфигурация с секретами | ❌ НЕТ |
| `.gitignore` | Исключения для Git | ✅ Да |
| `.dockerignore` | Исключения для Docker | ✅ Да |
| `requirements.txt` | Python зависимости | ✅ Да |
| `Dockerfile` | Docker образ | ✅ Да |

### Секретные данные
| Файл | Описание | Коммитить? |
|------|----------|------------|
| `service_account.json` | Google API ключи | ❌ НИКОГДА |
| `.env` | Токены и ID | ❌ НИКОГДА |

### Исполняемые файлы
| Файл | Описание | Статус |
|------|----------|--------|
| `pride-youthclub-bot.py` | Оригинальный скрипт (659 строк) | ✅ Работает |
| `main.py` | Новая точка входа (модульная) | ✅ Работает |
| `get_chat_ids.py` | Утилита для получения ID каналов | ✅ Работает |

---

## 🏗️ Модуль `bot/`

### `bot/config.py`
Централизованная конфигурация:
- Загрузка переменных окружения
- Валидация обязательных параметров
- Настройка логирования
- Парсинг списка админов

### `bot/keyboards.py`
Все inline клавиатуры:
- `get_main_menu()` - Главное меню
- `get_trainers_menu()` - Меню тренеров
- `get_tariffs_menu()` - Тарифы подписки
- `get_payment_button()` - Кнопка оплаты

### `bot/services/`

#### `sheets.py`
Работа с Google Sheets:
- `init_sheets()` - Инициализация подключения
- Создание таблиц: Users, InviteLinks, Bonuses, Payments
- Автоматическое добавление заголовков

#### `utils.py`
Утилиты:
- `now()` - Текущее время в ISO формате
- `get_ref_id()` - Получение реферального ID
- `is_admin()` - Проверка прав админа
- `fmt_cur()` - Форматирование валюты
- `parse_period()` - Парсинг периодов (today/week/month)

#### `bonuses.py`
Бонусная система:
- `update_bonuses()` - Обновление баланса
- `count_user_total_bonus()` - Подсчет бонусов
- `append_user_event()` - Логирование событий
- `get_user_id_by_ref()` - Поиск по реф. ID
- `log_referrer_bonus()` - Начисление комиссии

#### `payments.py`
Платежи:
- `log_payment()` - Запись платежа в Sheets

#### `notifications.py`
Уведомления:
- `notify_admin_text()` - Текстовое уведомление
- `notify_admin()` - Уведомление о подписчике
- `monitor_payments()` - Фоновый мониторинг платежей

### `bot/handlers/`

#### `start.py`
Обработчики команд:
- `start_handler()` - /start с рефералом и PDF
- `register_start_handlers()` - Регистрация в dispatcher

---

## 🔄 Как работают два варианта запуска

### Вариант 1: Оригинальный (`pride-youthclub-bot.py`)
```bash
python pride-youthclub-bot.py
```
- Монолитный файл 659 строк
- Все функции в одном месте
- Работает "как есть"
- Подходит для простых изменений

### Вариант 2: Модульный (`main.py`)
```bash
python main.py
```
- Использует модули из `bot/`
- Легко расширяется
- Подходит для масштабирования
- Рекомендуется для разработки

**Оба варианта используют общие сервисы из `bot/services/`!**

---

## 📦 Зависимости

### Python (в `requirements.txt`)
```txt
aiogram==3.7.0          # Telegram Bot Framework
gspread==6.0.0          # Google Sheets API
google-auth==2.28.0     # OAuth2 (замена oauth2client)
python-dotenv==1.0.1    # Переменные окружения
```

### Node.js (в `package.json`)
```json
{
  "@anthropic-ai/claude-code": "^2.0.21"  // Claude Code CLI
}
```

---

## 🚀 Быстрый старт

1. **Клонировать проект**
   ```bash
   git clone <repo>
   cd pride-youthclub-bot
   ```

2. **Установить зависимости**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # или .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

3. **Настроить конфигурацию**
   ```bash
   cp .env.example .env
   # Отредактировать .env
   ```

4. **Добавить service_account.json**
   - Создать в Google Cloud Console
   - Скачать JSON ключ
   - Положить в корень проекта

5. **Запустить**
   ```bash
   # Оригинальная версия
   python pride-youthclub-bot.py

   # Или модульная версия
   python main.py
   ```

---

## 🔒 Важно для безопасности

**НИКОГДА не коммитьте:**
- ❌ `.env`
- ❌ `service_account.json`
- ❌ Любые файлы с токенами/ключами

**Всегда проверяйте `.gitignore` перед `git push`!**

---

## 📞 Дополнительная информация

См. также:
- **[README.md](README.md)** - Полная документация
- **[SECURITY.md](SECURITY.md)** - Инструкции по безопасности
- **[IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md)** - Что улучшилось

---

✨ **Проект готов к использованию!**
