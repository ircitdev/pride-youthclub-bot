"""Утилиты и вспомогательные функции."""
from datetime import datetime, timezone, timedelta
from bot.config import ADMINS


def now():
    """
    Возвращает текущую дату и время в ISO формате с timezone.

    Returns:
        str: Текущая дата/время в формате ISO 8601

    Example:
        >>> now()
        '2025-01-15T14:30:45+03:00'
    """
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def get_ref_id(user):
    """
    Получает идентификатор реферала из объекта пользователя.

    Args:
        user: Объект пользователя Telegram (aiogram.types.User)

    Returns:
        str: Username если есть, иначе строковое представление ID

    Example:
        >>> get_ref_id(user)
        'john_doe'  # или '123456789'
    """
    return user.username if user.username else str(user.id)


def is_admin(user):
    """
    Проверяет, является ли пользователь администратором бота.

    Args:
        user: Объект пользователя Telegram (aiogram.types.User)

    Returns:
        bool: True если пользователь админ, иначе False

    Example:
        >>> is_admin(user)
        True
    """
    return user.id in ADMINS or (user.username and user.username in ADMINS)


def fmt_cur(x: int) -> str:
    """
    Форматирует число как валюту с пробелами между разрядами.

    Args:
        x: Число для форматирования

    Returns:
        str: Отформатированная строка

    Example:
        >>> fmt_cur(1000000)
        '1 000 000'
    """
    return f"{x:,}".replace(",", " ")


def parse_period(arg: str):
    """
    Парсит строковый аргумент периода в объект date.

    Args:
        arg: Строка периода ('today', 'week', 'month')

    Returns:
        datetime.date или None: Дата начала периода или None если аргумент некорректен

    Example:
        >>> parse_period("week")
        datetime.date(2025, 1, 8)  # 7 дней назад от текущей даты
    """
    if arg == "today":
        return datetime.now().date()
    elif arg == "week":
        return datetime.now().date() - timedelta(days=7)
    elif arg == "month":
        return datetime.now().date() - timedelta(days=30)
    return None
