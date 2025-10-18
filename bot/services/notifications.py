"""Сервис для отправки уведомлений администраторам."""
import asyncio
from aiogram.exceptions import TelegramAPIError
from bot.config import ADMIN_CHAT_ID, ADMIN_THREAD_ID, log
from bot.services.sheets import WS_PAYMENTS


async def notify_admin_text(bot, text: str) -> None:
    """
    Отправляет текстовое уведомление в админ-чат.

    Args:
        bot: Объект бота Telegram
        text: Текст уведомления

    Example:
        >>> await notify_admin_text(bot, "Новый пользователь зарегистрирован")
    """
    try:
        if ADMIN_THREAD_ID:
            await bot.send_message(
                ADMIN_CHAT_ID,
                text,
                message_thread_id=ADMIN_THREAD_ID
            )
        else:
            await bot.send_message(ADMIN_CHAT_ID, text)

        log.info("Уведомление админу отправлено")

    except TelegramAPIError as e:
        log.warning(f"Telegram API ошибка при отправке в админ-чат: {e}")
    except Exception as e:
        log.error(f"Не удалось отправить в админ-чат: {e}")


async def notify_admin(bot, user, ref: str, obj: str, bonus: int) -> None:
    """
    Отправляет уведомление админу о новом подписчике.

    Args:
        bot: Объект бота Telegram
        user: Объект пользователя Telegram
        ref: Источник реферала
        obj: Объект подписки (channel, group)
        bonus: Начисленные бонусы

    Example:
        >>> await notify_admin(bot, user, "john_doe", "channel", 10)
    """
    uname = f"@{user.username}" if user.username else user.full_name
    text = (
        f"👤 Новый подписчик: {uname}\n"
        f"Реферал: {ref}\n"
        f"Подписка: {obj} (+{bonus})"
    )
    await notify_admin_text(bot, text)


async def monitor_payments(bot) -> None:
    """
    Фоновая задача мониторинга новых платежей в Google Sheets.

    Периодически проверяет таблицу Payments на наличие строк с notified != 'yes',
    отправляет уведомления и помечает строки как обработанные.

    Args:
        bot: Объект бота Telegram

    Note:
        Эта функция работает бесконечно в фоновом режиме.
    """
    log.info("Запущен мониторинг платежей")

    while True:
        try:
            values = WS_PAYMENTS.get_all_values()

            if len(values) >= 2:
                headers = values[0]
                col_map = {h: i for i, h in enumerate(headers)}
                notified_idx = col_map.get("notified")

                for row_idx in range(1, len(values)):
                    row = values[row_idx]

                    # Проверяем, требуется ли уведомление
                    if notified_idx is None or notified_idx >= len(row) or \
                       row[notified_idx].strip().lower() != "yes":

                        # Извлекаем данные из строки
                        ts = row[col_map.get("timestamp", 0)] if col_map.get("timestamp") is not None else ""
                        uname = row[col_map.get("username", 2)] if len(row) > 2 else ""
                        fulln = row[col_map.get("full_name", 3)] if len(row) > 3 else ""
                        tariff = row[col_map.get("tariff", 4)] if len(row) > 4 else ""
                        price = row[col_map.get("price", 5)] if len(row) > 5 else "0"
                        ref = row[col_map.get("ref_source", 8)] if len(row) > 8 else ""

                        buyer = f"@{uname}" if uname else fulln or "—"
                        text = (
                            f"💳 <b>Оплата (новая строка)</b>\n"
                            f"🕒 {ts}\n"
                            f"👤 {buyer}\n"
                            f"📦 {tariff}\n"
                            f"💵 {price}₽\n"
                            f"👥 Реферал: {ref or '—'}"
                        )

                        await notify_admin_text(bot, text)

                        # Помечаем как notified
                        if notified_idx is not None:
                            WS_PAYMENTS.update_cell(row_idx + 1, notified_idx + 1, "yes")
                        else:
                            # Если колонки нет - добавляем
                            WS_PAYMENTS.update("J1", [["notified"]])
                            WS_PAYMENTS.update_cell(row_idx + 1, 10, "yes")

                        log.info(f"Обработан платеж в строке {row_idx + 1}")

        except Exception as e:
            log.warning(f"Ошибка в monitor_payments: {e}")

        await asyncio.sleep(20)  # Проверка каждые 20 секунд
