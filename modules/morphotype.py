import os
import logging
import asyncio
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone
from aiogram import Bot, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from dotenv import load_dotenv

load_dotenv()

# ===== Логирование =====
log = logging.getLogger("morphotype")

# ===== Настройки =====
GROUP_ID = int(os.getenv("MORPHO_GROUP_ID", "-1003113977264"))  # https://t.me/c/3113977264/
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
SERVICE_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("SERVICE_JSON_PATH")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

PAY_PHONE = "+79093802552"
PRICE = 500

# ===== Google Sheets =====
def morpho_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(SERVICE_JSON_PATH, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    # Обновляем список листов
    sh.fetch_sheet_metadata()

    # Ищем лист по имени (с маленькой буквы, как в таблице)
    worksheet_list = [ws.title for ws in sh.worksheets()]

    if "morphotype" in worksheet_list:
        ws = sh.worksheet("morphotype")
    elif "Morphotype" in worksheet_list:
        ws = sh.worksheet("Morphotype")
    else:
        try:
            ws = sh.add_worksheet("Morphotype", rows=1000, cols=10)
            ws.update("A1:J1", [[
                "timestamp", "user_id", "username", "full_name",
                "status", "payment_method", "confirmed",
                "photo_link", "topic_id", "morpho_completed"
            ]])
        except gspread.exceptions.APIError:
            # Если лист уже существует, получаем его
            sh.fetch_sheet_metadata()
            ws = sh.worksheet("morphotype")

    # Проверяем и добавляем колонку morpho_completed если её нет
    try:
        headers = ws.row_values(1)
        if "morpho_completed" not in headers:
            ws.update_cell(1, 10, "morpho_completed")
    except:
        pass

    return ws

WS_MORPHO = morpho_sheets()

def log_morpho(user, status="ожидание оплаты", payment_method="", confirmed="", photo_link="", topic_id=""):
    WS_MORPHO.append_row([
        datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        user.id,
        user.username or "",
        user.full_name,
        status,
        payment_method,
        confirmed,
        photo_link,
        topic_id
    ], value_input_option="USER_ENTERED")


def check_morpho_paid(user_id: int) -> bool:
    """Проверяет, оплатил ли пользователь морфотип"""
    rows = WS_MORPHO.get_all_records()
    for r in reversed(rows):
        if str(r.get("user_id")) == str(user_id):
            confirmed = str(r.get("confirmed", "")).lower()
            if confirmed == "yes":
                return True
    return False


def get_user_topic_id(user_id: int) -> int | None:
    """Получает topic_id для пользователя"""
    rows = WS_MORPHO.get_all_records()
    for r in reversed(rows):
        if str(r.get("user_id")) == str(user_id):
            confirmed = str(r.get("confirmed", "")).lower()
            topic_id = r.get("topic_id")
            if confirmed == "yes" and topic_id:
                return int(topic_id)
    return None


def is_morphotype_chat_active(user_id: int) -> bool:
    """
    Проверяет, активен ли морфотип чат для пользователя.
    Активен = оплачен (confirmed=yes) и НЕ завершен (morpho_completed != yes)
    """
    rows = WS_MORPHO.get_all_records()
    for r in reversed(rows):
        if str(r.get("user_id")) == str(user_id):
            confirmed = str(r.get("confirmed", "")).lower()
            completed = str(r.get("morpho_completed", "")).lower()
            if confirmed == "yes" and completed != "yes":
                return True
    return False


def complete_morphotype_chat(user_id: int) -> bool:
    """
    Помечает морфотип чат как завершенный (когда Мария отправила /ok).
    Возвращает True если успешно, False если не найден.
    """
    rows = WS_MORPHO.get_all_records()
    for idx, r in enumerate(rows, start=2):  # start=2 потому что первая строка - заголовки
        if str(r.get("user_id")) == str(user_id):
            confirmed = str(r.get("confirmed", "")).lower()
            if confirmed == "yes":
                # Находим колонку morpho_completed (должна быть 10-я, после topic_id)
                # Структура: timestamp, user_id, username, full_name, status, payment_method, confirmed, photo_link, topic_id, morpho_completed
                try:
                    WS_MORPHO.update_cell(idx, 10, "yes")  # 10-я колонка = morpho_completed
                    return True
                except Exception as e:
                    log.error(f"Ошибка обновления morpho_completed для user {user_id}: {e}")
                    return False
    return False


# ===== FSM состояния =====
class MorphotypeFSM(StatesGroup):
    waiting_payment_method = State()
    waiting_manual_confirm = State()
    waiting_photo = State()


# ===== Функции =====
async def start_morphotype(bot: Bot, message: types.Message, state: FSMContext):
    """Первый экран: кнопка узнать подробнее"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Узнать подробнее", callback_data="morpho_learn_more")]
    ])

    caption = (
        "📸 Загрузи фото и получи рекомендации от Марии Букиной.\n"
        f"Стоимость услуги — {PRICE}₽"
    )

    # Пытаемся отправить с фото morph.jpg
    try:
        import os
        morph_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "morph.jpg")
        if os.path.exists(morph_path):
            photo = FSInputFile(morph_path, filename="morph.jpg")
            await message.answer_photo(photo, caption=caption, reply_markup=kb)
        else:
            # Если файла нет - отправляем просто текст
            await message.answer(caption, reply_markup=kb)
    except Exception as e:
        log.warning(f"Не удалось отправить morph.jpg: {e}")
        await message.answer(caption, reply_markup=kb)

    await state.set_state(MorphotypeFSM.waiting_payment_method)


async def show_morphotype_details(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Показать подробную информацию о морфотипе"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оплатить 500₽ и загрузить фото", callback_data="morpho_pay")]
    ])

    details_text = (
        "🔥 Определение морфотипа по фотографии от Марии Букиной — твой первый шаг к омоложению без уколов.\n\n"
        "Ты можешь тратить месяцы на массажи и кремы, но без знания своего морфотипа всё это — как стрелять в темноте.\n"
        "Морфотип — это карта твоего лица: как распределяются ткани, мышцы и жировые пакеты, почему «поплыл» овал или появилась отёчность.\n\n"
        "📸 Отправь одно фото — и уже через день ты:\n"
        "✨ узнаешь, почему именно у тебя появились возрастные изменения;\n"
        "✨ поймёшь, какие техники тебе подходят.\n\n"
        f"Стоимость услуги — {PRICE}₽"
    )

    await call.message.edit_caption(caption=details_text, reply_markup=kb)
    await call.answer()
    await state.set_state(MorphotypeFSM.waiting_payment_method)


async def choose_payment(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Выбор способа оплаты"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через YooKassa", callback_data="morpho_yookassa")],
        [InlineKeyboardButton(text="💰 Оплатить прямым переводом", callback_data="morpho_manual")],
    ])
    await call.message.edit_caption(
        caption="Выберите способ оплаты 👇",
        reply_markup=kb
    )
    await state.set_state(MorphotypeFSM.waiting_manual_confirm)
    await call.answer()


async def manual_payment(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Инструкция для ручного перевода"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="morpho_done")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="morpho_back")],
    ])
    await call.message.edit_caption(
        caption=f"Переведите {PRICE}₽ через СБП по номеру <b>{PAY_PHONE}</b>\n"
        "и укажите в примечании ваш Telegram username.\n\n"
        "После перевода нажмите «Готово».",
        reply_markup=kb
    )
    await state.set_state(MorphotypeFSM.waiting_manual_confirm)
    await call.answer()


async def back_to_payment_choice(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору способа оплаты"""
    await choose_payment(bot, call, state)


async def manual_done(bot: Bot, call: types.CallbackQuery, state: FSMContext):
    """Пользователь нажал 'Готово' после перевода"""
    user = call.from_user
    log_morpho(user, status="ожидание оплаты", payment_method="перевод")

    await call.message.edit_caption(caption="💌 Ожидайте подтверждения оплаты.")
    await call.answer()

    # создаем топик в группе
    thread = await bot.create_forum_topic(GROUP_ID, name=user.username or str(user.id))
    topic_id = thread.message_thread_id

    # уведомление админам
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"morpho_confirm:{user.id}:{topic_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"morpho_reject:{user.id}:{topic_id}")]
    ])
    msg = (
        f"💳 {user.full_name} оплатил {PRICE}₽ за морфортип прямым переводом.\n"
        "Подтвердить получение средств?"
    )
    await bot.send_message(GROUP_ID, msg, message_thread_id=topic_id, reply_markup=kb)

    await state.clear()


async def confirm_payment(bot: Bot, call: types.CallbackQuery):
    """Админ нажал 'Да'"""
    _, user_id, topic_id = call.data.split(":")
    user_id = int(user_id)
    topic_id = int(topic_id)

    # обновляем таблицу
    WS_MORPHO.append_row([
        datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        user_id, "", "", "оплата подтверждена", "перевод", "yes", "", topic_id
    ], value_input_option="USER_ENTERED")

    # Отправляем подтверждение
    await bot.send_message(
        user_id,
        "✅ Оплата подтверждена!\nПришлите, пожалуйста, фото лица крупным планом."
    )
    await bot.send_message(GROUP_ID, f"✅ Оплата пользователя {user_id} подтверждена.", message_thread_id=topic_id)
    await call.answer("Подтверждено.")


async def reject_payment(bot: Bot, call: types.CallbackQuery):
    """Админ нажал 'Нет'"""
    _, user_id, topic_id = call.data.split(":")
    user_id = int(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверил, всё ок", callback_data=f"morpho_retry:{topic_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="morpho_cancel")],
    ])
    await bot.send_message(user_id, "⚠️ Оплата не подтверждена. Проверьте перевод.", reply_markup=kb)
    await call.answer("Отказ отправлен пользователю.")


async def retry_payment(bot: Bot, call: types.CallbackQuery):
    """Пользователь повторно подтвердил оплату"""
    topic_id = int(call.data.split(":")[1])
    user = call.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"morpho_confirm:{user.id}:{topic_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"morpho_reject:{user.id}:{topic_id}")]
    ])
    await bot.send_message(GROUP_ID, f"💳 Пользователь {user.full_name} повторно подтвердил оплату. Проверить?",
                           message_thread_id=topic_id, reply_markup=kb)
    await call.answer("Отправлено на проверку.")


async def handle_photo(bot: Bot, message: types.Message):
    """Получение фото пользователем после подтверждения"""
    user = message.from_user
    photo = message.photo[-1]
    file_id = photo.file_id

    # ищем топик (можно хранить в Sheets, здесь для упрощения ищем последнюю строку)
    rows = WS_MORPHO.get_all_records()
    topic_id = None
    for r in reversed(rows):
        if str(r.get("user_id")) == str(user.id):
            topic_id = r.get("topic_id")
            break
    if not topic_id:
        await message.answer("⚠️ Ошибка: не найден топик для вашего анализа. Свяжитесь с администратором.")
        return

    await bot.send_photo(GROUP_ID, file_id,
                         caption=f"📸 Фото пользователя {user.full_name}\n@{user.username or user.id}",
                         message_thread_id=int(topic_id))
    await message.answer("Фото отправлено Марии Букиной 💌")
    log.info(f"Фото пользователя {user.id} отправлено в топик {topic_id}.")
