# 🚀 Развертывание на сервере

## ✅ Проект успешно развернут на VPS!

**Сервер:** `root@83.166.247.130`
**Путь:** `~/bots/pride/pride-youthclub-bot`
**Статус:** 🟢 **Работает**

---

## 📊 Информация о развертывании

### Сервер
- **OS:** Ubuntu 6.8.0 (Linux)
- **Python:** 3.12.3
- **Docker:** 28.4.0
- **Docker Compose:** v2.39.2
- **Location:** `/root/bots/pride/pride-youthclub-bot`

### Бот
- **Имя:** @PRIDEyouthClub_bot
- **ID:** 8427133149
- **Режим:** Docker container (production)
- **Автозапуск:** Включен через systemd

---

## 🎛️ Управление ботом

### Через скрипт управления (рекомендуется)

```bash
# Подключиться к серверу
ssh root@83.166.247.130

# Перейти в директорию
cd ~/bots/pride/pride-youthclub-bot

# Использовать скрипт управления
./bot-control.sh {команда}
```

**Доступные команды:**

| Команда | Описание |
|---------|----------|
| `./bot-control.sh start` | Запустить бота |
| `./bot-control.sh stop` | Остановить бота |
| `./bot-control.sh restart` | Перезапустить бота |
| `./bot-control.sh status` | Статус контейнера |
| `./bot-control.sh logs` | Просмотр логов в реальном времени |
| `./bot-control.sh update` | Обновить из GitHub и перезапустить |

---

### Через Docker Compose

```bash
# Подключиться к серверу
ssh root@83.166.247.130
cd ~/bots/pride/pride-youthclub-bot

# Статус
docker-compose ps

# Логи
docker-compose logs -f

# Остановить
docker-compose stop

# Запустить
docker-compose start

# Перезапустить
docker-compose restart

# Остановить и удалить
docker-compose down

# Пересобрать и запустить
docker-compose up -d --build
```

---

### Через systemd (автозапуск при перезагрузке)

```bash
# Статус сервиса
systemctl status pride-bot

# Запустить
systemctl start pride-bot

# Остановить
systemctl stop pride-bot

# Перезапустить
systemctl restart pride-bot

# Включить автозапуск
systemctl enable pride-bot

# Отключить автозапуск
systemctl disable pride-bot

# Просмотр логов systemd
journalctl -u pride-bot -f
```

---

## 📝 Просмотр логов

### Логи в реальном времени
```bash
ssh root@83.166.247.130
cd ~/bots/pride/pride-youthclub-bot

# Через скрипт
./bot-control.sh logs

# Через docker-compose
docker-compose logs -f

# Последние 100 строк
docker-compose logs --tail=100
```

### Логи с фильтрацией
```bash
# Только ошибки
docker-compose logs | grep ERROR

# Только предупреждения
docker-compose logs | grep WARNING

# Только информация
docker-compose logs | grep INFO
```

---

## 🔄 Обновление бота

### Автоматическое обновление

```bash
ssh root@83.166.247.130
cd ~/bots/pride/pride-youthclub-bot

# Одна команда обновит всё
./bot-control.sh update
```

Скрипт выполнит:
1. Скачает последнюю версию с GitHub
2. Остановит текущий контейнер
3. Пересоберет Docker образ
4. Запустит обновленную версию

### Ручное обновление

```bash
ssh root@83.166.247.130
cd ~/bots/pride/pride-youthclub-bot

# 1. Остановить бота
docker-compose down

# 2. Получить обновления
git pull

# 3. Пересобрать образ
docker-compose build

# 4. Запустить
docker-compose up -d
```

---

## 🔒 Безопасность

### Файлы на сервере

**✅ Загружены:**
- Весь код проекта
- `.env` с конфигурацией
- `service_account.json` с ключами Google
- Медиа файлы (PDF, JPG)

**⚠️ Права доступа:**
```bash
# Проверить права
ssh root@83.166.247.130 "ls -la ~/bots/pride/pride-youthclub-bot/.env"

# Установить безопасные права (если нужно)
ssh root@83.166.247.130 "chmod 600 ~/bots/pride/pride-youthclub-bot/.env"
ssh root@83.166.247.130 "chmod 600 ~/bots/pride/pride-youthclub-bot/service_account.json"
```

---

## 🛡️ Мониторинг

### Проверка работы бота

```bash
# 1. Статус контейнера
ssh root@83.166.247.130 "cd ~/bots/pride/pride-youthclub-bot && docker-compose ps"

# 2. Использование ресурсов
ssh root@83.166.247.130 "docker stats pride-youthclub-bot --no-stream"

# 3. Логи за последний час
ssh root@83.166.247.130 "cd ~/bots/pride/pride-youthclub-bot && docker-compose logs --since=1h"

# 4. Healthcheck
ssh root@83.166.247.130 "docker inspect pride-youthclub-bot | grep -A 10 Health"
```

### Автоматический мониторинг (опционально)

Создайте cron задачу для проверки:

```bash
# Редактировать crontab
ssh root@83.166.247.130 "crontab -e"

# Добавить строку (проверка каждые 5 минут)
*/5 * * * * docker ps | grep pride-youthclub-bot || cd /root/bots/pride/pride-youthclub-bot && docker-compose up -d
```

---

## 🐛 Troubleshooting

### Бот не отвечает

**1. Проверьте статус:**
```bash
ssh root@83.166.247.130
cd ~/bots/pride/pride-youthclub-bot
docker-compose ps
```

**2. Проверьте логи:**
```bash
docker-compose logs --tail=50
```

**3. Перезапустите:**
```bash
./bot-control.sh restart
```

---

### Ошибка "Conflict: terminated by other getUpdates"

**Причина:** Запущено несколько экземпляров бота

**Решение:**
```bash
# Остановить все контейнеры
docker stop $(docker ps -q --filter ancestor=pride-youthclub-bot-pride-bot)

# Или полностью
cd ~/bots/pride/pride-youthclub-bot
docker-compose down

# Подождать 10 секунд
sleep 10

# Запустить заново
docker-compose up -d
```

---

### Контейнер постоянно перезапускается

**Проверьте:**
```bash
# Логи
docker-compose logs

# Причины:
# - Неверный BOT_TOKEN в .env
# - Проблемы с Google Sheets (service_account.json)
# - Нет интернета на сервере
```

---

### Обновление секретных данных

**Если нужно обновить .env или service_account.json:**

```bash
# С локальной машины
scp .env root@83.166.247.130:~/bots/pride/pride-youthclub-bot/
scp service_account.json root@83.166.247.130:~/bots/pride/pride-youthclub-bot/

# Перезапустить бота
ssh root@83.166.247.130 "cd ~/bots/pride/pride-youthclub-bot && ./bot-control.sh restart"
```

---

## 📊 Полезные команды

### Информация о системе
```bash
# Использование диска
ssh root@83.166.247.130 "df -h"

# Использование RAM
ssh root@83.166.247.130 "free -h"

# Нагрузка CPU
ssh root@83.166.247.130 "top -bn1 | head -20"

# Запущенные контейнеры
ssh root@83.166.247.130 "docker ps"

# Использование Docker
ssh root@83.166.247.130 "docker system df"
```

### Очистка Docker (если места мало)
```bash
ssh root@83.166.247.130

# Удалить неиспользуемые образы
docker image prune -a

# Удалить неиспользуемые контейнеры
docker container prune

# Очистить всё (осторожно!)
docker system prune -a
```

---

## 🔧 Настройка после развертывания

### 1. Проверьте, что бот работает
Отправьте `/start` боту в Telegram: @PRIDEyouthClub_bot

### 2. Настройте мониторинг
- Проверяйте логи раз в день
- Настройте алерты при ошибках

### 3. Сделайте резервную копию
```bash
# Backup .env и service_account.json
ssh root@83.166.247.130 "tar -czf ~/bot-backup-$(date +%Y%m%d).tar.gz -C ~/bots/pride/pride-youthclub-bot .env service_account.json"

# Скачать на локальную машину
scp root@83.166.247.130:~/bot-backup-*.tar.gz ./
```

---

## 📞 Быстрый доступ

```bash
# SSH подключение
ssh root@83.166.247.130

# Директория бота
cd ~/bots/pride/pride-youthclub-bot

# Статус
./bot-control.sh status

# Логи
./bot-control.sh logs

# Перезапуск
./bot-control.sh restart
```

---

## ✅ Чеклист развертывания

- [x] Проект клонирован на сервер
- [x] .env и service_account.json скопированы
- [x] Docker образ собран
- [x] Бот запущен через docker-compose
- [x] Systemd сервис создан и включен
- [x] Скрипт управления bot-control.sh создан
- [x] Автозапуск настроен
- [x] Бот работает и отвечает в Telegram

---

🎉 **Бот успешно развернут и работает на production сервере!**

**Ссылка на бота:** https://t.me/PRIDEyouthClub_bot
