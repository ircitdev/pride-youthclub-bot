"""Сервис для работы с Google Sheets."""
import gspread
from google.oauth2.service_account import Credentials
from bot.config import SPREADSHEET_ID, SERVICE_JSON_PATH, log


def init_sheets():
    """
    Инициализирует подключение к Google Sheets и создает необходимые таблицы.

    Returns:
        gspread.Spreadsheet: Объект таблицы Google Sheets

    Raises:
        FileNotFoundError: Если файл service account не найден
        Exception: При ошибках подключения к Google Sheets API
    """
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(SERVICE_JSON_PATH, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)

        # Авто-создание вкладок
        for ws_name in ["Users", "InviteLinks", "Bonuses", "Payments"]:
            try:
                sh.worksheet(ws_name)
            except gspread.WorksheetNotFound:
                log.info(f"Создание вкладки {ws_name}")
                sh.add_worksheet(ws_name, 1000, 10)

        # Инициализация заголовков Users
        ws_users = sh.worksheet("Users")
        if not ws_users.cell(1, 1).value:
            ws_users.update("A1:H1", [[
                "timestamp", "user_id", "username", "full_name",
                "ref_source", "action", "object", "bonus"
            ]])
            log.info("Инициализированы заголовки Users")

        # Инициализация заголовков InviteLinks
        ws_links = sh.worksheet("InviteLinks")
        headers = ["ref_id", "bot_link", "created_at", "created_by"]
        first_row = ws_links.row_values(1)
        if first_row != headers:
            ws_links.clear()
            ws_links.update("A1:D1", [headers])
            log.info("Инициализированы заголовки InviteLinks")

        # Инициализация заголовков Bonuses
        ws_bonuses = sh.worksheet("Bonuses")
        if not ws_bonuses.cell(1, 1).value:
            ws_bonuses.update("A1:D1", [[
                "ref_id", "total_refs", "total_bonus", "updated_at"
            ]])
            log.info("Инициализированы заголовки Bonuses")

        # Инициализация заголовков Payments
        ws_payments = sh.worksheet("Payments")
        pay_headers = [
            "timestamp", "user_id", "username", "full_name",
            "tariff", "price", "period", "status", "ref_source", "notified"
        ]
        first_row = ws_payments.row_values(1)
        if first_row != pay_headers:
            ws_payments.clear()
            ws_payments.update("A1:J1", [pay_headers])
            log.info("Инициализированы заголовки Payments")

        log.info("Google Sheets успешно инициализированы")
        return sh

    except FileNotFoundError:
        log.error(f"Файл {SERVICE_JSON_PATH} не найден!")
        raise
    except Exception as e:
        log.error(f"Ошибка инициализации Google Sheets: {e}")
        raise


# Глобальные объекты таблиц
SHEETS = init_sheets()
WS_USERS = SHEETS.worksheet("Users")
WS_LINKS = SHEETS.worksheet("InviteLinks")
WS_BONUSES = SHEETS.worksheet("Bonuses")
WS_PAYMENTS = SHEETS.worksheet("Payments")
