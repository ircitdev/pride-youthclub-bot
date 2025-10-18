"""Клавиатуры для бота."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu() -> InlineKeyboardMarkup:
    """
    Возвращает главное меню бота.

    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Перейти в канал",
            url="https://t.me/PRIDEyouthClubChannel"
        )],
        [InlineKeyboardButton(
            text="🔒 Закрытая группа",
            callback_data="closed_group"
        )],
        [InlineKeyboardButton(
            text="🤝 Позвать подруг",
            callback_data="invitebtn"
        )],
        [InlineKeyboardButton(
            text="👩‍🏫 О тренерах",
            callback_data="trainers"
        )],
    ])


def get_trainers_menu() -> InlineKeyboardMarkup:
    """
    Возвращает меню выбора тренера.

    Returns:
        InlineKeyboardMarkup: Клавиатура с тренерами
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Мария Букина",
            callback_data="trainer_bukina"
        )],
    ])


def get_tariffs_menu() -> InlineKeyboardMarkup:
    """
    Возвращает меню тарифов для закрытой группы.

    Returns:
        InlineKeyboardMarkup: Клавиатура с тарифами
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="1 месяц — 990₽",
            callback_data="pay:1"
        )],
        [InlineKeyboardButton(
            text="3 месяца — 2673₽ (-10%)",
            callback_data="pay:3"
        )],
        [InlineKeyboardButton(
            text="12 месяцев — 8910₽ (-25%)",
            callback_data="pay:12"
        )],
    ])


def get_payment_button(period: str) -> InlineKeyboardMarkup:
    """
    Возвращает кнопку оплаты для выбранного тарифа.

    Args:
        period: Период подписки ('1', '3', '12')

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой оплаты
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Оплатить через ЮKassa",
            callback_data=f"success:{period}"
        )]
    ])
