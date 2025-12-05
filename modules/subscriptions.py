import os
import logging
import uuid
from datetime import datetime, timedelta, timezone

import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yookassa import Configuration, Payment
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("subscriptions")

# ===== Настройки =====
SERVICE_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("SERVICE_JSON_PATH")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CLOSED_CHAT_LINK = os.getenv("CLOSED_CHAT_LINK")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
PAY_PHONE = "+79093802552"

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY


# ===== Google Sheets =====
def subs_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(SERVICE_JSON_PATH, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    # Обновляем список листов
    sh.fetch_sheet_metadata()
    worksheet_list = [ws.title for ws in sh.worksheets()]

    if "Subscriptions" in worksheet_list:
        ws = sh.worksheet("Subscriptions")
    else:
        try:
            ws = sh.add_worksheet("Subscriptions", rows=1000, cols=11)
            ws.update(
                "A1:K1",
                [[
                    "timestamp", "user_id", "username", "full_name", "tariff", "amount",
                    "payment_method", "confirmed", "start_date", "end_date", "ref_source"
                ]]
            )
        except gspread.exceptions.APIError:
            sh.fetch_sheet_metadata()
            ws = sh.worksheet("Subscriptions")
    return ws


WS_SUBS = subs_sheets()


def log_sub(user, tariff, amount, payment_method, confirmed, start, end, ref_source=""):
    WS_SUBS.append_row([
        datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        user.id,
        user.username or "",
        user.full_name,
        tariff,
        amount,
        payment_method,
        confirmed,
        start,
        end,
        ref_source
    ], value_input_option="USER_ENTERED")


# ===== FSM =====
class SubscriptionFSM(StatesGroup):
    waiting_payment = State()
    waiting_manual_confirm = State()


# ===== Тарифы =====
TARIFFS = {
    "5w": {"label": "5 недель", "weeks": 5, "price": 2000},
    "12w": {"label": "3 месяца (12 недель)", "weeks": 12, "price": 4990},
}


# ===== Функции =====
async def show_subscribe_menu(bot: Bot, message: types.Message, state: FSMContext):
    """Главный экран"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 недель — 2000₽", callback_data="sub_tariff:5w")],
        [InlineKeyboardButton(text="3 месяца (12 недель) — 4990₽", callback_data="sub_tariff:12w")]
    ])
    await message.answer(
        "🔒 Купить абонемент на закрытую группу.\n\nВыберите тариф 👇",
        reply_markup=kb
    )
    await state.clear()


async def choose_tariff(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Выбор тарифа"""
    tariff_key = call.data.split(":")[1]
    tariff = TARIFFS.get(tariff_key)
    if not tariff:
        await call.answer("Ошибка тарифа", show_alert=True)
        return

    await state.update_data(tariff_key=tariff_key)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через YooKassa", callback_data=f"sub_yookassa:{tariff_key}")],
        [InlineKeyboardButton(text="💰 Оплатить прямым переводом", callback_data=f"sub_manual:{tariff_key}")],
        [InlineKeyboardButton(text="✅ Эмуляция оплаты (тест)", callback_data=f"sub_emulate:{tariff_key}")]
    ])
    await call.message.edit_text(
        f"Вы выбрали: <b>{tariff['label']}</b>\n"
        f"Стоимость: <b>{tariff['price']}₽</b>\n\nВыберите способ оплаты 👇",
        reply_markup=kb
    )
    await call.answer()


# ===== YooKassa =====
async def pay_yookassa(bot: Bot, call: types.CallbackQuery):
    tariff_key = call.data.split(":")[1]
    tariff = TARIFFS.get(tariff_key)
    if not tariff:
        await call.answer("Ошибка тарифа", show_alert=True)
        return

    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY):
        await call.message.answer("❌ Оплата через YooKassa временно недоступна.")
        await call.answer()
        return

    try:
        payment = Payment.create(
            {
                "amount": {"value": f"{tariff['price']:.2f}", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": "https://t.me/PRIDEyouthClub_bot"},
                "capture": True,
                "description": f"Подписка на {tariff['label']}",
                "metadata": {
                    "user_id": call.from_user.id,
                    "tariff": tariff['label'],
                    "weeks": tariff['weeks'],
                },
            },
            uuid.uuid4().hex,
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить через YooKassa", url=payment.confirmation.confirmation_url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"sub_check:{payment.id}:{tariff_key}")]
        ])
        await call.message.answer(
            f"💰 <b>{tariff['label']}</b>\nСтоимость: {tariff['price']}₽\n\nПерейдите по ссылке для оплаты:",
            reply_markup=kb
        )
        await call.answer()
    except Exception as e:
        log.error(f"YooKassa create error: {e}")
        await call.message.answer("❌ Ошибка при создании платежа.")
        await call.answer()


async def check_yookassa(bot: Bot, call: types.CallbackQuery):
    from yookassa import Payment
    _, payment_id, tariff_key = call.data.split(":")
    tariff = TARIFFS.get(tariff_key)
    if not tariff:
        await call.answer("Ошибка тарифа", show_alert=True)
        return

    payment = Payment.find_one(payment_id)
    if payment.status == "succeeded":
        user = call.from_user
        start = datetime.now().date()
        end = start + timedelta(weeks=tariff["weeks"])
        log_sub(user, tariff["label"], tariff["price"], "YooKassa", "yes", str(start), str(end))
        await call.message.answer(
            f"🎉 Оплата успешно подтверждена!\n"
            f"Ваш абонемент действует до <b>{end.strftime('%d.%m.%Y')}</b>.\n\n"
            f"Добро пожаловать в закрытую группу 💚",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔗 Перейти в группу", url=CLOSED_CHAT_LINK)]]
            )
        )
        await call.answer("✅ Оплата подтверждена.")
    else:
        await call.message.answer("⏳ Платёж пока не подтверждён. Попробуйте позже.")
        await call.answer()


# ===== Ручная оплата =====
async def manual_payment(bot: Bot, call: types.CallbackQuery):
    tariff_key = call.data.split(":")[1]
    tariff = TARIFFS.get(tariff_key)
    if not tariff:
        await call.answer("Ошибка тарифа", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data=f"sub_done:{tariff_key}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sub_back")]
    ])
    await call.message.edit_text(
        f"Переведите {tariff['price']}₽ через СБП по номеру <b>{PAY_PHONE}</b>\n"
        "и укажите ваш Telegram username в комментарии.\n\nПосле перевода нажмите «Готово».",
        reply_markup=kb
    )
    await call.answer()


async def manual_done(bot: Bot, call: types.CallbackQuery):
    tariff_key = call.data.split(":")[1]
    tariff = TARIFFS.get(tariff_key)
    user = call.from_user

    start = datetime.now().date()
    end = start + timedelta(weeks=tariff["weeks"])
    log_sub(user, tariff["label"], tariff["price"], "перевод", "ожидание", str(start), str(end))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"sub_confirm:{user.id}:{tariff_key}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"sub_reject:{user.id}:{tariff_key}")]
    ])
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"💳 Пользователь {user.full_name} оплатил {tariff['price']}₽ за {tariff['label']} прямым переводом.\nПодтвердить получение?",
        reply_markup=kb
    )
    await call.message.edit_text("💌 Ожидайте подтверждения оплаты от администратора.")
    await call.answer()


async def confirm_payment(bot: Bot, call: types.CallbackQuery):
    _, user_id, tariff_key = call.data.split(":")
    user_id = int(user_id)
    tariff = TARIFFS.get(tariff_key)

    start = datetime.now().date()
    end = start + timedelta(weeks=tariff["weeks"])
    log_sub(types.User(id=user_id, is_bot=False, first_name="?", last_name="", username=""),
            tariff["label"], tariff["price"], "перевод", "yes", str(start), str(end))

    await bot.send_message(
        user_id,
        f"✅ Оплата подтверждена!\n"
        f"Ваш абонемент действует до <b>{end.strftime('%d.%m.%Y')}</b>.\n\n"
        f"Добро пожаловать в закрытую группу 💚",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔗 Перейти в группу", url=CLOSED_CHAT_LINK)]]
        )
    )
    await call.message.edit_text(f"✅ Подтверждено: пользователь {user_id} получил доступ.")
    await call.answer()


async def reject_payment(bot: Bot, call: types.CallbackQuery):
    _, user_id, tariff_key = call.data.split(":")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверил, всё ок", callback_data=f"sub_retry:{tariff_key}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="sub_cancel")]
    ])
    await bot.send_message(user_id, "⚠️ Оплата не подтверждена. Проверьте перевод.", reply_markup=kb)
    await call.answer("Отказ отправлен пользователю.")


async def retry_payment(bot: Bot, call: types.CallbackQuery):
    tariff_key = call.data.split(":")[1]
    user = call.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"sub_confirm:{user.id}:{tariff_key}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"sub_reject:{user.id}:{tariff_key}")]
    ])
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"💳 Пользователь {user.full_name} повторно подтвердил оплату за {TARIFFS[tariff_key]['label']}. Проверить?",
        reply_markup=kb
    )
    await call.answer("Отправлено на проверку.")


# ===== Эмуляция оплаты для тестирования =====
async def emulate_payment(bot: Bot, call: types.CallbackQuery):
    """Эмуляция успешной оплаты для тестирования"""
    tariff_key = call.data.split(":")[1]
    tariff = TARIFFS.get(tariff_key)
    user = call.from_user

    start = datetime.now().date()
    end = start + timedelta(weeks=tariff["weeks"])
    log_sub(user, tariff["label"], tariff["price"], "эмуляция (тест)", "подтверждено", str(start), str(end))

    # Отправляем уведомление админу (без кнопок подтверждения)
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"🧪 [ТЕСТ] Пользователь {user.full_name} (@{user.username or user.id}) эмулировал оплату {tariff['price']}₽ за {tariff['label']}."
    )

    # Отправляем ссылку пользователю
    await call.message.edit_text(
        f"✅ Тестовая оплата успешна!\n\n"
        f"Доступ к закрытой группе:\n{CLOSED_CHAT_LINK}\n\n"
        f"Период: {tariff['label']} до {end.strftime('%d.%m.%Y')}"
    )
    await call.answer("✅ Эмуляция оплаты выполнена!", show_alert=True)
