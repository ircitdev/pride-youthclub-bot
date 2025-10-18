"""Сервис для работы с платежами."""
from bot.config import log
from bot.services.sheets import WS_PAYMENTS
from bot.services.utils import now


def log_payment(user, tariff: str, price: int, period: str, ref_source: str, status: str = "success") -> None:
    """
    Записывает информацию о платеже в таблицу Payments.

    Args:
        user: Объект пользователя Telegram (aiogram.types.User)
        tariff: Название тарифа
        price: Стоимость в рублях
        period: Период подписки
        ref_source: Источник реферала или пустая строка
        status: Статус платежа (по умолчанию "success")

    Example:
        >>> log_payment(user, "1 месяц", 990, "1", "john_doe", "success")
    """
    try:
        WS_PAYMENTS.append_row([
            now(),
            user.id,
            user.username or "",
            user.full_name,
            tariff,
            price,
            period,
            status,
            ref_source or "",
            "yes"  # notified - помечаем сразу как уведомленное
        ], value_input_option="USER_ENTERED")

        log.info(f"Платеж записан: {user.id} | {tariff} | {price}₽ | Ref: {ref_source}")

    except Exception as e:
        log.error(f"Ошибка записи платежа для {user.id}: {e}")
        raise
