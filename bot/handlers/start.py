"""Обработчики команды /start и начального взаимодействия."""
import os
from aiogram import F, types
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramAPIError

from bot.config import log
from bot.keyboards import get_main_menu
from bot.services.bonuses import append_user_event


async def start_handler(message: Message, bot) -> None:
    """
    Обработчик команды /start.

    Args:
        message: Сообщение от пользователя
        bot: Объект бота
    """
    payload = message.text.split(maxsplit=1)
    ref = payload[1].strip() if len(payload) > 1 else None

    # Фиксируем старт по реферальной ссылке
    if ref:
        try:
            append_user_event(message.from_user, ref, "started", "bot", 0, bot)
        except Exception as e:
            log.error(f"Ошибка записи события старта: {e}")

    # Отправка PDF
    try:
        pdf_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "youthsecret.pdf"
        )
        if os.path.exists(pdf_path):
            file = FSInputFile(pdf_path, filename="youthsecret.pdf")
            await message.answer_document(
                file,
                caption="Диагностика морфотипа лица"
            )
        else:
            log.warning(f"PDF файл не найден: {pdf_path}")

    except TelegramAPIError as e:
        log.error(f"Telegram API ошибка при отправке PDF: {e}")
    except FileNotFoundError:
        log.error("PDF файл youthsecret.pdf не найден")
    except Exception as e:
        log.error(f"Неожиданная ошибка при отправке PDF: {e}")

    # Главное меню
    await message.answer(
        "Подпишись на канал и оформи доступ в закрытую группу 👇",
        reply_markup=get_main_menu()
    )


def register_start_handlers(dp, bot):
    """
    Регистрирует обработчики для команды /start.

    Args:
        dp: Dispatcher
        bot: Объект бота
    """
    @dp.message(CommandStart())
    async def start(m: Message):
        await start_handler(m, bot)
