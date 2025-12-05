"""
Модуль закрытого клуба с:
- SQLite база данных для хранения подписок
- Интеграция ЮКасса для автоматической оплаты
- Контроль доступа к закрытому чату
- Напоминания об истечении подписки
- Автоматическое удаление из чата при окончании подписки
- Уведомления в админ-топик и запись в Google Sheets
"""

import os
import sqlite3
import logging
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yookassa import Configuration, Payment
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("club")

# ===== Настройки =====
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID_CLUB") or os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY_CLUB") or os.getenv("YOOKASSA_SECRET_KEY")
CLOSED_GROUP_ID = int(os.getenv("CLOSED_GROUP_ID", "0"))
CLOSED_CHAT_LINK = os.getenv("CLOSED_CHAT_LINK", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_THREAD_ID = int(os.getenv("ADMIN_THREAD_ID", "0"))
SERVICE_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("SERVICE_JSON_PATH")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
DB_PATH = os.getenv("CLUB_DB_PATH", "club.db")

# Настраиваем YooKassa
if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY


# ===== Google Sheets =====
def get_sheets_connection():
    """Получить подключение к Google Sheets"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(SERVICE_JSON_PATH, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID)


def get_club_worksheet():
    """Получить лист ClubPayments для записи платежей"""
    try:
        sh = get_sheets_connection()

        # Ищем или создаём лист ClubPayments
        worksheet_list = [ws.title for ws in sh.worksheets()]
        if "ClubPayments" not in worksheet_list:
            ws = sh.add_worksheet("ClubPayments", rows=1000, cols=14)
            ws.update("A1:N1", [[
                "timestamp", "user_id", "username", "full_name",
                "tariff", "price", "payment_id", "status",
                "start_date", "end_date", "payment_method", "ref_source",
                "referrer_bonus", "notified"
            ]])
        else:
            ws = sh.worksheet("ClubPayments")
        return ws
    except Exception as e:
        log.error(f"Ошибка подключения к Google Sheets: {e}")
        return None


def get_users_worksheet():
    """Получить лист Users для поиска ref_source"""
    try:
        sh = get_sheets_connection()
        return sh.worksheet("Users")
    except Exception as e:
        log.error(f"Ошибка получения листа Users: {e}")
        return None


def get_referrals_worksheet():
    """Получить лист Referrals для записи бонусов"""
    try:
        sh = get_sheets_connection()
        return sh.worksheet("Referrals")
    except Exception as e:
        log.error(f"Ошибка получения листа Referrals: {e}")
        return None


def get_bonuses_worksheet():
    """Получить лист Bonuses для обновления общих бонусов"""
    try:
        sh = get_sheets_connection()
        return sh.worksheet("Bonuses")
    except Exception as e:
        log.error(f"Ошибка получения листа Bonuses: {e}")
        return None


def find_user_ref_source(user_id: int) -> str:
    """Найти ref_source (метку) по которой пришел пользователь"""
    try:
        ws = get_users_worksheet()
        if not ws:
            return ""

        rows = ws.get_all_records()
        for r in reversed(rows):
            if str(r.get("user_id")) == str(user_id):
                ref = r.get("ref_source") or ""
                if ref and ref != "direct":
                    return ref
        return ""
    except Exception as e:
        log.error(f"Ошибка поиска ref_source: {e}")
        return ""


def get_user_id_by_ref(ref_source: str):
    """Получить user_id и username реферера по ref_source"""
    try:
        ws = get_users_worksheet()
        if not ws:
            return None, None

        rows = ws.get_all_records()
        for r in reversed(rows):
            username = str(r.get("username") or "")
            uid = str(r.get("user_id") or "")

            if username == ref_source or uid == ref_source:
                return uid, username
        return None, None
    except Exception as e:
        log.error(f"Ошибка получения user_id по ref: {e}")
        return None, None


def update_bonuses(ref_source: str, bonus: int):
    """Обновить общие бонусы реферера в листе Bonuses"""
    try:
        ws = get_bonuses_worksheet()
        if not ws:
            return

        rows = ws.get_all_records()
        for idx, r in enumerate(rows, start=2):
            if str(r.get("ref_id")) == str(ref_source):
                total_refs = int(r.get("total_refs", 0)) + 1
                total_bonus = int(r.get("total_bonus", 0)) + bonus
                ws.update(f"B{idx}:D{idx}", [[
                    total_refs,
                    total_bonus,
                    datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                ]])
                return

        # Если не найден - добавляем новую строку
        ws.append_row([
            ref_source,
            1,
            bonus,
            datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        ], value_input_option="USER_ENTERED")
    except Exception as e:
        log.error(f"Ошибка обновления Bonuses: {e}")


def log_referral_bonus(ref_source: str, ref_username: str, user_id: int,
                       username: str, purchase_type: str, amount: int, bonus: int):
    """Записать реферальный бонус в лист Referrals"""
    try:
        ws = get_referrals_worksheet()
        if ws:
            ws.append_row([
                datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                ref_source,
                ref_username,
                user_id,
                username,
                purchase_type,
                amount,
                bonus
            ], value_input_option="USER_ENTERED")
    except Exception as e:
        log.error(f"Ошибка записи в Referrals: {e}")


def log_club_payment_to_sheets(user_id: int, username: str, full_name: str,
                                tariff: str, price: int, payment_id: str,
                                status: str, start_date: str, end_date: str,
                                payment_method: str = "yookassa",
                                ref_source: str = "", referrer_bonus: int = 0):
    """Записать платеж в Google Sheets"""
    try:
        ws = get_club_worksheet()
        if ws:
            ws.append_row([
                datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                user_id,
                username,
                full_name,
                tariff,
                price,
                payment_id,
                status,
                start_date,
                end_date,
                payment_method,
                ref_source,
                referrer_bonus,
                "yes"
            ], value_input_option="USER_ENTERED")
            log.info(f"Платеж {payment_id} записан в Google Sheets")
    except Exception as e:
        log.error(f"Ошибка записи в Google Sheets: {e}")


async def notify_admin_topic(bot: Bot, text: str):
    """Отправить уведомление в топик админ-чата"""
    try:
        if ADMIN_THREAD_ID:
            await bot.send_message(ADMIN_CHAT_ID, text, message_thread_id=ADMIN_THREAD_ID)
        else:
            await bot.send_message(ADMIN_CHAT_ID, text)
        log.info("Уведомление отправлено в админ-топик")
    except Exception as e:
        log.warning(f"Не удалось отправить в админ-топик: {e}")


async def process_referral_bonus(bot: Bot, user_id: int, username: str,
                                  purchase_type: str, amount: int):
    """
    Обработать реферальный бонус при оплате.
    - Найти по чьей ссылке пришел пользователь
    - Начислить 25% от суммы
    - Записать в Referrals и Bonuses
    - Уведомить реферера
    """
    # Находим метку пользователя
    ref_source = find_user_ref_source(user_id)
    if not ref_source:
        log.info(f"Пользователь {user_id} пришёл без реферала (direct)")
        return "", 0

    # Вычисляем бонус 25%
    bonus = int(amount * 0.25)

    # Получаем данные реферера
    referrer_id, referrer_username = get_user_id_by_ref(ref_source)

    # Записываем в лист Referrals
    log_referral_bonus(
        ref_source=ref_source,
        ref_username=referrer_username or "",
        user_id=user_id,
        username=username,
        purchase_type=purchase_type,
        amount=amount,
        bonus=bonus
    )

    # Обновляем общие бонусы в Bonuses
    update_bonuses(ref_source, bonus)

    # Уведомляем реферера если известен его user_id
    if referrer_id and str(referrer_id).isdigit():
        try:
            await bot.send_message(
                int(referrer_id),
                f"🎉 <b>Новая оплата по вашей ссылке!</b>\n\n"
                f"👤 Пользователь оформил: <b>{purchase_type}</b>\n"
                f"💵 Сумма покупки: <b>{amount}₽</b>\n"
                f"💰 Ваш бонус (25%): <b>{bonus}₽</b>\n\n"
                f"Спасибо, что приглашаете друзей! 💚"
            )
            log.info(f"Реферер {referrer_id} уведомлен о платеже {amount}₽ и бонусе {bonus}₽")
        except Exception as e:
            log.warning(f"Не удалось уведомить реферера {referrer_id}: {e}")

    return ref_source, bonus


# ===== Тарифы закрытого клуба =====
CLUB_TARIFFS = {
    "1m": {"label": "1 месяц", "days": 30, "price": 990},
    "3m": {"label": "3 месяца", "days": 90, "price": 2490},
    "6m": {"label": "6 месяцев", "days": 180, "price": 4490},
    "12m": {"label": "12 месяцев", "days": 365, "price": 7990},
}


# ===== SQLite База данных =====
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица подписок
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            tariff TEXT NOT NULL,
            price INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            payment_id TEXT,
            status TEXT DEFAULT 'pending',
            start_date TEXT,
            end_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TEXT,
            reminded_3d INTEGER DEFAULT 0,
            reminded_1d INTEGER DEFAULT 0,
            reminded_expired INTEGER DEFAULT 0
        )
    """)

    # Таблица платежей (история)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            payment_id TEXT UNIQUE,
            amount INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TEXT,
            tariff TEXT,
            method TEXT
        )
    """)

    # Таблица напоминаний
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reminder_type TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    log.info("База данных club.db инициализирована")


def get_db():
    """Получить подключение к БД"""
    return sqlite3.connect(DB_PATH)


def add_subscription(user_id: int, username: str, full_name: str,
                     tariff: str, price: int, payment_method: str,
                     payment_id: str = None, status: str = "pending") -> int:
    """Добавить новую подписку"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO subscriptions
        (user_id, username, full_name, tariff, price, payment_method, payment_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, full_name, tariff, price, payment_method, payment_id, status,
          datetime.now(timezone.utc).isoformat()))
    sub_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sub_id


def confirm_subscription(sub_id: int, days: int) -> bool:
    """Подтвердить подписку и установить даты"""
    conn = get_db()
    cursor = conn.cursor()

    start_date = datetime.now(timezone.utc).date()
    end_date = start_date + timedelta(days=days)

    cursor.execute("""
        UPDATE subscriptions
        SET status = 'active',
            start_date = ?,
            end_date = ?,
            confirmed_at = ?
        WHERE id = ?
    """, (str(start_date), str(end_date), datetime.now(timezone.utc).isoformat(), sub_id))

    conn.commit()
    conn.close()
    return True


def get_active_subscription(user_id: int) -> Optional[dict]:
    """Получить активную подписку пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, username, full_name, tariff, price,
               start_date, end_date, status
        FROM subscriptions
        WHERE user_id = ? AND status = 'active' AND end_date >= date('now')
        ORDER BY end_date DESC LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "user_id": row[1],
            "username": row[2],
            "full_name": row[3],
            "tariff": row[4],
            "price": row[5],
            "start_date": row[6],
            "end_date": row[7],
            "status": row[8]
        }
    return None


def get_subscription_by_id(sub_id: int) -> Optional[dict]:
    """Получить подписку по ID"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, username, full_name, tariff, price,
               start_date, end_date, status, payment_method
        FROM subscriptions WHERE id = ?
    """, (sub_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "user_id": row[1],
            "username": row[2],
            "full_name": row[3],
            "tariff": row[4],
            "price": row[5],
            "start_date": row[6],
            "end_date": row[7],
            "status": row[8],
            "payment_method": row[9]
        }
    return None


def get_expiring_subscriptions(days: int) -> List[dict]:
    """Получить подписки, истекающие через N дней"""
    conn = get_db()
    cursor = conn.cursor()
    target_date = (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT id, user_id, username, full_name, tariff, end_date
        FROM subscriptions
        WHERE status = 'active' AND end_date = ?
    """, (target_date,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "user_id": row[1],
            "username": row[2],
            "full_name": row[3],
            "tariff": row[4],
            "end_date": row[5]
        }
        for row in rows
    ]


def get_expired_subscriptions() -> List[dict]:
    """Получить истекшие подписки"""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now(timezone.utc).date().isoformat()

    cursor.execute("""
        SELECT id, user_id, username, full_name, tariff, end_date
        FROM subscriptions
        WHERE status = 'active' AND end_date < ?
    """, (today,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "user_id": row[1],
            "username": row[2],
            "full_name": row[3],
            "tariff": row[4],
            "end_date": row[5]
        }
        for row in rows
    ]


def mark_subscription_expired(sub_id: int):
    """Пометить подписку как истекшую"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE subscriptions SET status = 'expired' WHERE id = ?
    """, (sub_id,))
    conn.commit()
    conn.close()


def mark_reminder_sent(sub_id: int, reminder_type: str):
    """Пометить, что напоминание отправлено"""
    conn = get_db()
    cursor = conn.cursor()

    if reminder_type == "3d":
        cursor.execute("UPDATE subscriptions SET reminded_3d = 1 WHERE id = ?", (sub_id,))
    elif reminder_type == "1d":
        cursor.execute("UPDATE subscriptions SET reminded_1d = 1 WHERE id = ?", (sub_id,))
    elif reminder_type == "expired":
        cursor.execute("UPDATE subscriptions SET reminded_expired = 1 WHERE id = ?", (sub_id,))

    conn.commit()
    conn.close()


def get_pending_reminders(days: int, reminder_type: str) -> List[dict]:
    """Получить подписки для отправки напоминаний"""
    conn = get_db()
    cursor = conn.cursor()

    if reminder_type == "3d":
        target_date = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
        query = """
            SELECT id, user_id, username, full_name, tariff, end_date
            FROM subscriptions
            WHERE status = 'active' AND end_date = ? AND reminded_3d = 0
        """
    elif reminder_type == "1d":
        target_date = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        query = """
            SELECT id, user_id, username, full_name, tariff, end_date
            FROM subscriptions
            WHERE status = 'active' AND end_date = ? AND reminded_1d = 0
        """
    else:
        conn.close()
        return []

    cursor.execute(query, (target_date,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "user_id": row[1],
            "username": row[2],
            "full_name": row[3],
            "tariff": row[4],
            "end_date": row[5]
        }
        for row in rows
    ]


def log_payment(user_id: int, payment_id: str, amount: int,
                tariff: str, method: str, status: str = "pending"):
    """Логируем платеж"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO payments (user_id, payment_id, amount, tariff, method, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, payment_id, amount, tariff, method, status,
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def update_payment_status(payment_id: str, status: str):
    """Обновить статус платежа"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE payments SET status = ?, confirmed_at = ? WHERE payment_id = ?
    """, (status, datetime.now(timezone.utc).isoformat() if status == "succeeded" else None,
          payment_id))
    conn.commit()
    conn.close()


# Инициализируем БД при импорте
init_db()


# ===== FSM =====
class ClubFSM(StatesGroup):
    choosing_tariff = State()
    choosing_payment = State()
    waiting_payment = State()


# ===== Функции бота =====
async def show_club_menu(bot: Bot, message: types.Message, state: FSMContext):
    """Главное меню закрытого клуба"""
    user = message.from_user

    # Проверяем активную подписку
    active_sub = get_active_subscription(user.id)

    if active_sub:
        end_date = datetime.strptime(active_sub["end_date"], "%Y-%m-%d").date()
        days_left = (end_date - datetime.now().date()).days

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Перейти в закрытый клуб", url=CLOSED_CHAT_LINK)],
            [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="club_extend")],
            [InlineKeyboardButton(text="📊 Моя подписка", callback_data="club_my_sub")]
        ])

        await message.answer(
            f"🏆 <b>Добро пожаловать в Закрытый Клуб!</b>\n\n"
            f"✅ У вас активная подписка: <b>{active_sub['tariff']}</b>\n"
            f"📅 Действует до: <b>{end_date.strftime('%d.%m.%Y')}</b>\n"
            f"⏳ Осталось дней: <b>{days_left}</b>\n\n"
            f"Нажмите кнопку ниже, чтобы перейти в закрытый клуб 👇",
            reply_markup=kb
        )
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Вступить в клуб", callback_data="club_join")],
            [InlineKeyboardButton(text="❓ Что такое клуб?", callback_data="club_about")]
        ])

        await message.answer(
            "🏆 <b>Закрытый Клуб Омоложения ПРАЙД</b>\n\n"
            "Здесь вы получаете:\n"
            "✨ Эксклюзивные тренировки каждую неделю\n"
            "✨ Личные консультации от Марии Букиной\n"
            "✨ Закрытый чат с единомышленницами\n"
            "✨ Дополнительные материалы и бонусы\n\n"
            "Вступайте в клуб и начните путь к молодости! 💫",
            reply_markup=kb
        )

    await state.clear()


async def show_tariffs(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Показать тарифы"""
    buttons = []
    for key, tariff in CLUB_TARIFFS.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{tariff['label']} — {tariff['price']}₽",
                callback_data=f"club_tariff:{key}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="club_back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await call.message.edit_text(
        "💎 <b>Выберите тариф:</b>\n\n"
        "🥉 <b>1 месяц</b> — 990₽\n"
        "🥈 <b>3 месяца</b> — 2490₽ (экономия 480₽)\n"
        "🥇 <b>6 месяцев</b> — 4490₽ (экономия 1450₽)\n"
        "👑 <b>12 месяцев</b> — 7990₽ (экономия 3890₽)\n\n"
        "Выберите подходящий тариф 👇",
        reply_markup=kb
    )
    await call.answer()


async def choose_tariff(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Выбор тарифа"""
    tariff_key = call.data.split(":")[1]
    tariff = CLUB_TARIFFS.get(tariff_key)

    if not tariff:
        await call.answer("Ошибка тарифа", show_alert=True)
        return

    await state.update_data(tariff_key=tariff_key, tariff=tariff)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить картой", callback_data=f"club_yookassa:{tariff_key}")],
        [InlineKeyboardButton(text="🔙 Назад к тарифам", callback_data="club_join")]
    ])

    await call.message.edit_text(
        f"💎 Вы выбрали: <b>{tariff['label']}</b>\n"
        f"💰 Стоимость: <b>{tariff['price']}₽</b>\n\n"
        f"Нажмите «Оплатить картой» для перехода к оплате 👇",
        reply_markup=kb
    )
    await call.answer()


async def pay_yookassa(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Оплата через YooKassa"""
    tariff_key = call.data.split(":")[1]
    tariff = CLUB_TARIFFS.get(tariff_key)
    user = call.from_user

    if not tariff:
        await call.answer("Ошибка тарифа", show_alert=True)
        return

    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY):
        await call.message.answer("❌ Оплата через YooKassa временно недоступна.")
        await call.answer()
        return

    try:
        # Создаем подписку в БД
        sub_id = add_subscription(
            user_id=user.id,
            username=user.username or "",
            full_name=user.full_name,
            tariff=tariff["label"],
            price=tariff["price"],
            payment_method="yookassa"
        )

        # Создаем платеж в YooKassa
        payment = Payment.create(
            {
                "amount": {"value": f"{tariff['price']:.2f}", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": "https://t.me/PRIDEyouthClub_bot"},
                "capture": True,
                "description": f"Закрытый клуб: {tariff['label']}",
                "metadata": {
                    "user_id": user.id,
                    "sub_id": sub_id,
                    "tariff_key": tariff_key,
                    "tariff_label": tariff["label"],
                    "days": tariff["days"],
                },
            },
            uuid.uuid4().hex,
        )

        # Сохраняем payment_id
        log_payment(user.id, payment.id, tariff["price"], tariff_key, "yookassa")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment.confirmation.confirmation_url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"club_check:{payment.id}:{tariff_key}:{sub_id}")]
        ])

        await call.message.edit_text(
            f"💳 <b>Оплата подписки</b>\n\n"
            f"📦 Тариф: {tariff['label']}\n"
            f"💰 Сумма: {tariff['price']}₽\n\n"
            f"Нажмите кнопку для перехода к оплате.\n"
            f"После оплаты нажмите «Проверить оплату» 👇",
            reply_markup=kb
        )
        await call.answer()

    except Exception as e:
        log.error(f"YooKassa create error: {e}")
        await call.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        await call.answer()


async def check_payment(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Проверка оплаты YooKassa"""
    parts = call.data.split(":")
    payment_id = parts[1]
    tariff_key = parts[2]
    sub_id = int(parts[3])

    tariff = CLUB_TARIFFS.get(tariff_key)
    if not tariff:
        await call.answer("Ошибка тарифа", show_alert=True)
        return

    user = call.from_user

    try:
        payment = Payment.find_one(payment_id)

        if payment.status == "succeeded":
            # Подтверждаем подписку
            confirm_subscription(sub_id, tariff["days"])
            update_payment_status(payment_id, "succeeded")

            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=tariff["days"])
            end_date_str = end_date.strftime("%d.%m.%Y")

            # Обрабатываем реферальный бонус
            ref_source, referrer_bonus = await process_referral_bonus(
                bot=bot,
                user_id=user.id,
                username=user.username or "",
                purchase_type=f"Закрытый клуб: {tariff['label']}",
                amount=tariff["price"]
            )

            # Сообщение пользователю
            await call.message.edit_text(
                f"🎉 <b>Оплата успешно прошла!</b>\n\n"
                f"✅ Тариф: {tariff['label']}\n"
                f"📅 Действует до: {end_date_str}\n\n"
                f"Добро пожаловать в Закрытый Клуб! 💚",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Перейти в клуб", url=CLOSED_CHAT_LINK)]
                ])
            )

            # Записываем в Google Sheets (с ref_source и бонусом)
            log_club_payment_to_sheets(
                user_id=user.id,
                username=user.username or "",
                full_name=user.full_name,
                tariff=tariff["label"],
                price=tariff["price"],
                payment_id=payment_id,
                status="succeeded",
                start_date=str(start_date),
                end_date=str(end_date),
                payment_method="yookassa",
                ref_source=ref_source,
                referrer_bonus=referrer_bonus
            )

            # Формируем текст уведомления с информацией о реферале
            admin_text = (
                f"💳 <b>Новая оплата Закрытого Клуба</b>\n\n"
                f"👤 {user.full_name} (@{user.username or user.id})\n"
                f"📦 Тариф: {tariff['label']}\n"
                f"💰 Сумма: {tariff['price']}₽\n"
                f"📅 До: {end_date_str}\n"
                f"🆔 Платеж: <code>{payment_id}</code>"
            )
            if ref_source:
                admin_text += f"\n\n👥 Реферал: <code>{ref_source}</code>\n💎 Бонус рефереру: {referrer_bonus}₽"

            # Уведомление в топик админ-чата
            await notify_admin_topic(bot, admin_text)

            await call.answer("✅ Оплата подтверждена!")
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Проверить еще раз", callback_data=f"club_check:{payment_id}:{tariff_key}:{sub_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="club_back")]
            ])
            await call.message.edit_text(
                f"⏳ <b>Оплата еще не поступила</b>\n\n"
                f"Статус: {payment.status}\n\n"
                f"Подождите пару минут и попробуйте снова.",
                reply_markup=kb
            )
            await call.answer("Оплата не найдена")

    except Exception as e:
        log.error(f"Check payment error: {e}")
        await call.answer("Ошибка проверки платежа", show_alert=True)


async def show_my_subscription(bot: Bot, call: types.CallbackQuery):
    """Показать информацию о подписке"""
    user = call.from_user
    sub = get_active_subscription(user.id)

    if sub:
        end_date = datetime.strptime(sub["end_date"], "%Y-%m-%d").date()
        days_left = (end_date - datetime.now().date()).days

        await call.message.edit_text(
            f"📊 <b>Ваша подписка</b>\n\n"
            f"📦 Тариф: {sub['tariff']}\n"
            f"📅 Начало: {sub['start_date']}\n"
            f"📅 Окончание: {end_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Осталось: {days_left} дней\n\n"
            f"Статус: ✅ Активна",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Продлить", callback_data="club_join")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="club_back")]
            ])
        )
    else:
        await call.message.edit_text(
            "❌ У вас нет активной подписки.\n\n"
            "Оформите подписку, чтобы получить доступ к закрытому клубу!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Оформить подписку", callback_data="club_join")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="club_back")]
            ])
        )

    await call.answer()


async def about_club(bot: Bot, call: types.CallbackQuery):
    """Информация о клубе"""
    await call.message.edit_text(
        "🏆 <b>О Закрытом Клубе Омоложения ПРАЙД</b>\n\n"
        "Это эксклюзивное сообщество для тех, кто хочет выглядеть моложе "
        "без уколов и пластики.\n\n"
        "<b>Что вы получите:</b>\n"
        "✨ Еженедельные тренировки в записи\n"
        "✨ Живые эфиры с Марией Букиной\n"
        "✨ Персональную поддержку и ответы на вопросы\n"
        "✨ Закрытый чат единомышленниц\n"
        "✨ Бонусные материалы и техники\n"
        "✨ Мотивацию и поддержку группы\n\n"
        "Присоединяйтесь к нам и начните путь к естественной молодости! 💫",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Вступить в клуб", callback_data="club_join")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="club_back")]
        ])
    )
    await call.answer()


# ===== Фоновые задачи =====
async def check_subscriptions_task(bot: Bot):
    """Фоновая задача для проверки подписок"""
    while True:
        try:
            # Напоминания за 3 дня
            subs_3d = get_pending_reminders(3, "3d")
            for sub in subs_3d:
                try:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="club_join")]
                    ])
                    await bot.send_message(
                        sub["user_id"],
                        f"⏰ <b>Напоминание</b>\n\n"
                        f"Ваша подписка на закрытый клуб истекает через 3 дня.\n"
                        f"📅 Дата окончания: {sub['end_date']}\n\n"
                        f"Продлите подписку, чтобы не потерять доступ!",
                        reply_markup=kb
                    )
                    mark_reminder_sent(sub["id"], "3d")
                except Exception as e:
                    log.warning(f"Ошибка отправки напоминания 3d: {e}")

            # Напоминания за 1 день
            subs_1d = get_pending_reminders(1, "1d")
            for sub in subs_1d:
                try:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Продлить сейчас", callback_data="club_join")]
                    ])
                    await bot.send_message(
                        sub["user_id"],
                        f"⚠️ <b>Срочно!</b>\n\n"
                        f"Ваша подписка истекает <b>завтра</b>!\n"
                        f"📅 Дата окончания: {sub['end_date']}\n\n"
                        f"Продлите сейчас, чтобы сохранить доступ к закрытому клубу.",
                        reply_markup=kb
                    )
                    mark_reminder_sent(sub["id"], "1d")
                except Exception as e:
                    log.warning(f"Ошибка отправки напоминания 1d: {e}")

            # Обработка истекших подписок
            expired = get_expired_subscriptions()
            for sub in expired:
                try:
                    # Помечаем как истекшую
                    mark_subscription_expired(sub["id"])

                    # Уведомляем пользователя
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Возобновить подписку", callback_data="club_join")]
                    ])
                    await bot.send_message(
                        sub["user_id"],
                        f"❌ <b>Подписка истекла</b>\n\n"
                        f"Ваша подписка на закрытый клуб закончилась.\n"
                        f"Вы больше не можете получать новые материалы.\n\n"
                        f"Возобновите подписку, чтобы вернуться в клуб!",
                        reply_markup=kb
                    )

                    # Удаляем/ограничиваем в закрытом чате
                    if CLOSED_GROUP_ID:
                        try:
                            await bot.ban_chat_member(CLOSED_GROUP_ID, sub["user_id"])
                            await bot.unban_chat_member(CLOSED_GROUP_ID, sub["user_id"])
                            log.info(f"Пользователь {sub['user_id']} удален из закрытого чата")
                        except Exception as e:
                            log.warning(f"Не удалось удалить из чата: {e}")

                except Exception as e:
                    log.warning(f"Ошибка обработки истекшей подписки: {e}")

        except Exception as e:
            log.error(f"Ошибка в check_subscriptions_task: {e}")

        # Проверяем каждый час
        await asyncio.sleep(3600)


async def has_active_subscription(user_id: int) -> bool:
    """Проверить, есть ли активная подписка"""
    sub = get_active_subscription(user_id)
    return sub is not None
