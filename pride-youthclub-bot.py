import os
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from yookassa import Configuration, Payment

# 🚀 Подключаем модули (должны быть в папке modules/)
from modules.leadmagnit import send_leadmagnit_sequence, extract_base_label
from modules.morphotype import (
    start_morphotype,
    show_morphotype_details,
    choose_payment as morpho_choose_payment,
    manual_payment as morpho_manual_payment,
    back_to_payment_choice as morpho_back,
    manual_done as morpho_done,
    confirm_payment as morpho_confirm,
    reject_payment as morpho_reject,
    retry_payment as morpho_retry,
    handle_photo as morpho_photo,
    check_morpho_paid,
    get_user_topic_id,
    is_morphotype_chat_active,
    complete_morphotype_chat,
    GROUP_ID as MORPHO_GROUP_ID,
)
from modules.subscriptions import (
    show_subscribe_menu,
    choose_tariff,
    pay_yookassa,
    check_yookassa,
    manual_payment as sub_manual_payment,
    manual_done as sub_manual_done,
    confirm_payment as sub_confirm,
    reject_payment as sub_reject,
    retry_payment as sub_retry,
    emulate_payment as sub_emulate,
)


# =========================================================
#                    БАЗОВЫЕ ХЕЛПЕРЫ
# =========================================================
def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def fmt_cur(x: int | float) -> str:
    return f"{x:,}".replace(",", " ")


def parse_period(arg: str):
    if arg == "today":
        return datetime.now().date()
    elif arg == "week":
        return datetime.now().date() - timedelta(days=7)
    elif arg == "month":
        return datetime.now().date() - timedelta(days=30)
    return None


# =========================================================
#                    ЗАГРУЗКА .ENV
# =========================================================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("SERVICE_JSON_PATH")

OPEN_CHANNEL_ID = int(os.getenv("OPEN_CHANNEL_ID", "0"))
CLOSED_GROUP_ID = int(os.getenv("CLOSED_GROUP_ID", "0"))
CLOSED_CHAT_LINK = os.getenv("CLOSED_CHAT_LINK", "")

CHANNEL_BONUS = int(os.getenv("CHANNEL_BONUS", 100))
GROUP_BONUS = int(os.getenv("GROUP_BONUS", 500))

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_THREAD_ID = int(os.getenv("ADMIN_THREAD_ID", 0))

ADMINS_RAW = os.getenv("ADMINS", "")
ADMINS = set()
for adm in ADMINS_RAW.split(","):
    adm = adm.strip()
    if not adm:
        continue
    if adm.isdigit():
        ADMINS.add(int(adm))
    else:
        ADMINS.add(adm)

# YooKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pride-bot")


# =========================================================
#                    GOOGLE SHEETS
# =========================================================
def get_worksheet_case_insensitive(sh, ws_name):
    """Получает лист независимо от регистра"""
    existing_sheets = {ws.title.lower(): ws.title for ws in sh.worksheets()}
    actual_name = existing_sheets.get(ws_name.lower(), ws_name)
    return sh.worksheet(actual_name)


def sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(
        SERVICE_JSON_PATH,
        scopes=scopes
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    # авто-создание вкладок (проверяем регистронезависимо)
    sh.fetch_sheet_metadata()
    existing_sheets = {ws.title.lower(): ws.title for ws in sh.worksheets()}

    for ws_name in ["Users", "InviteLinks", "Bonuses", "Payments",
                    "Subscriptions", "Morphotype", "Referrals"]:
        try:
            # Пытаемся найти лист с любым регистром
            actual_name = existing_sheets.get(ws_name.lower(), ws_name)
            sh.worksheet(actual_name)
        except gspread.exceptions.WorksheetNotFound:
            try:
                sh.add_worksheet(ws_name, 1000, 12)
            except gspread.exceptions.APIError:
                # Лист уже существует
                pass

    # Users
    ws_users = get_worksheet_case_insensitive(sh, "Users")
    if not ws_users.cell(1, 1).value:
        ws_users.update(
            "A1:H1",
            [[
                "timestamp", "user_id", "username", "full_name",
                "ref_source", "action", "object", "bonus"
            ]]
        )

    # InviteLinks
    ws_links = get_worksheet_case_insensitive(sh, "InviteLinks")
    headers_links = ["ref_id", "bot_link", "created_at", "created_by"]
    first_row_links = ws_links.row_values(1)
    if first_row_links != headers_links:
        ws_links.clear()
        ws_links.update("A1:D1", [headers_links])

    # Bonuses
    ws_bonuses = get_worksheet_case_insensitive(sh, "Bonuses")
    if not ws_bonuses.cell(1, 1).value:
        ws_bonuses.update(
            "A1:D1",
            [["ref_id", "total_refs", "total_bonus", "updated_at"]]
        )

    # Payments
    ws_payments = get_worksheet_case_insensitive(sh, "Payments")
    pay_headers = [
        "timestamp", "user_id", "username", "full_name",
        "tariff", "price", "period", "status", "ref_source", "notified"
    ]
    first_row_pay = ws_payments.row_values(1)
    if first_row_pay != pay_headers:
        ws_payments.clear()
        ws_payments.update("A1:J1", [pay_headers])

    # Subscriptions
    ws_subs = get_worksheet_case_insensitive(sh, "Subscriptions")
    subs_headers = [
        "timestamp", "user_id", "username", "full_name", "tariff",
        "amount", "payment_method", "confirmed", "start_date", "end_date", "ref_source"
    ]
    first_row_subs = ws_subs.row_values(1)
    if first_row_subs != subs_headers:
        ws_subs.clear()
        ws_subs.update("A1:K1", [subs_headers])

    # Morphotype
    ws_morpho = get_worksheet_case_insensitive(sh, "Morphotype")
    morpho_headers = [
        "timestamp", "user_id", "username", "full_name",
        "status", "payment_method", "confirmed", "photo_link", "topic_id"
    ]
    first_row_morpho = ws_morpho.row_values(1)
    if first_row_morpho != morpho_headers:
        ws_morpho.clear()
        ws_morpho.update("A1:I1", [morpho_headers])

    # Referrals (для отслеживания 25%)
    ws_ref = get_worksheet_case_insensitive(sh, "Referrals")
    ref_headers = [
        "timestamp", "referrer_id", "referrer_username",
        "user_id", "username", "purchase_type", "amount", "bonus_given"
    ]
    first_row_ref = ws_ref.row_values(1)
    if first_row_ref != ref_headers:
        ws_ref.clear()
        ws_ref.update("A1:H1", [ref_headers])

    return sh


SHEETS = sheets()
WS_USERS = get_worksheet_case_insensitive(SHEETS, "Users")
WS_LINKS = get_worksheet_case_insensitive(SHEETS, "InviteLinks")
WS_BONUSES = get_worksheet_case_insensitive(SHEETS, "Bonuses")
WS_PAYMENTS = get_worksheet_case_insensitive(SHEETS, "Payments")
WS_SUBS = get_worksheet_case_insensitive(SHEETS, "Subscriptions")
WS_MORPHO = get_worksheet_case_insensitive(SHEETS, "Morphotype")
WS_REF = get_worksheet_case_insensitive(SHEETS, "Referrals")


# =========================================================
#             ФУНКЦИИ ДЛЯ РАБОТЫ С МЕТКАМИ
# =========================================================
def ensure_label_worksheet(label: str):
    """
    Создает вкладку, если её нет.
    Структура: Время перехода | Имя | Username | Telegram ID | Метка | Статус
    """
    try:
        ws = SHEETS.worksheet(label)
    except:
        ws = SHEETS.add_worksheet(label, 1000, 6)
        ws.update(
            "A1:F1",
            [[
                "Время перехода",
                "Имя пользователя",
                "Username",
                "Telegram ID",
                "Метка",
                "Статус"
            ]]
        )
    return ws


def check_user_in_label(label: str, user_id: int) -> bool:
    """Проверяет, есть ли юзер уже в вкладке конкретной метки (чтобы не дублировать)."""
    try:
        ws = SHEETS.worksheet(label)
        records = ws.get_all_records()
        for r in records:
            if str(r.get("Telegram ID", "")) == str(user_id):
                return True
    except:
        pass
    return False


def log_label_user(label: str, user: types.User, is_top10: bool) -> bool:
    """
    Записывает пользователя в вкладку label.
    Возвращает True если добавили, False если он уже там был.
    """
    if check_user_in_label(label, user.id):
        return False

    ws = ensure_label_worksheet(label)
    status = "первые 10" if is_top10 else "обычный"
    ws.append_row(
        [
            now(),
            user.full_name,
            user.username or "",
            user.id,
            label,
            status
        ],
        value_input_option="USER_ENTERED"
    )
    return True


def count_label_users(label: str) -> int:
    """Считает сколько юзеров в вкладке метки (для топ-10 приветствия)."""
    try:
        ws = SHEETS.worksheet(label)
        records = ws.get_all_records()
        return len(records)
    except:
        return 0


def ensure_friend_worksheet(base_label: str):
    """
    Создает вкладку {label}_friend для приглашений через "подруг".
    Структура: Время | Кто пригласил | Кого пригласил | Имя | Статус
    """
    friend_label = f"{base_label}_friend"
    try:
        ws = SHEETS.worksheet(friend_label)
    except:
        ws = SHEETS.add_worksheet(friend_label, 1000, 5)
        ws.update(
            "A1:E1",
            [[
                "Время приглашения",
                "Кто пригласил (ID/username)",
                "Кого пригласил (ID)",
                "Имя пользователя",
                "Статус"
            ]]
        )
    return ws


def log_friend_invitation(base_label: str, inviter_id: str, inviter_username: str, invited_user: types.User):
    """
    Записываем факт, что inviter пригласил invited_user по ссылки ..._friend_f<inviter_id>.
    """
    ws = ensure_friend_worksheet(base_label)

    # не дублируем, если он уже есть
    records = ws.get_all_records()
    for r in records:
        if str(r.get("Кого пригласил (ID)", "")) == str(invited_user.id):
            return False

    inviter_display = inviter_username if inviter_username else str(inviter_id)

    ws.append_row(
        [
            now(),
            inviter_display,
            invited_user.id,
            invited_user.full_name,
            "новый"
        ],
        value_input_option="USER_ENTERED"
    )
    return True


def parse_label(label_str: str):
    """
    Парсит payload:
      pridefit                  -> base_label=pridefit, inviter_id=None
      pridefit_friend_f123456   -> base_label=pridefit, inviter_id="123456"
    Возвращает (base_label, inviter_id, inviter_username)
    inviter_username сейчас не кодируем, так что None.
    """
    if not label_str:
        return None, None, None

    parts = label_str.split("_friend_f")
    if len(parts) == 2:
        base_label = parts[0]
        inviter_id = parts[1]
        return base_label, inviter_id, None
    else:
        return label_str, None, None


# =========================================================
#                 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================
def get_ref_id(user: types.User) -> str:
    return user.username if user.username else str(user.id)


def is_admin(user: types.User) -> bool:
    return user.id in ADMINS or (user.username and user.username in ADMINS)


async def notify_admin_text(text: str):
    try:
        if ADMIN_THREAD_ID:
            await bot.send_message(ADMIN_CHAT_ID, text, message_thread_id=ADMIN_THREAD_ID)
        else:
            await bot.send_message(ADMIN_CHAT_ID, text)
    except Exception as e:
        log.warning(f"Не удалось отправить в админ-чат: {e}")


async def notify_admin(user: types.User, ref: str, obj: str, bonus: int):
    """Уведомление админов о новом подписчике с бонусом"""
    uname = f"@{user.username}" if user.username else user.full_name
    text = (
        f"👤 Новый подписчик: {uname}\n"
        f"Реферал: {ref}\n"
        f"Подписка: {obj} (+{bonus})"
    )
    await notify_admin_text(text)


def count_user_total_bonus(user_id: int) -> int:
    """Сумма бонусов самого пользователя (для инфо в личку)."""
    rows = WS_USERS.get_all_records()
    total = 0
    for r in rows:
        if str(r.get("user_id")) == str(user_id):
            total += int(r.get("bonus", 0))
    return total


def append_user_event(user: types.User, ref_source: str, action: str, obj: str, bonus: int):
    """
    Логируем любое событие по пользователю в лист Users.
    Если есть бонус -> начисляем, пишем в Bonuses, уведомляем и юзера, и админов.
    """
    WS_USERS.append_row(
        [
            now(),
            user.id,
            user.username or "",
            user.full_name,
            ref_source or "",
            action,
            obj,
            bonus,
        ],
        value_input_option="USER_ENTERED",
    )
    
    # если это начисление по рефералу — обновим сводную
    if ref_source and ref_source != "direct" and bonus > 0:
        update_bonuses(ref_source, bonus)
        
        # отправка бонусного уведомления юзеру
        total_bonus = count_user_total_bonus(user.id)
        asyncio.create_task(
            bot.send_message(
                user.id,
                (
                    f"💎 Тебе начислено <b>+{bonus}</b> за {obj}!\n"
                    f"📊 Текущий баланс: {total_bonus} бонусов."
                )
            )
        )
        asyncio.create_task(
            notify_admin(user, ref_source, obj, bonus)
        )


def update_bonuses(ref_id: str, bonus: int):
    """Накапливаем суммарные бонусы для пригласителя во вкладке Bonuses."""
    rows = WS_BONUSES.get_all_records()
    for idx, r in enumerate(rows, start=2):
        if str(r.get("ref_id")) == str(ref_id):
            total_refs = int(r.get("total_refs", 0)) + 1
            total_bonus = int(r.get("total_bonus", 0)) + bonus
            WS_BONUSES.update(f"B{idx}:D{idx}", [[total_refs, total_bonus, now()]])
            return
    WS_BONUSES.append_row([ref_id, 1, bonus, now()], value_input_option="USER_ENTERED")


def get_user_id_by_ref(ref_source: str):
    """
    По рефке (username или numeric string) пытаемся найти реального автора.
    Возвращаем (user_id_str, username_str) или (None, None).
    """
    rows = WS_USERS.get_all_records()
    for r in reversed(rows):
        if str(r.get("username") or "") == ref_source:
            return str(r.get("user_id")), r.get("username") or ""
        if str(r.get("user_id") or "") == ref_source:
            return str(r.get("user_id")), r.get("username") or ""
    return None, None


def log_referrer_bonus(ref_user_id: str, ref_username: str, bonus: int, reason: str):
    """
    Отдельная запись в Users для пригласившего.
    Чтобы это отражалось у него в /mystats.
    """
    WS_USERS.append_row(
        [
            now(),
            ref_user_id,
            ref_username or "",
            "",
            "system",
            "ref_bonus",
            reason,
            bonus
        ],
        value_input_option="USER_ENTERED"
    )


def log_payment(user: types.User, tariff: str, price: int, period: str, ref_source: str, status="success"):
    """Лог записи в Payments."""
    WS_PAYMENTS.append_row(
        [
            now(),
            user.id,
            user.username or "",
            user.full_name,
            tariff,
            price,
            period,
            status,
            ref_source or "",
            "yes",
        ],
        value_input_option="USER_ENTERED",
    )


def get_user_original_label(user_id: int):
    """
    Возвращает оригинальную метку (ref_source) с которой юзер впервые зашёл.
    """
    rows = WS_USERS.get_all_records()
    for r in reversed(rows):
        if str(r.get("user_id")) == str(user_id) and r.get("action") == "started":
            ref = r.get("ref_source", "")
            if ref and ref != "direct":
                base_label, _, _ = parse_label(ref)
                return base_label
    return None


def find_user_ref_source(user_id: int | str) -> str | None:
    """
    Ищем последнюю запись для этого user_id в Users и забираем поле ref_source.
    Используется для начисления 25% реферальных.
    """
    rows = WS_USERS.get_all_records()
    for r in reversed(rows):
        if str(r.get("user_id")) == str(user_id):
            ref = r.get("ref_source") or ""
            return ref if ref else None
    return None


async def process_referral(user: types.User, purchase_type: str, amount: float):
    """
    Находим, по чьей ссылке пришёл user, и начисляем ему 25% от amount.
    Логируем в Referrals и уведомляем админа.
    """
    ref_source = find_user_ref_source(user.id)
    if not ref_source or ref_source == "direct":
        return

    bonus = round(amount * 0.25, 2)
    
    # Лог в лист Referrals
    WS_REF.append_row([
        now(),
        ref_source,
        ref_source if str(ref_source).startswith("@") else "",
        user.id,
        user.username or "",
        purchase_type,
        amount,
        bonus
    ], value_input_option="USER_ENTERED")

    # Обновим общую "копилку" по этому ref_source
    update_bonuses(ref_source, int(bonus))

    # Попробуем уведомить реферала
    try:
        if str(ref_source).isdigit():
            await bot.send_message(
                int(ref_source),
                f"🎉 По твоей ссылке оформили {purchase_type}!\n"
                f"💰 Тебе начислено {fmt_cur(bonus)} бонусов (25% от {fmt_cur(amount)})."
            )
    except Exception as e:
        log.warning(f"Не удалось уведомить реферала {ref_source}: {e}")

    # уведомление админу
    await notify_admin_text(
        f"📣 Реферальное начисление\n"
        f"Реферал: {ref_source}\n"
        f"Покупатель: @{user.username or user.id}\n"
        f"Тип: {purchase_type}\n"
        f"Сумма: {fmt_cur(amount)}₽ → бонус: {fmt_cur(bonus)}₽"
    )


# =========================================================
#                  FSM для рассылки
# =========================================================
class BroadcastStates(StatesGroup):
    waiting_for_message = State()


# =========================================================
#                  ИНИЦИАЛИЗАЦИЯ БОТА
# =========================================================
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())


# =========================================================
#                  ГЛАВНОЕ МЕНЮ
# =========================================================
def main_keyboard(user_id: int = None):
    """Убираем ReplyKeyboard - используем только команды бота"""
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()


# =========================================================
#                        /start
# =========================================================
@dp.message(CommandStart())
async def start(m: Message):
    """
    Логика онбординга:
    1. Сохраняем метку (utm) и кто приглашал.
    2. Показываем приветствие с Марией Букиной.
    3. Просим подписаться на канал и нажать "я подписалась".
    """
    payload_parts = m.text.split(maxsplit=1)
    raw_label = payload_parts[1].strip() if len(payload_parts) > 1 else None

    user = m.from_user
    first_name = user.first_name or user.full_name

    # разбор метки (обычная / friend-ссылка)
    base_label, inviter_id, inviter_username = parse_label(raw_label)

    if inviter_id:
        # это старт по friend-ссылке - логируем приглашение подруги
        log_friend_invitation(
            base_label,
            inviter_id,
            inviter_username,
            user
        )
        # переписываем ref_source в "чистый" base_label
        raw_label = base_label

    # считаем "топ-10" в рамках метки
    is_top10 = False
    if raw_label:
        current_count = count_label_users(raw_label)
        is_top10 = current_count < 10

        # логируем в таб метки (антидубль)
        log_label_user(raw_label, user, is_top10)

        # логируем факт старта
        append_user_event(user, raw_label, "started", "bot", 0)
    else:
        # без метки - direct
        append_user_event(user, "direct", "started", "bot", 0)

    # собираем приветственный текст
    greeting = (
        f"💫 Привет, {first_name}!\n\n"
        f"Рада видеть тебя 🌸\n"
        f"Я — Мария Букина, тренер по фейсфитнесу и автор клуба «Омоложения ПРАЙД».\n\n"
        f"Здесь мы возвращаем молодость естественным способом — без уколов, без фанатизма и без лишних обещаний 💖\n\n"
        f"Чтобы получить 🎁 бесплатный видео-урок\n"
        f"👇 подпишись на наш канал:\n"
        f"👉 <a href='https://t.me/PRIDEyouthClubChannel'>Клуб Омоложения ПРАЙД</a>\n\n"
        f"После подписки нажми кнопку «✅ Я подписалась» — и я пришлю тебе видео 💎"
    )

    if raw_label and is_top10:
        greeting += (
            f"\n\n🎉 {first_name}, тебе повезло!\n"
            f"Ты вошла в число первых 10 участниц,\n"
            f"которым Мария лично проведёт короткую консультацию 💬\n\n"
            f"Она свяжется с тобой в ближайшее время 💖"
        )

    # Кнопки
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Подписаться на канал",
                    url="https://t.me/PRIDEyouthClubChannel"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Я подписалась",
                    callback_data=f"check_sub_new:{raw_label or 'direct'}"
                )
            ]
        ]
    )

    # пытаемся отправить привет с welcome.jpg
    try:
        img_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "welcome.jpg"
        )
        if os.path.exists(img_path):
            photo = FSInputFile(img_path, filename="welcome.jpg")
            await m.answer_photo(
                photo,
                caption=greeting,
                reply_markup=kb
            )
            return
    except Exception as e:
        log.error(f"Ошибка отправки welcome.jpg: {e}")

    # если welcome.jpg нет - просто текст
    await m.answer(greeting, reply_markup=kb)


# =========================================================
#           Проверка подписки → лидмагнит → CTA
# =========================================================
@dp.callback_query(F.data.startswith("check_sub_new:"))
async def check_subscription_new(call: CallbackQuery):
    """
    1. Проверяем, подписан ли юзер на канал.
    2. Если да — отправляем warm-текст + запускаем отправку видео (с прелоадером).
    3. Потом через 5 минут пушим CTA "Пригласить подруг".
    4. Начисляем бонус рефералу (CHANNEL_BONUS) если был ref_source.
    """
    raw_label = call.data.split(":", 1)[1]
    user = call.from_user
    first_name = user.first_name or user.full_name

    # проверяем подписку в канале
    try:
        member = await bot.get_chat_member(OPEN_CHANNEL_ID, user.id)
        if member.status not in ["member", "administrator", "creator"]:
            await call.message.answer(
                f"❗Пока не вижу тебя среди подписчиков, {first_name} 💌\n"
                f"Подпишись, чтобы получить видео и начать путь к естественному омоложению 🌸\n"
                f"👉 <a href='https://t.me/PRIDEyouthClubChannel'>Перейти в канал</a>"
            )
            await call.answer()
            return
    except Exception as e:
        log.warning(f"Ошибка проверки подписки: {e}")
        await call.message.answer(
            "⚠️ Не удалось проверить подписку. Убедись, что бот является администратором канала."
        )
        await call.answer()
        return

    # Подписка есть — отправляем первое сообщение (до видео)
    await call.message.answer(
        "🌿 Ты теперь с нами 💫\n"
        "Сейчас пришлю обещанный видео-урок:"
    )

    # 🔹 Передаём label в модуль лидмагнита
    asyncio.create_task(send_leadmagnit_sequence(bot, call.from_user.id, label=raw_label))

    # Логируем бонус за подписку на канал (если была рефка)
    if raw_label and raw_label != "direct":
        append_user_event(
            call.from_user,
            raw_label,
            "subscribed",
            "channel",
            CHANNEL_BONUS
        )

    # Через 5 минут отправляем CTA "Пригласить подруг"
    async def delayed_invite_cta():
        await asyncio.sleep(300)

        cta_text = (
            f"💖 {first_name}, как тебе видео?\n"
            "Чувствуешь, что молодость действительно можно вернуть без уколов и процедур? 🌸\n\n"
            "Если тебе откликнулось — поделись этим открытием с подругами 💬\n"
            "Пусть и они узнают, что можно выглядеть моложе, не тратя состояния на косметологов!\n\n"
            "👭 В «Клубе Омоложения ПРАЙД» мы вдохновляем друг друга —\n"
            "и именно это делает путь к себе лёгким и приятным 💫\n\n"
            "👇 Пригласи подругу — пусть она тоже получит бесплатный видео-урок 💎"
        )

        kb_invite = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👭 Пригласить подруг",
                        callback_data="reveal_friend_link"
                    )
                ]
            ]
        )

        await bot.send_message(
            call.from_user.id,
            cta_text,
            reply_markup=kb_invite
        )

    asyncio.create_task(delayed_invite_cta())

    await call.answer()


# =========================================================
#        КНОПКА "ПРИГЛАСИТЬ ПОДРУГ" → friend-ссылка
# =========================================================
@dp.callback_query(F.data == "reveal_friend_link")
async def reveal_friend_link(call: CallbackQuery):
    """
    После того как мы через 5 минут прислали CTA с кнопкой "👭 Пригласить подруг",
    пользователь жмёт эту кнопку:
    - бот присылает персональную ссылку
    - даёт кнопку "📋 Скопировать ссылку" через switch_inline_query
    - убираем inline-клавиатуру у исходного сообщения
    """
    me = await bot.me()
    user = call.from_user

    base_label = get_user_original_label(user.id)
    if base_label:
        friend_link = f"https://t.me/{me.username}?start={base_label}_friend_f{user.id}"
    else:
        friend_link = f"https://t.me/{me.username}?start=friend_f{user.id}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Скопировать ссылку",
                    switch_inline_query=friend_link
                )
            ]
        ]
    )

    await call.message.answer(
        (
            "🔗 Вот твоя персональная ссылка:\n\n"
            f"<code>{friend_link}</code>\n\n"
            "📋 Нажми кнопку ниже, чтобы скопировать ссылку и отправить подруге 💬"
        ),
        parse_mode="HTML",
        reply_markup=kb
    )

    # убираем клавиатуру у предыдущего сообщения (где была кнопка "пригласить подруг")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await call.answer("📋 Ссылка готова! Отправь её подруге 💬", show_alert=True)


# =========================================================
#       КОМАНДЫ ДЛЯ МОДУЛЕЙ (morphotype + subscriptions)
# =========================================================

@dp.message(Command("morphotype"))
async def morphotype_cmd(m: Message, state: FSMContext):
    """Команда /morphotype для определения морфотипа"""
    await start_morphotype(bot, m, state)


# Morphotype callbacks
@dp.callback_query(F.data == "morpho_learn_more")
async def _morpho_learn_more(call: CallbackQuery, state: FSMContext):
    await show_morphotype_details(bot, call, state)


@dp.callback_query(F.data == "morpho_pay")
async def _morpho_pay(call: CallbackQuery, state: FSMContext):
    await morpho_choose_payment(bot, call, state)


@dp.callback_query(F.data == "morpho_manual")
async def _morpho_manual(call: CallbackQuery, state: FSMContext):
    await morpho_manual_payment(bot, call, state)


@dp.callback_query(F.data == "morpho_back")
async def _morpho_back(call: CallbackQuery, state: FSMContext):
    await morpho_back(bot, call, state)


@dp.callback_query(F.data == "morpho_done")
async def _morpho_done(call: CallbackQuery, state: FSMContext):
    await morpho_done(bot, call, state)


@dp.callback_query(F.data.startswith("morpho_confirm:"))
async def _morpho_confirm(call: CallbackQuery):
    await morpho_confirm(bot, call)
    # Начисляем 25% от 500₽
    user_id = int(call.data.split(":")[1])
    dummy_user = types.User(id=user_id, is_bot=False, first_name="User")
    await process_referral(dummy_user, "Морфотип", 500)

    # Скрываем все команды меню для пользователя (только чат с Марией)
    try:
        await bot.set_my_commands([], scope=BotCommandScopeChat(chat_id=user_id))
        log.info(f"Команды меню скрыты для пользователя {user_id} (активен морфотип чат)")
    except Exception as e:
        log.warning(f"Не удалось скрыть команды для {user_id}: {e}")


@dp.callback_query(F.data.startswith("morpho_reject:"))
async def _morpho_reject(call: CallbackQuery):
    await morpho_reject(bot, call)


@dp.callback_query(F.data.startswith("morpho_retry:"))
async def _morpho_retry(call: CallbackQuery):
    await morpho_retry(bot, call)


@dp.message(F.photo)
async def _morpho_photo(m: Message):
    await morpho_photo(bot, m)


# Subscriptions callbacks
@dp.callback_query(F.data.startswith("sub_tariff:"))
async def _sub_tariff(call: CallbackQuery, state: FSMContext):
    await choose_tariff(bot, call, state)


@dp.callback_query(F.data.startswith("sub_yookassa:"))
async def _sub_yk(call: CallbackQuery):
    await pay_yookassa(bot, call)


@dp.callback_query(F.data.startswith("sub_check:"))
async def _sub_check(call: CallbackQuery):
    before_user = call.from_user
    await check_yookassa(bot, call)
    
    # Начисляем 25% от суммы абонемента
    data = call.data.split(":")
    if len(data) >= 3:
        tariff_key = data[2]
        if tariff_key == "5w":
            amount = 2000
            title = "Абонемент 5 недель"
        else:
            amount = 4990
            title = "Абонемент 3 месяца"
        await process_referral(before_user, title, amount)


@dp.callback_query(F.data.startswith("sub_manual:"))
async def _sub_manual(call: CallbackQuery):
    await sub_manual_payment(bot, call)


@dp.callback_query(F.data.startswith("sub_done:"))
async def _sub_done(call: CallbackQuery):
    await sub_manual_done(bot, call)


@dp.callback_query(F.data.startswith("sub_confirm:"))
async def _sub_confirm(call: CallbackQuery):
    await sub_confirm(bot, call)
    
    # Начисляем 25% после подтверждения админом
    _, user_id, tariff_key = call.data.split(":")
    user_id = int(user_id)
    user = types.User(id=user_id, is_bot=False, first_name="User")
    if tariff_key == "5w":
        amount = 2000
        title = "Абонемент 5 недель"
    else:
        amount = 4990
        title = "Абонемент 3 месяца"
    await process_referral(user, title, amount)


@dp.callback_query(F.data.startswith("sub_reject:"))
async def _sub_reject(call: CallbackQuery):
    await sub_reject(bot, call)


@dp.callback_query(F.data.startswith("sub_retry:"))
async def _sub_retry(call: CallbackQuery):
    await sub_retry(bot, call)


@dp.callback_query(F.data.startswith("sub_emulate:"))
async def _sub_emulate(call: CallbackQuery):
    await sub_emulate(bot, call)


# =========================================================
#                       /invite
# =========================================================
@dp.message(Command("invite"))
async def invite_cmd(m: Message):
    """
    /invite для пользователя:
    - генерим персональную ссылку бота (?start=<id или username>)
    - сохраняем/обновляем в InviteLinks таб
    - показываем ссылку
    """
    ref_id = get_ref_id(m.from_user)
    me = await bot.me()
    bot_link = f"https://t.me/{me.username}?start={ref_id}"

    # обновляем/добавляем в InviteLinks
    rows = WS_LINKS.get_all_records()
    found = False
    for idx, r in enumerate(rows, start=2):
        if str(r.get("ref_id")) == str(ref_id):
            WS_LINKS.update(
                f"B{idx}:C{idx}",
                [[bot_link, now()]]
            )
            found = True
            break
    if not found:
        WS_LINKS.append_row(
            [ref_id, bot_link, now(), m.from_user.full_name],
            value_input_option="USER_ENTERED"
        )

    await m.answer(
        "👤 Твоя реферальная ссылка:\n\n"
        f"🔗 {bot_link}\n\n"
        "Приглашай подруг и получай бонусы!\n\n"
        "❗️Важно: бонусы начисляются только после подписки."
    )


# =========================================================
#                       /mystats
# =========================================================
@dp.message(Command("mystats"))
async def mystats(m: Message):
    """
    Обычный пользователь: видит тех, кто пришёл по его рефке, и свои бонусы.
    Админ: сводка по выручке, комиссиям и топ-рефералам.
    /mystats [today|week|month] для админа.
    """
    user = m.from_user
    args = m.text.split()
    period_arg = args[1] if len(args) > 1 else None
    filter_from = parse_period(period_arg) if period_arg else None

    # Ветка для АДМИНА
    if is_admin(user):
        payments = WS_PAYMENTS.get_all_records()
        total_revenue = 0
        total_commissions = 0
        by_tariff = defaultdict(int)
        by_referrer = defaultdict(int)

        for p in payments:
            ts = p.get("timestamp")
            if filter_from and ts:
                try:
                    dt = datetime.fromisoformat(ts).date()
                    if dt < filter_from:
                        continue
                except:
                    pass

            price = int(str(p.get("price", "0")) or 0)
            total_revenue += price
            by_tariff[p.get("tariff", "—")] += price

            ref = (p.get("ref_source") or "").strip()
            if ref:
                comm = int(price * 0.25)
                total_commissions += comm
                by_referrer[ref] += comm

        lines = [
            f"📈 <b>Сводка ({period_arg or 'all'})</b>",
            f"💵 Выручка: <b>{fmt_cur(total_revenue)}₽</b>",
            f"🤝 Комиссии (25%): <b>{fmt_cur(total_commissions)}</b>"
        ]

        lines.append("\n📦 По тарифам:")
        for t, s in sorted(by_tariff.items(), key=lambda x: -x[1]):
            lines.append(f" • {t}: {fmt_cur(s)}₽")

        if by_referrer:
            lines.append("\n🏆 ТОП-рефералы:")
            for i, (r, s) in enumerate(
                sorted(by_referrer.items(), key=lambda x: -x[1])[:10], 1
            ):
                lines.append(f"{i}. {r} — {fmt_cur(s)}₽")
        else:
            lines.append("\n🏆 ТОП-рефералы: пока нет")

        return await m.answer("\n".join(lines))

    # Ветка для обычного пользователя
    ref_id = get_ref_id(user)
    rows = WS_USERS.get_all_records()

    invited_lines = []
    total_bonus = 0
    for r in rows:
        if str(r.get("ref_source", "")) == ref_id and int(r.get("bonus", 0)) > 0:
            uname = (
                f"@{r['username']}" if r.get("username")
                else r.get("full_name", "")
            )
            invited_lines.append(
                f"{r.get('timestamp', '')} — {uname} — {r.get('object', '')} (+{r.get('bonus', 0)})"
            )
            total_bonus += int(r.get("bonus", 0))

    stats_text = (
        "\n".join(invited_lines)
        if invited_lines
        else "Пока никто не пришёл по твоей ссылке."
    )

    await m.answer(
        "📊 Моя статистика:\n\n"
        f"{stats_text}\n\n"
        f"💎 Суммарные бонусы: {fmt_cur(total_bonus)}"
    )


# =========================================================
#                  /trainers и тренер
# =========================================================
@dp.message(Command("trainers"))
async def trainers_cmd(m: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Мария Букина",
                    callback_data="trainer_bukina"
                )
            ]
        ]
    )
    await m.answer("Выберите тренера:", reply_markup=kb)


@dp.callback_query(F.data == "trainer_bukina")
async def trainer_bukina(call: CallbackQuery):
    caption = (
        "👩‍🏫 <b>Мария Букина — тренер по естественному омоложению</b>\n\n"
        "Дипломированный специалист по фейс-фитнесу и естественному омоложению лица и тела. "
        "С 2017 года помогает женщинам сохранять молодость без уколов и пластики.\n\n"
        "✨ Член Международной ассоциации фейс-фитнеса\n"
        "✨ Автор курсов и программ по омоложению\n"
        "✨ Практик с личным опытом восстановления после рождения третьего ребёнка\n\n"
        "«Я уверена: естественная красота — это не тренд, а новый стандарт»"
    )
    img_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "bukina.jpg"
    )
    if os.path.exists(img_path):
        photo = FSInputFile(img_path, filename="bukina.jpg")
        await call.message.answer_photo(photo, caption=caption)
    else:
        await call.message.answer(
            caption + "\n\n⚠️ Фото bukina.jpg не найдено в корне проекта."
        )
    await call.answer()


# =========================================================
#                 /channel и /subscribe
# =========================================================
@dp.message(Command("channel"))
async def channel_cmd(m: Message):
    await m.answer(
        "📢 Наш открытый канал:\n"
        "https://t.me/PRIDEyouthClubChannel"
    )


@dp.message(Command("subscribe"))
async def subscribe_cmd(m: Message, state: FSMContext):
    """Перенаправляем на модуль подписок"""
    await show_subscribe_menu(bot, m, state)


# =========================================================
#               АДМИН-ПАНЕЛЬ /admin
# =========================================================
@dp.message(Command("admin"))
async def admin_panel(m: Message):
    if not is_admin(m.from_user):
        await m.answer("⛔️ У вас нет доступа к админ-панели.")
        return

    # Считаем общее число уникальных user_id из Users
    all_users = set()
    rows = WS_USERS.get_all_records()
    for r in rows:
        uid = r.get("user_id")
        if uid:
            all_users.add(str(uid))

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Массовая рассылка",
                    callback_data="admin_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"👥 Количество подписчиков: {len(all_users)}",
                    callback_data="admin_users"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Метки и статистика",
                    callback_data="admin_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚪 Выйти",
                    callback_data="admin_exit"
                )
            ]
        ]
    )

    await m.answer(
        "🛠 <b>Меню администратора</b>\n\n"
        "Вы можете:\n"
        "1️⃣ Отправить массовое сообщение всем пользователям\n"
        "2️⃣ Проверить количество подписчиков\n"
        "3️⃣ Посмотреть статистику по меткам",
        reply_markup=kb
    )


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user):
        await call.answer("⛔️ Нет доступа", show_alert=True)
        return

    await call.message.answer(
        "📬 <b>Массовая рассылка</b>\n\n"
        "Введите текст сообщения для рассылки:\n"
        "(Можно использовать emoji, ссылки и HTML-форматирование)"
    )
    await state.set_state(BroadcastStates.waiting_for_message)
    await call.answer()


@dp.message(BroadcastStates.waiting_for_message)
async def admin_broadcast_confirm(m: Message, state: FSMContext):
    if not is_admin(m.from_user):
        return

    await state.update_data(broadcast_text=m.text)

    # считаем получателей
    all_users = set()
    rows = WS_USERS.get_all_records()
    for r in rows:
        uid = r.get("user_id")
        if uid:
            all_users.add(str(uid))

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_broadcast")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
        ]
    )

    await m.answer(
        f"Вы собираетесь отправить сообщение <b>{len(all_users)}</b> пользователям.\n\n"
        f"<b>Текст сообщения:</b>\n{m.text}\n\n"
        "Подтвердить отправку?",
        reply_markup=kb
    )


@dp.callback_query(F.data == "confirm_broadcast")
async def admin_broadcast_send(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user):
        await call.answer("⛔️ Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")

    if not broadcast_text:
        await call.message.answer("❌ Ошибка: текст сообщения не найден")
        await call.answer()
        return

    # получаем всех уникальных юзеров
    all_users = set()
    rows = WS_USERS.get_all_records()
    for r in rows:
        uid = r.get("user_id")
        if uid:
            all_users.add(int(uid))

    await call.message.answer("⏳ Начинаю рассылку...")

    delivered = 0
    failed = 0
    skipped = 0
    for uid in all_users:
        # Пропускаем пользователей с активным морфотип чатом
        if is_morphotype_chat_active(uid):
            skipped += 1
            log.info(f"Пропущен пользователь {uid} (активен морфотип чат)")
            continue

        try:
            await bot.send_message(uid, broadcast_text)
            delivered += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            log.warning(f"Не удалось отправить сообщение {uid}: {e}")

    await call.message.answer(
        "✅ Рассылка завершена!\n\n"
        f"📤 Успешно: <b>{delivered}</b>\n"
        f"🚫 Ошибок: <b>{failed}</b>\n"
        f"⏭️ Пропущено (морфотип чат): <b>{skipped}</b>"
    )

    await state.clear()
    await call.answer()


@dp.callback_query(F.data == "cancel_broadcast")
async def admin_broadcast_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Рассылка отменена")
    await call.answer()


@dp.callback_query(F.data == "admin_users")
async def admin_users_count(call: CallbackQuery):
    if not is_admin(call.from_user):
        await call.answer("⛔️ Нет доступа", show_alert=True)
        return

    all_users = set()
    rows = WS_USERS.get_all_records()
    for r in rows:
        uid = r.get("user_id")
        if uid:
            all_users.add(str(uid))

    await call.answer(
        f"👥 Всего пользователей: {len(all_users)}",
        show_alert=True
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user):
        await call.answer("⛔️ Нет доступа", show_alert=True)
        return

    # Статистика по меткам
    label_stats = defaultdict(int)
    rows = WS_USERS.get_all_records()
    for r in rows:
        ref_src = r.get("ref_source", "")
        if ref_src and ref_src != "direct":
            base, _, _ = parse_label(ref_src)
            if base:
                label_stats[base] += 1

    if not label_stats:
        await call.message.answer("📊 Статистика по меткам пока пуста")
        await call.answer()
        return

    lines = ["📊 <b>Статистика по меткам:</b>\n"]
    for label, cnt in sorted(label_stats.items(), key=lambda x: -x[1]):
        lines.append(f"• <code>{label}</code>: {cnt} пользователей")

    await call.message.answer("\n".join(lines))
    await call.answer()


@dp.callback_query(F.data == "admin_exit")
async def admin_exit(call: CallbackQuery):
    await call.message.answer("👋 Выход из админ-панели")
    await call.answer()


# =========================================================
#       Мониторинг Payments → в админ-чат (внешние строки)
# =========================================================
async def monitor_payments():
    """
    Периодически проверяет WS_PAYMENTS и ищет строки, у которых notified != 'yes'.
    Если находит — шлёт админам уведомление и проставляет notified='yes'.
    Это нужно для платежей, записанных НЕ ботом.
    """
    while True:
        try:
            values = WS_PAYMENTS.get_all_values()
            if len(values) >= 2:
                headers = values[0]
                col_map = {h: i for i, h in enumerate(headers)}
                notified_idx = col_map.get("notified")

                for row_idx in range(1, len(values)):
                    row = values[row_idx]

                    need_notify = True
                    if notified_idx is not None and notified_idx < len(row):
                        if row[notified_idx].strip().lower() == "yes":
                            need_notify = False

                    if not need_notify:
                        continue

                    ts = row[col_map.get("timestamp", 0)] if col_map.get("timestamp", None) is not None else ""
                    uname = row[col_map.get("username", 2)] if len(row) > 2 else ""
                    fulln = row[col_map.get("full_name", 3)] if len(row) > 3 else ""
                    tariff = row[col_map.get("tariff", 4)] if len(row) > 4 else ""
                    price = row[col_map.get("price", 5)] if len(row) > 5 else "0"
                    ref = row[col_map.get("ref_source", 8)] if len(row) > 8 else ""

                    buyer = f"@{uname}" if uname else (fulln or "—")
                    text = (
                        "💳 <b>Оплата (новая строка)</b>\n"
                        f"🕒 {ts}\n"
                        f"👤 {buyer}\n"
                        f"📦 {tariff}\n"
                        f"💵 {price}₽\n"
                        f"👥 Реферал: {ref or '—'}"
                    )
                    await notify_admin_text(text)

                    # помечаем notified='yes'
                    if notified_idx is not None:
                        WS_PAYMENTS.update_cell(row_idx + 1, notified_idx + 1, "yes")
                    else:
                        # если нет колонки notified (теоретически), создаём
                        WS_PAYMENTS.update("J1", [["notified"]])
                        WS_PAYMENTS.update_cell(row_idx + 1, 10, "yes")

        except Exception as e:
            log.warning(f"monitor_payments error: {e}")

        await asyncio.sleep(20)


# =========================================================
#         ПЕРЕСЫЛКА СООБЩЕНИЙ МЕЖДУ ЮЗЕРОМ И ТОПИКОМ
# =========================================================
@dp.message(F.chat.type == "private", F.text)
async def forward_user_to_topic(m: Message):
    """Пересылка текстовых сообщений от пользователя в топик"""
    # Игнорируем команды
    if m.text.startswith("/"):
        return  # Пропускаем, пусть обработают другие хендлеры

    user_id = m.from_user.id
    topic_id = get_user_topic_id(user_id)

    if topic_id:
        # Пересылаем сообщение в топик
        await bot.send_message(
            MORPHO_GROUP_ID,
            f"💬 От пользователя {m.from_user.full_name} (@{m.from_user.username or user_id}):\n\n{m.text}",
            message_thread_id=topic_id
        )
        await m.answer("✅ Сообщение отправлено Марии Букиной")


@dp.message(F.chat.id == MORPHO_GROUP_ID, F.is_topic_message == True, F.text)
async def forward_topic_to_user(m: Message):
    """Пересылка ответов из топика пользователю"""
    topic_id = m.message_thread_id

    # Проверяем, является ли это командой /ok
    if m.text and m.text.strip() == "/ok":
        # Находим пользователя по topic_id
        from modules.morphotype import WS_MORPHO
        rows = WS_MORPHO.get_all_records()
        user_id = None

        for r in reversed(rows):
            if str(r.get("topic_id")) == str(topic_id):
                user_id = r.get("user_id")
                break

        if user_id:
            # Завершаем морфотип чат
            success = complete_morphotype_chat(int(user_id))
            if success:
                # Отправляем уведомление в топик
                await m.answer("✅ Морфотип чат завершен. Пользователю восстановлено обычное меню.")

                # Отправляем уведомление пользователю
                try:
                    await bot.send_message(
                        int(user_id),
                        "✅ Консультация по морфотипу завершена!\n\n"
                        "Спасибо за участие 💚\n"
                        "Теперь вам доступны все функции бота."
                    )

                    # Устанавливаем команды меню обратно
                    user_cmds = [
                        BotCommand(command="morphotype", description="📸 Узнать свой морфотип"),
                        BotCommand(command="subscribe", description="🔒 Купить абонемент"),
                        BotCommand(command="invite", description="👭 Мои ссылки"),
                        BotCommand(command="channel", description="💬 Канал Клуб Омоложения"),
                        BotCommand(command="trainers", description="О тренерах"),
                        BotCommand(command="mystats", description="📊 Моя статистика"),
                    ]
                    await bot.set_my_commands(user_cmds, scope=BotCommandScopeChat(chat_id=int(user_id)))
                except Exception as e:
                    log.warning(f"Не удалось уведомить пользователя {user_id}: {e}")
            else:
                await m.answer("⚠️ Не удалось завершить морфотип чат. Проверьте данные пользователя.")
        else:
            await m.answer("⚠️ Не удалось найти пользователя для этого топика.")
        return

    # Обычная пересылка сообщений
    # Находим пользователя по topic_id
    from modules.morphotype import WS_MORPHO
    rows = WS_MORPHO.get_all_records()
    user_id = None

    for r in reversed(rows):
        if str(r.get("topic_id")) == str(topic_id):
            user_id = r.get("user_id")
            break

    if user_id and m.from_user.id != bot.id:  # Не пересылаем собственные сообщения бота
        try:
            await bot.send_message(
                int(user_id),
                f"💌 Мария Букина:\n\n{m.text}"
            )
        except Exception as e:
            log.warning(f"Не удалось переслать сообщение пользователю {user_id}: {e}")


# =========================================================
#                           MAIN
# =========================================================
async def main():
    # Команды для обычных пользователей
    user_cmds = [
        BotCommand(command="morphotype", description="📸 Узнать свой морфотип"),
        BotCommand(command="subscribe", description="🔒 Купить абонемент"),
        BotCommand(command="invite", description="👭 Мои ссылки"),
        BotCommand(command="channel", description="💬 Канал Клуб Омоложения"),
        BotCommand(command="trainers", description="О тренерах"),
        BotCommand(command="mystats", description="📊 Моя статистика"),
    ]
    await bot.set_my_commands(user_cmds)

    # Команды для админов
    admin_cmds = user_cmds + [
        BotCommand(command="admin", description="Рассылка / панель админа"),
    ]
    for admin_id in ADMINS:
        if isinstance(admin_id, int):
            try:
                await bot.set_my_commands(
                    admin_cmds,
                    scope=BotCommandScopeChat(chat_id=admin_id)
                )
            except Exception as e:
                log.warning(f"Не удалось установить команды для {admin_id}: {e}")

    # Запускаем мониторинг платежей (новые строки в таблице)
    asyncio.create_task(monitor_payments())

    # Запускаем поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
