# 🚀 Быстрый запуск с Docker

## ⚡ За 3 шага

### 1️⃣ Убедитесь, что Docker Desktop запущен

**Windows:**
- Откройте Docker Desktop из меню Пуск
- Дождитесь, пока статус станет "Docker Desktop is running"

**Проверка:**
```bash
docker --version
# Должно вывести: Docker version 20.x.x или выше
```

---

### 2️⃣ Соберите Docker образ

**Windows:**
```cmd
docker-build.bat
```

**Linux/Mac:**
```bash
chmod +x docker-build.sh
./docker-build.sh
```

**Или вручную:**
```bash
docker build -t pride-youthclub-bot:latest .
```

---

### 3️⃣ Запустите бота

**Способ 1: Docker Compose (рекомендуется)**
```bash
docker-compose up -d
```

**Способ 2: Прямой запуск**
```bash
docker run -d \
  --name pride-bot \
  --restart unless-stopped \
  --env-file .env \
  -v "$(pwd)/service_account.json:/app/service_account.json:ro" \
  -v "$(pwd)/youthsecret.pdf:/app/youthsecret.pdf:ro" \
  -v "$(pwd)/bukina.jpg:/app/bukina.jpg:ro" \
  -v "$(pwd)/logs:/app/logs" \
  pride-youthclub-bot:latest
```

---

## 📊 Проверка работы

```bash
# Статус контейнера
docker-compose ps

# Логи в реальном времени
docker-compose logs -f

# Или для прямого запуска
docker ps
docker logs -f pride-bot
```

---

## 🎛️ Управление

```bash
# Остановить
docker-compose stop

# Запустить снова
docker-compose start

# Перезапустить
docker-compose restart

# Остановить и удалить
docker-compose down
```

---

## 🐛 Если что-то пошло не так

### Docker не найден
```
ERROR: docker: command not found
```
**Решение:** Установите [Docker Desktop](https://www.docker.com/products/docker-desktop/)

---

### Docker не запущен
```
ERROR: Cannot connect to the Docker daemon
```
**Решение:** Запустите Docker Desktop и дождитесь, пока он полностью загрузится

---

### Ошибки при сборке
```bash
# Очистить кэш и пересобрать
docker-compose build --no-cache
docker-compose up -d
```

---

### Бот не работает

**1. Проверьте логи:**
```bash
docker-compose logs
```

**2. Частые проблемы:**
- ❌ Отсутствует `.env` → создайте из `.env.example`
- ❌ Отсутствует `service_account.json` → скачайте из Google Cloud
- ❌ Неверный BOT_TOKEN → проверьте в @BotFather
- ❌ Проблемы с временем → синхронизируйте системное время

---

## 📚 Подробная документация

См. **[DOCKER_GUIDE.md](DOCKER_GUIDE.md)** для полной информации.

---

✅ **Готово! Бот работает в Docker контейнере!**
