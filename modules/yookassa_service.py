"""
Сервис для работы с YooKassa (ЮKassa) API
Создание платежей и обработка подтверждений
"""

import uuid
import logging
from yookassa import Configuration, Payment

logger = logging.getLogger(__name__)


class YooKassaService:
    """Сервис для интеграции с YooKassa"""

    def __init__(self, shop_id: str, secret_key: str):
        """
        Инициализация YooKassa

        Args:
            shop_id: ID магазина
            secret_key: Секретный ключ
        """
        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key
        logger.info(f"YooKassa initialized with shop_id: {shop_id}")

    def create_payment(
        self,
        amount: float,
        description: str,
        user_id: int,
        period: str,
        return_url: str = "https://t.me/PRIDEyouthClub_bot"
    ) -> dict:
        """
        Создание платежа в YooKassa

        Args:
            amount: Сумма платежа в рублях
            description: Описание платежа
            user_id: Telegram ID пользователя
            period: Период подписки (1, 3, 12)
            return_url: URL для возврата после оплаты

        Returns:
            dict: {"payment_id": str, "confirmation_url": str, "status": str}
        """
        try:
            idempotence_key = str(uuid.uuid4())

            payment = Payment.create({
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "user_id": str(user_id),
                    "period": period
                }
            }, idempotence_key)

            logger.info(f"Payment created: {payment.id} for user {user_id}, amount {amount}")

            return {
                "payment_id": payment.id,
                "confirmation_url": payment.confirmation.confirmation_url,
                "status": payment.status
            }

        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise

    def check_payment(self, payment_id: str) -> dict:
        """
        Проверка статуса платежа

        Args:
            payment_id: ID платежа в YooKassa

        Returns:
            dict: {"status": str, "paid": bool, "amount": float, "metadata": dict}
        """
        try:
            payment = Payment.find_one(payment_id)

            return {
                "status": payment.status,
                "paid": payment.paid,
                "amount": float(payment.amount.value),
                "metadata": payment.metadata
            }

        except Exception as e:
            logger.error(f"Error checking payment {payment_id}: {e}")
            raise

    def get_payment_info(self, payment_id: str) -> Payment:
        """
        Получение полной информации о платеже

        Args:
            payment_id: ID платежа

        Returns:
            Payment: Объект платежа YooKassa
        """
        return Payment.find_one(payment_id)
