"""Главный файл запуска Pride YouthClub Bot с модульной архитектурой."""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram.client.default import DefaultBotProperties

from bot.config import BOT_TOKEN, ADMINS, log
from bot.services.notifications import monitor_payments

# Импорт старых обработчиков из оригинального файла
# В будущем их нужно будет разнести по модулям
import pride_youthclub_bot as old_bot


async def setup_commands(bot: Bot) -> None:
    """
    Настраивает команды бота для пользователей и админов.

    Args:
        bot: Объект бота
    """
    user_cmds = [
        BotCommand(command="invite", description="Мои ссылки"),
        BotCommand(command="mystats", description="Моя статистика"),
        BotCommand(command="trainers", description="О тренерах"),
        BotCommand(command="channel", description="Канал Клуб Омоложения"),
        BotCommand(command="subscribe", description="Подписка на закрытую группу"),
    ]
    await bot.set_my_commands(user_cmds)

    admin_cmds = user_cmds + [
        BotCommand(command="top", description="Рейтинг ТОП-10"),
    ]

    for admin_id in ADMINS:
        if isinstance(admin_id, int):
            try:
                await bot.set_my_commands(
                    admin_cmds,
                    scope=BotCommandScopeChat(chat_id=admin_id)
                )
            except Exception as e:
                log.warning(f"Не удалось установить команды для админа {admin_id}: {e}")


async def main():
    """Главная функция запуска бота."""
    log.info("Запуск Pride YouthClub Bot (модульная версия)")

    # Инициализация бота и диспетчера
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # Регистрация обработчиков из старого файла
    # TODO: Перенести в отдельные модули
    old_bot.bot = bot
    old_bot.dp = dp

    # Настройка команд
    await setup_commands(bot)

    # Запуск фоновых задач
    asyncio.create_task(monitor_payments(bot))
    log.info("Фоновый мониторинг платежей запущен")

    # Запуск polling
    log.info("Начинаю polling...")
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        log.info("Бот остановлен пользователем")
    except Exception as e:
        log.error(f"Критическая ошибка: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Программа завершена")
