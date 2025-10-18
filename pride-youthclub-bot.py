import os
import asyncio
import logging
from datetime import datetime, timezone
from collections import defaultdict

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, BotCommand,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommandScopeChat, FSInputFile
)
from aiogram.client.default import DefaultBotProperties
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import timedelta
from yookassa import Configuration, Payment
import uuid

def parse_period(arg: str):
    if arg == "today":
        return datetime.now().date()
    elif arg == "week":
        return datetime.now().date() - timedelta(days=7)
    elif arg == "month":
        return datetime.now().date() - timedelta(days=30)
    return None

# ================== CONFIG ==================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

OPEN_CHANNEL_ID = int(os.getenv("OPEN_CHANNEL_ID"))
CLOSED_GROUP_ID = int(os.getenv("CLOSED_GROUP_ID"))
CLOSED_CHAT_LINK = os.getenv("CLOSED_CHAT_LINK")

CHANNEL_BONUS = int(os.getenv("CHANNEL_BONUS", 10))
GROUP_BONUS = int(os.getenv("GROUP_BONUS", 500))

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
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
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pride-bot")

# ================== Google Sheets ==================
def sheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(SERVICE_JSON_PATH, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    # авто-создание вкладок
    for ws_name in ["Users", "InviteLinks", "Bonuses", "Payments"]:
        try:
            sh.worksheet(ws_name)
        except:
            sh.add_worksheet(ws_name, 1000, 10)

    # Users
    ws_users = sh.worksheet("Users")
    if not ws_users.cell(1, 1).value:
        ws_users.update("A1:H1", [[
            "timestamp", "user_id", "username", "full_name",
            "ref_source", "action", "object", "bonus"
        ]])

    # InviteLinks
    ws_links = sh.worksheet("InviteLinks")
    headers = ["ref_id", "bot_link", "created_at", "created_by"]
    first_row = ws_links.row_values(1)
    if first_row != headers:
        ws_links.clear()
        ws_links.update("A1:D1", [headers])

    # Bonuses
    ws_bonuses = sh.worksheet("Bonuses")
    if not ws_bonuses.cell(1, 1).value:
        ws_bonuses.update("A1:D1", [[
            "ref_id", "total_refs", "total_bonus", "updated_at"
        ]])

    # Payments (+тех. колонка notified)
    ws_payments = sh.worksheet("Payments")
    pay_headers = ["timestamp", "user_id", "username", "full_name",
                   "tariff", "price", "period", "status", "ref_source", "notified"]
    first_row = ws_payments.row_values(1)
    if first_row != pay_headers:
        ws_payments.clear()
        ws_payments.update("A1:J1", [pay_headers])

    return sh

SHEETS = sheets()
WS_USERS = SHEETS.worksheet("Users")
WS_LINKS = SHEETS.worksheet("InviteLinks")
WS_BONUSES = SHEETS.worksheet("Bonuses")
WS_PAYMENTS = SHEETS.worksheet("Payments")

# ================== Helpers ==================
def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def get_ref_id(user):
    """username если есть, иначе id строкой"""
    return user.username if user.username else str(user.id)

def is_admin(user):
    return user.id in ADMINS or (user.username and user.username in ADMINS)

def fmt_cur(x: int) -> str:
    return f"{x:,}".replace(",", " ")

async def notify_admin_text(text: str):
    try:
        if ADMIN_THREAD_ID:
            await bot.send_message(ADMIN_CHAT_ID, text, message_thread_id=ADMIN_THREAD_ID)
        else:
            await bot.send_message(ADMIN_CHAT_ID, text)
    except Exception as e:
        log.warning(f"Не удалось отправить в админ-чат: {e}")

async def notify_admin(user, ref, obj, bonus):
    uname = f"@{user.username}" if user.username else user.full_name
    text = (f"👤 Новый подписчик: {uname}\n"
            f"Реферал: {ref}\n"
            f"Подписка: {obj} (+{bonus})")
    await notify_admin_text(text)

def update_bonuses(ref_id: str, bonus: int):
    """Накапливаем бонусы по ref_id во вкладке Bonuses"""
    rows = WS_BONUSES.get_all_records()
    found = False
    for idx, r in enumerate(rows, start=2):
        if str(r.get("ref_id", "")) == str(ref_id):
            total_refs = int(r["total_refs"]) + 1
            total_bonus = int(r["total_bonus"]) + bonus
            WS_BONUSES.update(f"B{idx}:D{idx}", [[total_refs, total_bonus, now()]])
            found = True
            break
    if not found:
        WS_BONUSES.append_row([ref_id, 1, bonus, now()], value_input_option="USER_ENTERED")

def count_user_total_bonus(user_id: int):
    rows = WS_USERS.get_all_records()
    total = 0
    for r in rows:
        if str(r.get("user_id")) == str(user_id):
            total += int(r["bonus"])
    return total

def append_user_event(user, ref_source, action, obj, bonus):
    """Логируем событие по ПОЛЬЗОВАТЕЛЮ (приглашённый/покупатель) во вкладку Users"""
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

    if ref_source and ref_source != "direct" and bonus > 0:
        update_bonuses(ref_source, bonus)

    total_bonus = count_user_total_bonus(user.id)

    if bonus > 0:
        asyncio.create_task(
            bot.send_message(
                user.id,
                f"💎 Тебе начислено <b>+{bonus}</b> за {obj}!\n"
                f"📊 Текущий баланс: {total_bonus} бонусов."
            )
        )

    if bonus > 0:
        asyncio.create_task(notify_admin(user, ref_source, obj, bonus))

def get_user_id_by_ref(ref_source: str):
    """
    Пытаемся найти user_id реферала по ref_source (username или числовой id)
    Ищем по Users: либо username == ref_source, либо user_id == ref_source
    Возвращает (user_id, username) или (None, None)
    """
    rows = WS_USERS.get_all_records()
    for r in reversed(rows):  # последние записи вероятнее актуальнее
        if str(r.get("username") or "") == ref_source:
            return str(r.get("user_id")), r.get("username") or ""
        if str(r.get("user_id") or "") == ref_source:
            return str(r.get("user_id")), r.get("username") or ""
    return None, None

def log_referrer_bonus(ref_user_id: str, ref_username: str, bonus: int, reason: str):
    """
    Записываем отдельной строкой начисление бонуса рефералу во вкладку Users,
    чтобы это отображалось в статистике /mystats у реферала.
    """
    WS_USERS.append_row([
        now(),
        ref_user_id,
        ref_username or "",
        "",              # full_name неизвестно (не критично)
        "system",
        "ref_bonus",
        reason,
        bonus
    ], value_input_option="USER_ENTERED")

# --- Payments logger ---
def log_payment(user, tariff, price, period, ref_source, status="success"):
    # notified = yes, т.к. мы шлём уведомление в этом же процессе
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
        "yes"
    ], value_input_option="USER_ENTERED")

# ================== Bot ==================
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


@dp.callback_query(F.data == "trainers")
async def trainers_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мария Букина", callback_data="trainer_bukina")],
    ])
    await call.message.answer("Выберите тренера:", reply_markup=kb)
    await call.answer()

@dp.message(Command("trainers"))
async def trainers_cmd(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мария Букина", callback_data="trainer_bukina")],
    ])
    await m.answer("Выберите тренера:", reply_markup=kb)


# /start
@dp.message(CommandStart())
async def start(m: Message):
    payload = m.text.split(maxsplit=1)
    ref = payload[1].strip() if len(payload) > 1 else None

    if ref:
        # фиксируем факт старта по реферальной ссылке (без бонуса)
        append_user_event(m.from_user, ref, "started", "bot", 0)

    # PDF
    try:
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youthsecret.pdf")
        if os.path.exists(pdf_path):
            file = FSInputFile(pdf_path, filename="youthsecret.pdf")
            await m.answer_document(file, caption="Диагностика морфотипа лица")
    except Exception as e:
        log.error(f"Не удалось отправить PDF: {e}")

    # Главное меню
    kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 Перейти в канал", url="https://t.me/PRIDEyouthClubChannel")],
    [InlineKeyboardButton(text="🔒 Закрытая группа", callback_data="closed_group")],
    [InlineKeyboardButton(text="🤝 Позвать подруг", callback_data="invitebtn")],
    [InlineKeyboardButton(text="👩‍🏫 О тренерах", callback_data="trainers")],
    ])
    await m.answer("Подпишись на канал и оформи доступ в закрытую группу 👇", reply_markup=kb)

# --- Кнопка "Закрытая группа" ---
@dp.callback_query(F.data == "closed_group")
async def closed_group(call: types.CallbackQuery):
    text = (
        "🔒 Членство в закрытой группе стоит <b>990₽/мес</b>.\n\n"
        "Выберите тариф 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц — 990₽", callback_data="pay:1")],
        [InlineKeyboardButton(text="3 месяца — 2673₽ (-10%)", callback_data="pay:3")],
        [InlineKeyboardButton(text="12 месяцев — 8910₽ (-25%)", callback_data="pay:12")],
    ])
    await call.message.answer(text, reply_markup=kb)
    await call.answer()

# --- Эмуляция оплаты ---
@dp.callback_query(F.data.startswith("pay:"))
async def process_payment(call: types.CallbackQuery):
    period = call.data.split(":")[1]
    if period == "1":
        price = 990
        label = "1 месяц"
    elif period == "3":
        price = 2673
        label = "3 месяца (-10%)"
    else:
        price = 8910
        label = "12 месяцев (-25%)"

    text = (
        f"💳 Тариф: {label}\n"
        f"Сумма: {fmt_cur(price)}₽\n\n"
        "👉 Нажмите кнопку ниже для перехода к оплате через ЮKassa."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить через ЮKassa", callback_data=f"success:{period}")]
    ])
    await call.message.answer(text, reply_markup=kb)
    await call.answer()

# --- Успешная оплата ---
@dp.callback_query(F.data.startswith("success:"))
async def payment_success(call: types.CallbackQuery):
    period = call.data.split(":")[1]
    if period == "1":
        price = 990
        label = "1 месяц"
    elif period == "3":
        price = 2673
        label = "3 месяца (-10%)"
    else:
        price = 8910
        label = "12 месяцев (-25%)"

    # определяем реферера (если пользователь ранее запускал бота по ?start=ref)
    rows = WS_USERS.get_all_records()
    ref_source = None
    for r in reversed(rows):
        if str(r.get("user_id")) == str(call.from_user.id) and r.get("ref_source") and r["ref_source"] != "direct":
            ref_source = r["ref_source"]
            break

    # логируем оплату (со статическим notified=yes для внутр. операций бота)
    log_payment(call.from_user, label, price, period, ref_source, "success")

    # уведомление в админ-чат
    uname = f"@{call.from_user.username}" if call.from_user.username else call.from_user.full_name
    admin_text = (
        f"💳 <b>Оплата!</b>\n"
        f"👤 Покупатель: {uname}\n"
        f"Тариф: {label}\n"
        f"Сумма: <b>{fmt_cur(price)}₽</b>\n"
        f"Реферал: {ref_source if ref_source else '—'}"
    )
    await notify_admin_text(admin_text)

    # если был реферал — начисляем ему 25% от суммы и уведомляем
    if ref_source:
        ref_user_id, ref_username = get_user_id_by_ref(ref_source)
        try:
            bonus = int(price * 0.25)
            # записываем строку о бонусе рефералу в Users (чтобы /mystats его видел)
            log_referrer_bonus(ref_user_id or ref_source, ref_username or (ref_source if ref_source.startswith("@") else ""), bonus, f"Комиссия 25% от оплаты {label}")
            # обновим общую таблицу бонусов по ref_id
            update_bonuses(ref_source, bonus)
            # уведомим реферала
            if ref_user_id:
                await bot.send_message(
                    int(ref_user_id),
                    f"🎉 Ура! Пользователь {uname} оплатил подписку.\n"
                    f"💰 Тебе начислено <b>+{fmt_cur(bonus)}</b> бонусов (25% от суммы)."
                )
        except Exception as e:
            log.error(f"Ошибка начисления бонуса рефералу {ref_source}: {e}")

    # сообщение покупателю
    await call.message.answer(
        "✅ Оплата прошла успешно!\n\n"
        f"Вот ссылка для вступления в закрытую группу:\n{CLOSED_CHAT_LINK}"
    )
    await call.answer()

# --- Проверка подписки ---
@dp.callback_query(F.data.startswith("checksub:"))
async def check_subscription(call: types.CallbackQuery):
    ref = call.data.split(":")[1]
    user = call.from_user
    results = []

    try:
        member = await bot.get_chat_member(OPEN_CHANNEL_ID, user.id)
        if member.status in ["member", "administrator", "creator"]:
            if ref and ref != "direct":
                append_user_event(user, ref, "subscribed", "channel", CHANNEL_BONUS)
                results.append(f"📢 Подписка на канал (+{CHANNEL_BONUS})")
    except Exception as e:
        log.warning(f"Не удалось проверить подписку в канале: {e}")

    try:
        member = await bot.get_chat_member(CLOSED_GROUP_ID, user.id)
        if member.status in ["member", "administrator", "creator"]:
            if ref and ref != "direct":
                append_user_event(user, ref, "subscribed", "group", GROUP_BONUS)
                results.append(f"👥 Вступление в группу (+{GROUP_BONUS})")
    except Exception as e:
        log.warning(f"Не удалось проверить вступление в группу: {e}")

    if results:
        await call.message.answer("🎉 Отлично! Бонусы зачислены.\n" + "\n".join(results))
    else:
        await call.message.answer("⛔️ Подписка не найдена. Убедись, что бот — админ канала/группы.")
    await call.answer()

# --- Инвайт (кнопка) ---
@dp.callback_query(F.data == "invitebtn")
async def on_invite_btn(call: types.CallbackQuery):
    ref_id = get_ref_id(call.from_user)
    me = await bot.me()
    bot_link = f"https://t.me/{me.username}?start={ref_id}"

    # пишем/обновляем InviteLinks
    rows = WS_LINKS.get_all_records()
    found = False
    for idx, r in enumerate(rows, start=2):
        if str(r["ref_id"]) == str(ref_id):
            WS_LINKS.update(values=[[bot_link, now()]], range_name=f"B{idx}:C{idx}")
            found = True
            break
    if not found:
        WS_LINKS.append_row([ref_id, bot_link, now(), call.from_user.full_name],
                            value_input_option="USER_ENTERED")

    text = (
        "👤 Твоя реферальная ссылка:\n\n"
        f"🔗 {bot_link}\n\n"
        "Приглашай подруг и получай бонусы!\n\n"
        "❗️Важно: бонусы начисляются только после подписки."
    )

    await bot.send_message(call.from_user.id, text)
    await call.answer()


# --- /mystats (для юзера: личная статистика; для админа: сводка по выручке/комиссиям) ---
@dp.message(Command("mystats"))
async def mystats(m: Message):
    user = m.from_user
    args = m.text.split()
    period_arg = args[1] if len(args) > 1 else None
    filter_from = parse_period(period_arg) if period_arg else None

    # если админ
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

        lines = [f"📈 <b>Сводка ({period_arg or 'all'})</b>",
                 f"💵 Выручка: <b>{fmt_cur(total_revenue)}₽</b>",
                 f"🤝 Комиссии (25%): <b>{fmt_cur(total_commissions)}</b>"]

        lines.append("\n📦 По тарифам:")
        for t, s in sorted(by_tariff.items(), key=lambda x: -x[1]):
            lines.append(f" • {t}: {fmt_cur(s)}₽")

        if by_referrer:
            lines.append("\n🏆 ТОП-рефералы:")
            for i, (r, s) in enumerate(sorted(by_referrer.items(), key=lambda x: -x[1])[:10], 1):
                lines.append(f"{i}. {r} — {fmt_cur(s)}₽")
        else:
            lines.append("\n🏆 ТОП-рефералы: пока нет")

        return await m.answer("\n".join(lines))

    # обычный пользователь — личная статистика
    ref_id = get_ref_id(user)
    rows = WS_USERS.get_all_records()

    invited = []
    total_bonus = 0
    for r in rows:
        if str(r.get("ref_source", "")) == ref_id and int(r.get("bonus", 0)) > 0:
            uname = f"@{r['username']}" if r["username"] else r["full_name"]
            invited.append(f"{r['timestamp']} — {uname} — {r['object']} (+{r['bonus']})")
            total_bonus += int(r["bonus"])

    stats_text = "\n".join(invited) if invited else "Пока никто не пришёл по твоей ссылке."
    await m.answer(f"📊 Моя статистика:\n\n{stats_text}\n\n💎 Суммарные бонусы: {fmt_cur(total_bonus)}")

# --- Debug подписки ---
@dp.message(Command("debugsub"))
async def debugsub(m: Message):
    user = m.from_user
    text = [f"🔎 Проверка подписки для {user.full_name} (@{user.username or 'без username'})"]

    try:
        member = await bot.get_chat_member(OPEN_CHANNEL_ID, user.id)
        text.append(f"📢 Канал: {member.status}")
    except Exception as e:
        text.append(f"📢 Канал: ошибка — {e}")

    try:
        member = await bot.get_chat_member(CLOSED_GROUP_ID, user.id)
        text.append(f"👥 Группа: {member.status}")
    except Exception as e:
        text.append(f"👥 Группа: ошибка — {e}")

    await m.answer("\n".join(text))

# ================== Мониторинг Payments: новые строки -> в админ-чат ==================
async def monitor_payments():
    """
    Периодически ищем строки, у которых notified != 'yes',
    шлём уведомление в админ-чат и помечаем их как notified.
    Это работает и для внешних добавлений строк.
    """
    while True:
        try:
            values = WS_PAYMENTS.get_all_values()  # список списков
            if len(values) >= 2:
                headers = values[0]
                col_map = {h: i for i, h in enumerate(headers)}
                # ожидаем, что есть колонка 'notified'
                notified_idx = col_map.get("notified")
                for row_idx in range(1, len(values)):  # начиная со второй строки
                    row = values[row_idx]
                    if notified_idx is None or notified_idx >= len(row) or row[notified_idx].strip().lower() != "yes":
                        # новая/неуведомлённая запись
                        ts = row[col_map.get("timestamp", 0)] if col_map.get("timestamp", None) is not None else ""
                        uname = row[col_map.get("username", 2)] if len(row) > 2 else ""
                        fulln = row[col_map.get("full_name", 3)] if len(row) > 3 else ""
                        tariff = row[col_map.get("tariff", 4)] if len(row) > 4 else ""
                        price = row[col_map.get("price", 5)] if len(row) > 5 else "0"
                        ref = row[col_map.get("ref_source", 8)] if len(row) > 8 else ""

                        buyer = f"@{uname}" if uname else fulln or "—"
                        text = (f"💳 <b>Оплата (новая строка)</b>\n"
                                f"🕒 {ts}\n"
                                f"👤 {buyer}\n"
                                f"📦 {tariff}\n"
                                f"💵 {price}₽\n"
                                f"👥 Реферал: {ref or '—'}")
                        await notify_admin_text(text)

                        # помечаем как notified
                        if notified_idx is not None:
                            WS_PAYMENTS.update_cell(row_idx + 1, notified_idx + 1, "yes")
                        else:
                            # если почему-то нет колонки — добавим
                            WS_PAYMENTS.update(f"J1", [["notified"]])
                            WS_PAYMENTS.update_cell(row_idx + 1, 10, "yes")
        except Exception as e:
            log.warning(f"monitor_payments error: {e}")

        await asyncio.sleep(20)  # каждые 20 сек

from aiogram.types import FSInputFile  # убедись, что импорт есть сверху

@dp.callback_query(F.data == "trainer_bukina")
async def trainer_bukina(call: types.CallbackQuery):
    caption = (
    "👩‍🏫 <b>Мария Букина — тренер по естественному омоложению</b>\n\n"
    "Дипломированный специалист по фейс-фитнесу и естественному омоложению лица и тела. "
    "С 2017 года помогает женщинам сохранять молодость без уколов и пластики.\n\n"
    "✨ Член Международной ассоциации фейс-фитнеса\n"
    "✨ Автор курсов и программ по омоложению\n"
    "✨ Практик с личным опытом восстановления после рождения третьего ребёнка\n\n"
    "«Я уверена: естественная красота — это не тренд, а новый стандарт»"
    )
    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bukina.jpg")
    if os.path.exists(img_path):
        photo = FSInputFile(img_path, filename="bukina.jpg")
        await call.message.answer_photo(photo, caption=caption)
    else:
        await call.message.answer(caption + "\n\n⚠️ Фото bukina.jpg не найдено в корне проекта.")
    await call.answer()

@dp.message(Command("channel"))
async def channel_cmd(m: Message):
    await m.answer("📢 Наш открытый канал:\nhttps://t.me/PRIDEyouthClubChannel")

@dp.message(Command("subscribe"))
async def subscribe_cmd(m: Message):
    text = (
        "🔒 Членство в закрытой группе стоит <b>990₽/мес</b>.\n\n"
        "Выберите тариф 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц — 990₽", callback_data="pay:1")],
        [InlineKeyboardButton(text="3 месяца — 2673₽ (-10%)", callback_data="pay:3")],
        [InlineKeyboardButton(text="12 месяцев — 8910₽ (-25%)", callback_data="pay:12")],
    ])
    await m.answer(text, reply_markup=kb)


# ================== YOOKASSA PAYMENT HANDLERS ==================
@dp.callback_query(F.data.startswith("pay:"))
async def process_payment(call: types.CallbackQuery):
    """Создание платежа в YooKassa"""
    period = call.data.split(":")[1]

    # Определяем цену и описание
    if period == "1":
        price = 990
        label = "1 месяц"
    elif period == "3":
        price = 2673
        label = "3 месяца (-10%)"
    else:
        price = 8910
        label = "12 месяцев (-25%)"

    try:
        # Создаём платёж в YooKassa
        idempotence_key = str(uuid.uuid4())
        payment = Payment.create({
            "amount": {
                "value": f"{price:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/PRIDEyouthClub_bot"
            },
            "capture": True,
            "description": f"Подписка Pride YouthClub - {label}",
            "metadata": {
                "user_id": str(call.from_user.id),
                "username": call.from_user.username or "",
                "period": period,
                "tariff": label
            }
        }, idempotence_key)

        log.info(f"Payment created: {payment.id} for user {call.from_user.id}, amount {price}")

        # Логируем в Google Sheets со статусом "pending"
        log_payment(call.from_user, label, price, period, None, "pending")

        # Отправляем пользователю ссылку на оплату
        text = (
            f"💳 Тариф: {label}\n"
            f"Сумма: {fmt_cur(price)}₽\n\n"
            f"🔗 Перейдите по ссылке для оплаты через ЮKassa:\n"
            f"{payment.confirmation.confirmation_url}\n\n"
            f"После оплаты вы автоматически получите доступ к закрытой группе."
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить через ЮKassa", url=payment.confirmation.confirmation_url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_payment:{payment.id}")]
        ])

        await call.message.answer(text, reply_markup=kb)
        await call.answer()

    except Exception as e:
        log.error(f"Error creating payment: {e}")
        await call.message.answer(
            "❌ Ошибка при создании платежа. Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )
        await call.answer()


@dp.callback_query(F.data.startswith("check_payment:"))
async def check_payment(call: types.CallbackQuery):
    """Проверка статуса платежа"""
    payment_id = call.data.split(":", 1)[1]

    try:
        payment = Payment.find_one(payment_id)

        if payment.status == "succeeded" and payment.paid:
            # Платёж успешен
            metadata = payment.metadata
            period = metadata.get("period", "1")
            tariff = metadata.get("tariff", "1 месяц")
            price = float(payment.amount.value)

            # Обновляем статус в Google Sheets
            log_payment(call.from_user, tariff, int(price), period, None, "success")

            # Определяем реферера
            rows = WS_USERS.get_all_records()
            ref_source = None
            for r in reversed(rows):
                if str(r.get("user_id")) == str(call.from_user.id) and r.get("ref_source") and r["ref_source"] != "direct":
                    ref_source = r["ref_source"]
                    break

            # Уведомление в админ-чат
            uname = f"@{call.from_user.username}" if call.from_user.username else call.from_user.full_name
            admin_text = (
                f"💳 <b>Оплата успешна!</b>\n"
                f"👤 Покупатель: {uname}\n"
                f"Тариф: {tariff}\n"
                f"Сумма: <b>{fmt_cur(int(price))}₽</b>\n"
                f"Реферал: {ref_source if ref_source else '—'}\n"
                f"Payment ID: {payment_id}"
            )
            await notify_admin_text(admin_text)

            # Начисляем бонус рефералу (25%)
            if ref_source:
                ref_user_id, ref_username = get_user_id_by_ref(ref_source)
                try:
                    bonus = int(price * 0.25)
                    log_referrer_bonus(ref_user_id or ref_source, ref_username or (ref_source if ref_source.startswith("@") else ""), bonus, f"Комиссия 25% от оплаты {tariff}")
                    update_bonuses(ref_source, bonus)

                    if ref_user_id:
                        await bot.send_message(
                            int(ref_user_id),
                            f"🎉 Ура! Пользователь {uname} оплатил подписку.\n"
                            f"💰 Тебе начислено <b>+{fmt_cur(bonus)}</b> бонусов (25% от суммы)."
                        )
                except Exception as e:
                    log.error(f"Ошибка начисления бонуса рефералу {ref_source}: {e}")

            # Отправляем покупателю ссылку на группу
            await call.message.answer(
                "✅ Оплата прошла успешно!\n\n"
                f"Вот ссылка для вступления в закрытую группу:\n{CLOSED_CHAT_LINK}\n\n"
                "Добро пожаловать в Pride YouthClub! 🎉"
            )
            await call.answer("Оплата подтверждена ✅")

        elif payment.status == "canceled":
            await call.message.answer("❌ Платёж отменён.")
            await call.answer("Платёж отменён")

        elif payment.status == "pending":
            await call.message.answer("⏳ Платёж ещё обрабатывается. Попробуйте проверить позже.")
            await call.answer("Платёж в обработке...")

        else:
            await call.message.answer(f"ℹ️ Статус платежа: {payment.status}")
            await call.answer()

    except Exception as e:
        log.error(f"Error checking payment {payment_id}: {e}")
        await call.message.answer("❌ Ошибка проверки платежа. Попробуйте позже.")
        await call.answer()


# ================== MAIN ==================
async def main():
    user_cmds = [
        BotCommand(command="invite", description="Мои ссылки"),
        BotCommand(command="mystats", description="Моя статистика"),
        BotCommand(command="trainers", description="О тренерах"),
        BotCommand(command="channel", description="Канал Клуб Омоложения"),   # ← новое
        BotCommand(command="subscribe", description="Подписка на закрытую группу"),  # ← новое
    ]
    await bot.set_my_commands(user_cmds)

    admin_cmds = user_cmds + [
        BotCommand(command="top", description="Рейтинг ТОП-10"),
    ]
    for admin_id in ADMINS:
        if isinstance(admin_id, int):
            try:
                await bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                log.warning(f"Не удалось установить команды для {admin_id}: {e}")

    # фон: мониторинг листа Payments
    asyncio.create_task(monitor_payments())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
