# 🐳 Docker Guide - Pride YouthClub Bot

## 📋 Содержание
- [Предварительные требования](#предварительные-требования)
- [Быстрый старт](#быстрый-старт)
- [Docker Compose (рекомендуется)](#docker-compose-рекомендуется)
- [Ручной запуск](#ручной-запуск)
- [Управление контейнером](#управление-контейнером)
- [Просмотр логов](#просмотр-логов)
- [Troubleshooting](#troubleshooting)

---

## 🔧 Предварительные требования

### 1. Установка Docker

**Windows:**
1. Скачайте [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Запустите установщик
3. После установки перезагрузите компьютер
4. Запустите Docker Desktop

**Linux:**
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Проверка установки
docker --version
docker-compose --version
```

**macOS:**
1. Скачайте [Docker Desktop для Mac](https://www.docker.com/products/docker-desktop/)
2. Перетащите в Applications
3. Запустите Docker Desktop

### 2. Проверка Docker

```bash
# Проверить, что Docker работает
docker ps

# Должен вывести список контейнеров (может быть пустым)
```

---

## 🚀 Быстрый старт

### Шаг 1: Подготовка файлов

Убедитесь, что у вас есть:
- ✅ `.env` (скопируйте из `.env.example` и заполните)
- ✅ `service_account.json` (ключ Google API)
- ✅ `youthsecret.pdf` (PDF материалы)
- ✅ `bukina.jpg` (фото тренера)

### Шаг 2: Сборка и запуск

**Windows:**
```cmd
docker-build.bat
docker-compose up -d
```

**Linux/Mac:**
```bash
./docker-build.sh
docker-compose up -d
```

### Шаг 3: Проверка работы

```bash
# Посмотреть статус
docker-compose ps

# Посмотреть логи
docker-compose logs -f pride-bot
```

---

## 🐳 Docker Compose (рекомендуется)

### Запуск бота

```bash
# Запуск в фоновом режиме
docker-compose up -d

# Запуск с выводом логов
docker-compose up
```

### Остановка бота

```bash
# Остановить контейнер
docker-compose stop

# Остановить и удалить контейнер
docker-compose down

# Остановить, удалить контейнер и volumes
docker-compose down -v
```

### Перезапуск

```bash
# Перезапуск контейнера
docker-compose restart

# Пересборка и запуск (после изменения кода)
docker-compose up -d --build
```

### Просмотр логов

```bash
# Последние логи
docker-compose logs

# Следить за логами в реальном времени
docker-compose logs -f

# Последние 100 строк
docker-compose logs --tail=100
```

---

## 🔨 Ручной запуск (без docker-compose)

### 1. Сборка образа

```bash
docker build -t pride-youthclub-bot:latest .
```

### 2. Запуск контейнера

```bash
docker run -d \
  --name pride-bot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/service_account.json:/app/service_account.json:ro \
  -v $(pwd)/youthsecret.pdf:/app/youthsecret.pdf:ro \
  -v $(pwd)/bukina.jpg:/app/bukina.jpg:ro \
  -v $(pwd)/logs:/app/logs \
  pride-youthclub-bot:latest
```

**Windows (PowerShell):**
```powershell
docker run -d `
  --name pride-bot `
  --restart unless-stopped `
  --env-file .env `
  -v ${PWD}/service_account.json:/app/service_account.json:ro `
  -v ${PWD}/youthsecret.pdf:/app/youthsecret.pdf:ro `
  -v ${PWD}/bukina.jpg:/app/bukina.jpg:ro `
  -v ${PWD}/logs:/app/logs `
  pride-youthclub-bot:latest
```

### 3. Просмотр логов

```bash
docker logs -f pride-bot
```

### 4. Остановка

```bash
docker stop pride-bot
docker rm pride-bot
```

---

## 📊 Управление контейнером

### Проверка статуса

```bash
# Список запущенных контейнеров
docker ps

# Список всех контейнеров (включая остановленные)
docker ps -a

# Детальная информация о контейнере
docker inspect pride-bot
```

### Вход в контейнер

```bash
# Запустить bash внутри контейнера
docker exec -it pride-bot bash

# Или sh, если bash недоступен
docker exec -it pride-bot sh

# Выход из контейнера
exit
```

### Просмотр ресурсов

```bash
# Использование CPU/RAM
docker stats pride-bot

# Использование диска
docker system df
```

---

## 📝 Просмотр логов

### Docker Compose

```bash
# Все логи
docker-compose logs

# Следить в реальном времени
docker-compose logs -f

# Последние N строк
docker-compose logs --tail=50

# Логи с временными метками
docker-compose logs -t

# Логи с фильтрацией
docker-compose logs | grep "ERROR"
```

### Обычный Docker

```bash
# Все логи
docker logs pride-bot

# Следить в реальном времени
docker logs -f pride-bot

# Последние N строк
docker logs --tail=50 pride-bot

# Логи с временными метками
docker logs -t pride-bot
```

### Логи в файлах

Логи также сохраняются в папке `./logs/`:
```bash
# Linux/Mac
tail -f logs/bot.log

# Windows
type logs\bot.log
```

---

## 🔧 Troubleshooting

### Docker не запускается

**Проблема:** `Cannot connect to Docker daemon`

**Решение:**
```bash
# Windows: Запустите Docker Desktop
# Linux: Запустите Docker сервис
sudo systemctl start docker
sudo systemctl enable docker
```

---

### Ошибка "permission denied"

**Проблема:** `permission denied while trying to connect to Docker`

**Решение (Linux):**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

### Контейнер не запускается

**Проверьте логи:**
```bash
docker-compose logs

# Или
docker logs pride-bot
```

**Частые причины:**
1. Отсутствует `.env` файл
2. Отсутствует `service_account.json`
3. Неверный `BOT_TOKEN` в `.env`
4. Неверный `SPREADSHEET_ID` в `.env`

---

### Бот не отвечает в Telegram

**Проверьте:**
1. Контейнер запущен: `docker ps`
2. Логи на ошибки: `docker-compose logs -f`
3. Токен бота правильный в `.env`
4. Privacy Mode отключен в @BotFather

---

### Обновление после изменения кода

```bash
# Остановить контейнер
docker-compose down

# Пересобрать образ
docker-compose build

# Запустить заново
docker-compose up -d

# Или одной командой
docker-compose up -d --build
```

---

### Очистка Docker

```bash
# Удалить все остановленные контейнеры
docker container prune

# Удалить неиспользуемые образы
docker image prune

# Удалить все неиспользуемые объекты
docker system prune

# Удалить ВСЕ (включая volumes)
docker system prune -a --volumes
```

---

## 🎯 Полезные команды

### Быстрые команды

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose stop

# Перезапуск
docker-compose restart

# Логи
docker-compose logs -f

# Статус
docker-compose ps

# Удалить все
docker-compose down
```

### Обновление

```bash
# Остановить, пересобрать, запустить
docker-compose down && \
docker-compose build && \
docker-compose up -d
```

### Бэкап

```bash
# Создать образ текущего состояния
docker commit pride-bot pride-bot-backup:$(date +%Y%m%d)

# Экспорт образа
docker save pride-bot-backup:latest > pride-bot-backup.tar

# Импорт образа
docker load < pride-bot-backup.tar
```

---

## 📚 Дополнительные ресурсы

- [Официальная документация Docker](https://docs.docker.com/)
- [Docker Compose документация](https://docs.docker.com/compose/)
- [Лучшие практики Dockerfile](https://docs.docker.com/develop/dev-best-practices/)

---

## ✅ Чеклист перед деплоем

- [ ] Docker Desktop установлен и запущен
- [ ] `.env` файл создан и заполнен
- [ ] `service_account.json` на месте
- [ ] Все медиа файлы (PDF, JPG) на месте
- [ ] Образ успешно собран
- [ ] Контейнер запущен
- [ ] Логи не показывают ошибок
- [ ] Бот отвечает в Telegram на `/start`

---

🎉 **Готово! Ваш бот работает в Docker контейнере!**
