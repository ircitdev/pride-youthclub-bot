#!/bin/bash
# Скрипт для сборки Docker образа Pride YouthClub Bot

echo "🔨 Сборка Docker образа Pride YouthClub Bot..."

# Проверка наличия необходимых файлов
if [ ! -f ".env" ]; then
    echo "❌ Ошибка: файл .env не найден!"
    echo "📝 Создайте .env из .env.example:"
    echo "   cp .env.example .env"
    exit 1
fi

if [ ! -f "service_account.json" ]; then
    echo "❌ Ошибка: файл service_account.json не найден!"
    echo "📝 Получите service_account.json из Google Cloud Console"
    echo "   См. SECURITY.md для инструкций"
    exit 1
fi

# Сборка образа
docker build -t pride-youthclub-bot:latest .

if [ $? -eq 0 ]; then
    echo "✅ Образ успешно собран!"
    echo ""
    echo "🚀 Запустите бота командой:"
    echo "   docker-compose up -d"
    echo ""
    echo "📊 Или запустите напрямую:"
    echo "   docker run -d --name pride-bot --env-file .env pride-youthclub-bot:latest"
else
    echo "❌ Ошибка при сборке образа"
    exit 1
fi
