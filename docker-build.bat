@echo off
REM Скрипт для сборки Docker образа Pride YouthClub Bot (Windows)

echo 🔨 Сборка Docker образа Pride YouthClub Bot...
echo.

REM Проверка наличия необходимых файлов
if not exist ".env" (
    echo ❌ Ошибка: файл .env не найден!
    echo 📝 Создайте .env из .env.example:
    echo    copy .env.example .env
    exit /b 1
)

if not exist "service_account.json" (
    echo ❌ Ошибка: файл service_account.json не найден!
    echo 📝 Получите service_account.json из Google Cloud Console
    echo    См. SECURITY.md для инструкций
    exit /b 1
)

REM Сборка образа
docker build -t pride-youthclub-bot:latest .

if %errorlevel% equ 0 (
    echo.
    echo ✅ Образ успешно собран!
    echo.
    echo 🚀 Запустите бота командой:
    echo    docker-compose up -d
    echo.
    echo 📊 Или запустите напрямую:
    echo    docker run -d --name pride-bot --env-file .env pride-youthclub-bot:latest
) else (
    echo ❌ Ошибка при сборке образа
    exit /b 1
)
