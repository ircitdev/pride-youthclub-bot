"""Сервис для работы с бонусами и реферальной системой."""
import asyncio
from bot.config import log
from bot.services.sheets import WS_USERS, WS_BONUSES
from bot.services.utils import now


def update_bonuses(ref_id: str, bonus: int) -> None:
    """
    Обновляет бонусный баланс реферера в таблице Bonuses.

    Args:
        ref_id: Идентификатор реферера (username или user_id)
        bonus: Сумма бонусов для начисления

    Raises:
        Exception: При ошибках обновления Google Sheets

    Example:
        >>> update_bonuses("john_doe", 500)
    """
    try:
        rows = WS_BONUSES.get_all_records()
        found = False

        for idx, r in enumerate(rows, start=2):
            if str(r.get("ref_id", "")) == str(ref_id):
                total_refs = int(r.get("total_refs", 0)) + 1
                total_bonus = int(r.get("total_bonus", 0)) + bonus
                WS_BONUSES.update(f"B{idx}:D{idx}", [[total_refs, total_bonus, now()]])
                found = True
                log.info(f"Обновлены бонусы для {ref_id}: +{bonus} (всего: {total_bonus})")
                break

        if not found:
            WS_BONUSES.append_row([ref_id, 1, bonus, now()], value_input_option="USER_ENTERED")
            log.info(f"Создана новая запись бонусов для {ref_id}: {bonus}")

    except Exception as e:
        log.error(f"Ошибка обновления бонусов для {ref_id}: {e}")
        raise


def count_user_total_bonus(user_id: int) -> int:
    """
    Подсчитывает общую сумму бонусов пользователя.

    Args:
        user_id: Telegram ID пользователя

    Returns:
        int: Общая сумма бонусов

    Example:
        >>> count_user_total_bonus(123456789)
        1250
    """
    try:
        rows = WS_USERS.get_all_records()
        total = 0

        for r in rows:
            if str(r.get("user_id")) == str(user_id):
                total += int(r.get("bonus", 0))

        return total

    except Exception as e:
        log.error(f"Ошибка подсчета бонусов для {user_id}: {e}")
        return 0


def append_user_event(user, ref_source: str, action: str, obj: str, bonus: int, bot=None) -> None:
    """
    Логирует событие пользователя в таблицу Users.

    Args:
        user: Объект пользователя Telegram (aiogram.types.User)
        ref_source: Источник реферала или "direct"
        action: Тип действия (started, subscribed, ref_bonus)
        obj: Объект действия (bot, channel, group, payment)
        bonus: Количество начисленных бонусов
        bot: Объект бота для отправки уведомлений (опционально)

    Example:
        >>> append_user_event(user, "john_doe", "subscribed", "channel", 10, bot)
    """
    try:
        WS_USERS.append_row([
            now(),
            user.id,
            user.username or "",
            user.full_name,
            ref_source or "",
            action,
            obj,
            bonus
        ], value_input_option="USER_ENTERED")

        log.info(f"Событие: {action} | User: {user.id} | Ref: {ref_source} | Bonus: {bonus}")

        # Обновляем общую таблицу бонусов
        if ref_source and ref_source != "direct" and bonus > 0:
            update_bonuses(ref_source, bonus)

        # Уведомляем пользователя о начислении бонусов
        if bonus > 0 and bot:
            total_bonus = count_user_total_bonus(user.id)
            asyncio.create_task(
                bot.send_message(
                    user.id,
                    f"💎 Тебе начислено <b>+{bonus}</b> за {obj}!\n"
                    f"📊 Текущий баланс: {total_bonus} бонусов."
                )
            )

    except Exception as e:
        log.error(f"Ошибка записи события для {user.id}: {e}")
        raise


def get_user_id_by_ref(ref_source: str) -> tuple[str | None, str | None]:
    """
    Находит user_id и username реферала по идентификатору.

    Args:
        ref_source: Идентификатор реферала (username или числовой id)

    Returns:
        tuple: (user_id, username) или (None, None) если не найден

    Example:
        >>> get_user_id_by_ref("john_doe")
        ('123456789', 'john_doe')
    """
    try:
        rows = WS_USERS.get_all_records()

        # Ищем с конца, т.к. последние записи актуальнее
        for r in reversed(rows):
            if str(r.get("username") or "") == ref_source:
                return str(r.get("user_id")), r.get("username") or ""
            if str(r.get("user_id") or "") == ref_source:
                return str(r.get("user_id")), r.get("username") or ""

        return None, None

    except Exception as e:
        log.error(f"Ошибка поиска реферала {ref_source}: {e}")
        return None, None


def log_referrer_bonus(ref_user_id: str, ref_username: str, bonus: int, reason: str) -> None:
    """
    Записывает начисление бонуса рефералу в таблицу Users.

    Args:
        ref_user_id: ID реферала
        ref_username: Username реферала
        bonus: Сумма бонусов
        reason: Причина начисления

    Example:
        >>> log_referrer_bonus("123", "john", 247, "Комиссия 25% от оплаты 1 месяц")
    """
    try:
        WS_USERS.append_row([
            now(),
            ref_user_id,
            ref_username or "",
            "",  # full_name неизвестно
            "system",
            "ref_bonus",
            reason,
            bonus
        ], value_input_option="USER_ENTERED")

        log.info(f"Начислен бонус рефералу {ref_user_id}: {bonus} за '{reason}'")

    except Exception as e:
        log.error(f"Ошибка записи бонуса рефералу {ref_user_id}: {e}")
        raise
