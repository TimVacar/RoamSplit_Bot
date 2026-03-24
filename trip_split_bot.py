import asyncio
import logging
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

import psycopg
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
DEFAULT_TRIP_CURRENCY = os.getenv("DEFAULT_TRIP_CURRENCY", "EUR")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["en", "ru", "ro", "it", "fr", "es"]
EXPENSE_CATEGORIES = [
    "food",
    "cafe",
    "transport",
    "hotel",
    "tickets",
    "shopping",
    "entertainment",
    "groceries",
    "transfer",
    "excursions",
    "other",
]

PENDING_INPUTS: dict[int, dict] = {}


TRANSLATIONS = {
    "en": {
        "welcome": "Hi. I help groups track trip expenses and settlements.",
        "choose_language": "Choose your language:",
        "main_menu": "Main menu",
        "create_trip": "Create trip",
        "my_trips": "My trips",
        "join_trip": "Join trip",
        "open_trip": "Open trip",
        "language": "Language",
        "help": "Help",
        "trip_created": "Trip created successfully.",
        "enter_trip_name": "Send trip name.",
        "enter_trip_currency": "Send trip currency. Example: EUR",
        "choose_trip_language": "Choose trip language:",
        "no_trips": "You have no trips yet.",
        "unknown": "I didn't understand that. Use menu buttons.",
        "help_text": "MVP actions: create trip, join by ID, open trip, add expense, view members, list expenses, calculate debts.",
        "enter_trip_id": "Send trip ID. Example: 1",
        "trip_not_found": "Trip not found.",
        "already_member": "You are already a member of this trip.",
        "joined_trip": "You joined the trip:",
        "trip_opened": "Trip opened:",
        "not_member": "You are not a member of this trip.",
        "trip_menu": "Trip menu",
        "add_expense": "Add expense",
        "members": "Members",
        "expenses": "Expenses",
        "calculate": "Calculate debts",
        "back": "Back",
        "enter_amount": "Send expense amount. Example: 25.50",
        "choose_category": "Choose expense category:",
        "send_note": "Send comment or type 0 to skip.",
        "choose_split": "How to split this expense?",
        "split_all": "Split across all members",
        "split_selected": "Choose members manually",
        "send_member_ids": "Send Telegram IDs of members separated by commas. Example: 12345,67890",
        "expense_saved": "Expense saved.",
        "no_members": "No members found.",
        "members_title": "Trip members",
        "expenses_title": "Trip expenses",
        "no_expenses": "No expenses yet.",
        "debts_title": "Settlement result",
        "nobody_owes": "Nobody owes anyone anything.",
        "active_trip_missing": "Open a trip first.",
        "active_trip_cleared": "Returned to main menu.",
        "your_trip_ids": "Use the trip ID from My trips or from the creation confirmation.",
        "balances": "Balances",
        "who_owes": "Who owes whom",
        "invalid_amount": "Invalid amount. Example: 25.50",
    },
    "ru": {
        "welcome": "Привет. Я помогаю группам вести расходы в поездках и взаиморасчёты.",
        "choose_language": "Выбери язык:",
        "main_menu": "Главное меню",
        "create_trip": "Создать поездку",
        "my_trips": "Мои поездки",
        "join_trip": "Вступить в поездку",
        "open_trip": "Открыть поездку",
        "language": "Язык",
        "help": "Помощь",
        "trip_created": "Поездка успешно создана.",
        "enter_trip_name": "Отправь название поездки.",
        "enter_trip_currency": "Отправь валюту поездки. Например: EUR",
        "choose_trip_language": "Выбери язык поездки:",
        "no_trips": "У тебя пока нет поездок.",
        "unknown": "Не понял сообщение. Используй кнопки меню.",
        "help_text": "MVP-действия: создать поездку, вступить по ID, открыть поездку, добавить расход, посмотреть участников, расходы и расчёт долгов.",
        "enter_trip_id": "Введи ID поездки. Например: 1",
        "trip_not_found": "Поездка не найдена.",
        "already_member": "Ты уже состоишь в этой поездке.",
        "joined_trip": "Ты вступил в поездку:",
        "trip_opened": "Поездка открыта:",
        "not_member": "Ты не состоишь в этой поездке.",
        "trip_menu": "Меню поездки",
        "add_expense": "Добавить расход",
        "members": "Участники",
        "expenses": "Расходы",
        "calculate": "Рассчитать долги",
        "back": "Назад",
        "enter_amount": "Введи сумму расхода. Например: 25.50",
        "choose_category": "Выбери категорию расхода:",
        "send_note": "Отправь комментарий или 0, чтобы пропустить.",
        "choose_split": "Как разделить этот расход?",
        "split_all": "Делить на всех",
        "split_selected": "Выбрать участников вручную",
        "send_member_ids": "Отправь Telegram ID участников через запятую. Например: 12345,67890",
        "expense_saved": "Расход сохранён.",
        "no_members": "Участники не найдены.",
        "members_title": "Участники поездки",
        "expenses_title": "Расходы поездки",
        "no_expenses": "Пока нет расходов.",
        "debts_title": "Результат расчёта",
        "nobody_owes": "Никто никому не должен.",
        "active_trip_missing": "Сначала открой поездку.",
        "active_trip_cleared": "Вернулись в главное меню.",
        "your_trip_ids": "Используй ID из раздела «Мои поездки» или из сообщения после создания.",
        "balances": "Балансы",
        "who_owes": "Кто кому должен",
        "invalid_amount": "Некорректная сумма. Например: 25.50",
    },
    "ro": {
        "welcome": "Hi. I help groups track trip expenses and settlements.",
        "choose_language": "Choose your language:",
        "main_menu": "Main menu",
        "create_trip": "Create trip",
        "my_trips": "My trips",
        "join_trip": "Join trip",
        "open_trip": "Open trip",
        "language": "Language",
        "help": "Help",
        "trip_created": "Trip created successfully.",
        "enter_trip_name": "Send trip name.",
        "enter_trip_currency": "Send trip currency. Example: EUR",
        "choose_trip_language": "Choose trip language:",
        "no_trips": "You have no trips yet.",
        "unknown": "I didn't understand that. Use menu buttons.",
        "help_text": "MVP actions: create trip, join by ID, open trip, add expense, view members, list expenses, calculate debts.",
        "enter_trip_id": "Send trip ID. Example: 1",
        "trip_not_found": "Trip not found.",
        "already_member": "You are already a member of this trip.",
        "joined_trip": "You joined the trip:",
        "trip_opened": "Trip opened:",
        "not_member": "You are not a member of this trip.",
        "trip_menu": "Trip menu",
        "add_expense": "Add expense",
        "members": "Members",
        "expenses": "Expenses",
        "calculate": "Calculate debts",
        "back": "Back",
        "enter_amount": "Send expense amount. Example: 25.50",
        "choose_category": "Choose expense category:",
        "send_note": "Send comment or type 0 to skip.",
        "choose_split": "How to split this expense?",
        "split_all": "Split across all members",
        "split_selected": "Choose members manually",
        "send_member_ids": "Send Telegram IDs of members separated by commas. Example: 12345,67890",
        "expense_saved": "Expense saved.",
        "no_members": "No members found.",
        "members_title": "Trip members",
        "expenses_title": "Trip expenses",
        "no_expenses": "No expenses yet.",
        "debts_title": "Settlement result",
        "nobody_owes": "Nobody owes anyone anything.",
        "active_trip_missing": "Open a trip first.",
        "active_trip_cleared": "Returned to main menu.",
        "your_trip_ids": "Use the trip ID from My trips or from the creation confirmation.",
        "balances": "Balances",
        "who_owes": "Who owes whom",
        "invalid_amount": "Invalid amount. Example: 25.50",
    },
    "it": {
        "welcome": "Hi. I help groups track trip expenses and settlements.",
        "choose_language": "Choose your language:",
        "main_menu": "Main menu",
        "create_trip": "Create trip",
        "my_trips": "My trips",
        "join_trip": "Join trip",
        "open_trip": "Open trip",
        "language": "Language",
        "help": "Help",
        "trip_created": "Trip created successfully.",
        "enter_trip_name": "Send trip name.",
        "enter_trip_currency": "Send trip currency. Example: EUR",
        "choose_trip_language": "Choose trip language:",
        "no_trips": "You have no trips yet.",
        "unknown": "I didn't understand that. Use menu buttons.",
        "help_text": "MVP actions: create trip, join by ID, open trip, add expense, view members, list expenses, calculate debts.",
        "enter_trip_id": "Send trip ID. Example: 1",
        "trip_not_found": "Trip not found.",
        "already_member": "You are already a member of this trip.",
        "joined_trip": "You joined the trip:",
        "trip_opened": "Trip opened:",
        "not_member": "You are not a member of this trip.",
        "trip_menu": "Trip menu",
        "add_expense": "Add expense",
        "members": "Members",
        "expenses": "Expenses",
        "calculate": "Calculate debts",
        "back": "Back",
        "enter_amount": "Send expense amount. Example: 25.50",
        "choose_category": "Choose expense category:",
        "send_note": "Send comment or type 0 to skip.",
        "choose_split": "How to split this expense?",
        "split_all": "Split across all members",
        "split_selected": "Choose members manually",
        "send_member_ids": "Send Telegram IDs of members separated by commas. Example: 12345,67890",
        "expense_saved": "Expense saved.",
        "no_members": "No members found.",
        "members_title": "Trip members",
        "expenses_title": "Trip expenses",
        "no_expenses": "No expenses yet.",
        "debts_title": "Settlement result",
        "nobody_owes": "Nobody owes anyone anything.",
        "active_trip_missing": "Open a trip first.",
        "active_trip_cleared": "Returned to main menu.",
        "your_trip_ids": "Use the trip ID from My trips or from the creation confirmation.",
        "balances": "Balances",
        "who_owes": "Who owes whom",
        "invalid_amount": "Invalid amount. Example: 25.50",
    },
    "fr": {
        "welcome": "Hi. I help groups track trip expenses and settlements.",
        "choose_language": "Choose your language:",
        "main_menu": "Main menu",
        "create_trip": "Create trip",
        "my_trips": "My trips",
        "join_trip": "Join trip",
        "open_trip": "Open trip",
        "language": "Language",
        "help": "Help",
        "trip_created": "Trip created successfully.",
        "enter_trip_name": "Send trip name.",
        "enter_trip_currency": "Send trip currency. Example: EUR",
        "choose_trip_language": "Choose trip language:",
        "no_trips": "You have no trips yet.",
        "unknown": "I didn't understand that. Use menu buttons.",
        "help_text": "MVP actions: create trip, join by ID, open trip, add expense, view members, list expenses, calculate debts.",
        "enter_trip_id": "Send trip ID. Example: 1",
        "trip_not_found": "Trip not found.",
        "already_member": "You are already a member of this trip.",
        "joined_trip": "You joined the trip:",
        "trip_opened": "Trip opened:",
        "not_member": "You are not a member of this trip.",
        "trip_menu": "Trip menu",
        "add_expense": "Add expense",
        "members": "Members",
        "expenses": "Expenses",
        "calculate": "Calculate debts",
        "back": "Back",
        "enter_amount": "Send expense amount. Example: 25.50",
        "choose_category": "Choose expense category:",
        "send_note": "Send comment or type 0 to skip.",
        "choose_split": "How to split this expense?",
        "split_all": "Split across all members",
        "split_selected": "Choose members manually",
        "send_member_ids": "Send Telegram IDs of members separated by commas. Example: 12345,67890",
        "expense_saved": "Expense saved.",
        "no_members": "No members found.",
        "members_title": "Trip members",
        "expenses_title": "Trip expenses",
        "no_expenses": "No expenses yet.",
        "debts_title": "Settlement result",
        "nobody_owes": "Nobody owes anyone anything.",
        "active_trip_missing": "Open a trip first.",
        "active_trip_cleared": "Returned to main menu.",
        "your_trip_ids": "Use the trip ID from My trips or from the creation confirmation.",
        "balances": "Balances",
        "who_owes": "Who owes whom",
        "invalid_amount": "Invalid amount. Example: 25.50",
    },
    "es": {
        "welcome": "Hi. I help groups track trip expenses and settlements.",
        "choose_language": "Choose your language:",
        "main_menu": "Main menu",
        "create_trip": "Create trip",
        "my_trips": "My trips",
        "join_trip": "Join trip",
        "open_trip": "Open trip",
        "language": "Language",
        "help": "Help",
        "trip_created": "Trip created successfully.",
        "enter_trip_name": "Send trip name.",
        "enter_trip_currency": "Send trip currency. Example: EUR",
        "choose_trip_language": "Choose trip language:",
        "no_trips": "You have no trips yet.",
        "unknown": "I didn't understand that. Use menu buttons.",
        "help_text": "MVP actions: create trip, join by ID, open trip, add expense, view members, list expenses, calculate debts.",
        "enter_trip_id": "Send trip ID. Example: 1",
        "trip_not_found": "Trip not found.",
        "already_member": "You are already a member of this trip.",
        "joined_trip": "You joined the trip:",
        "trip_opened": "Trip opened:",
        "not_member": "You are not a member of this trip.",
        "trip_menu": "Trip menu",
        "add_expense": "Add expense",
        "members": "Members",
        "expenses": "Expenses",
        "calculate": "Calculate debts",
        "back": "Back",
        "enter_amount": "Send expense amount. Example: 25.50",
        "choose_category": "Choose expense category:",
        "send_note": "Send comment or type 0 to skip.",
        "choose_split": "How to split this expense?",
        "split_all": "Split across all members",
        "split_selected": "Choose members manually",
        "send_member_ids": "Send Telegram IDs of members separated by commas. Example: 12345,67890",
        "expense_saved": "Expense saved.",
        "no_members": "No members found.",
        "members_title": "Trip members",
        "expenses_title": "Trip expenses",
        "no_expenses": "No expenses yet.",
        "debts_title": "Settlement result",
        "nobody_owes": "Nobody owes anyone anything.",
        "active_trip_missing": "Open a trip first.",
        "active_trip_cleared": "Returned to main menu.",
        "your_trip_ids": "Use the trip ID from My trips or from the creation confirmation.",
        "balances": "Balances",
        "who_owes": "Who owes whom",
        "invalid_amount": "Invalid amount. Example: 25.50",
    },
}


@dataclass
class TripCreateDraft:
    title: str
    currency: str
    trip_language: str


def t(lang: str, key: str) -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


def parse_amount(raw: str) -> Decimal:
    cleaned = raw.replace(",", ".").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("invalid") from exc
    if value <= 0:
        raise ValueError("invalid")
    return value.quantize(Decimal("0.01"))


class TripDB:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._init_db()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def _init_db(self):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_user_id BIGINT UNIQUE NOT NULL,
                    display_name TEXT,
                    username TEXT,
                    language_code TEXT NOT NULL DEFAULT 'en',
                    active_trip_id BIGINT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS trips (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    base_currency TEXT NOT NULL DEFAULT 'EUR',
                    trip_language TEXT NOT NULL DEFAULT 'en',
                    created_by_user_id BIGINT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS trip_members (
                    id BIGSERIAL PRIMARY KEY,
                    trip_id BIGINT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    UNIQUE (trip_id, user_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id BIGSERIAL PRIMARY KEY,
                    trip_id BIGINT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                    payer_user_id BIGINT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    currency TEXT NOT NULL,
                    category TEXT NOT NULL,
                    note TEXT DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS expense_participants (
                    id BIGSERIAL PRIMARY KEY,
                    expense_id BIGINT NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL
                )
                """
            )
            conn.commit()

    def upsert_user(self, telegram_user_id: int, display_name: str, username: Optional[str], language_code: str):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (telegram_user_id, display_name, username, language_code)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telegram_user_id)
                DO UPDATE SET display_name = EXCLUDED.display_name,
                              username = EXCLUDED.username
                """,
                (telegram_user_id, display_name, username, language_code),
            )
            conn.commit()

    def set_user_language(self, telegram_user_id: int, language_code: str):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET language_code = %s WHERE telegram_user_id = %s",
                (language_code, telegram_user_id),
            )
            conn.commit()

    def get_user_language(self, telegram_user_id: int) -> str:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT language_code FROM users WHERE telegram_user_id = %s LIMIT 1",
                (telegram_user_id,),
            )
            row = cur.fetchone()
            return row[0] if row else "en"

    def set_active_trip(self, telegram_user_id: int, trip_id: Optional[int]):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET active_trip_id = %s WHERE telegram_user_id = %s",
                (trip_id, telegram_user_id),
            )
            conn.commit()

    def get_active_trip(self, telegram_user_id: int) -> Optional[int]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT active_trip_id FROM users WHERE telegram_user_id = %s LIMIT 1",
                (telegram_user_id,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None

    def create_trip(self, owner_user_id: int, draft: TripCreateDraft) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trips (title, base_currency, trip_language, created_by_user_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (draft.title, draft.currency, draft.trip_language, owner_user_id),
            )
            trip_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO trip_members (trip_id, user_id, role)
                VALUES (%s, %s, 'admin')
                ON CONFLICT (trip_id, user_id) DO NOTHING
                """,
                (trip_id, owner_user_id),
            )
            conn.commit()
            return trip_id

    def fetch_user_trips(self, user_id: int):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id, t.title, t.base_currency, t.trip_language, t.status, t.created_at
                FROM trips t
                JOIN trip_members tm ON tm.trip_id = t.id
                WHERE tm.user_id = %s AND tm.is_active = TRUE
                ORDER BY t.created_at DESC
                """,
                (user_id,),
            )
            return cur.fetchall()

    def get_trip_by_id(self, trip_id: int):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, base_currency, trip_language, status, created_at
                FROM trips
                WHERE id = %s
                LIMIT 1
                """,
                (trip_id,),
            )
            return cur.fetchone()

    def add_trip_member(self, trip_id: int, user_id: int, role: str = "member") -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trip_members (trip_id, user_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (trip_id, user_id)
                DO UPDATE SET is_active = TRUE
                """,
                (trip_id, user_id, role),
            )
            conn.commit()
            return True

    def is_trip_member(self, trip_id: int, user_id: int) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM trip_members
                WHERE trip_id = %s AND user_id = %s AND is_active = TRUE
                LIMIT 1
                """,
                (trip_id, user_id),
            )
            return cur.fetchone() is not None

    def fetch_trip_members(self, trip_id: int):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.telegram_user_id, COALESCE(u.display_name, u.username, u.telegram_user_id::text), tm.role
                FROM trip_members tm
                JOIN users u ON u.telegram_user_id = tm.user_id
                WHERE tm.trip_id = %s AND tm.is_active = TRUE
                ORDER BY tm.joined_at ASC
                """,
                (trip_id,),
            )
            return cur.fetchall()

    def fetch_trip_member_ids(self, trip_id: int):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id
                FROM trip_members
                WHERE trip_id = %s AND is_active = TRUE
                ORDER BY joined_at ASC
                """,
                (trip_id,),
            )
            return [row[0] for row in cur.fetchall()]

    def add_expense(self, trip_id: int, payer_user_id: int, amount: Decimal, currency: str, category: str, note: str) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO expenses (trip_id, payer_user_id, amount, currency, category, note)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (trip_id, payer_user_id, amount, currency, category, note),
            )
            expense_id = cur.fetchone()[0]
            conn.commit()
            return expense_id

    def add_expense_participants(self, expense_id: int, participant_ids: list[int]):
        with self._connect() as conn, conn.cursor() as cur:
            for user_id in participant_ids:
                cur.execute(
                    "INSERT INTO expense_participants (expense_id, user_id) VALUES (%s, %s)",
                    (expense_id, user_id),
                )
            conn.commit()

    def fetch_trip_expenses(self, trip_id: int):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    e.id,
                    e.payer_user_id,
                    e.amount,
                    e.currency,
                    e.category,
                    e.note,
                    e.created_at,
                    COALESCE(u.display_name, u.username, u.telegram_user_id::text) AS payer_name
                FROM expenses e
                LEFT JOIN users u ON u.telegram_user_id = e.payer_user_id
                WHERE e.trip_id = %s
                ORDER BY e.created_at DESC
                """,
                (trip_id,),
            )
            return cur.fetchall()

    def fetch_expense_participants(self, expense_id: int):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT ep.user_id, COALESCE(u.display_name, u.username, u.telegram_user_id::text)
                FROM expense_participants ep
                LEFT JOIN users u ON u.telegram_user_id = ep.user_id
                WHERE ep.expense_id = %s
                ORDER BY ep.id ASC
                """,
                (expense_id,),
            )
            return cur.fetchall()


def language_keyboard():
    builder = InlineKeyboardBuilder()
    for lang in SUPPORTED_LANGUAGES:
        builder.button(text=lang.upper(), callback_data=f"lang:{lang}")
    builder.adjust(3)
    return builder.as_markup()


def trip_language_keyboard():
    builder = InlineKeyboardBuilder()
    for lang in SUPPORTED_LANGUAGES:
        builder.button(text=lang.upper(), callback_data=f"triplang:{lang}")
    builder.adjust(3)
    return builder.as_markup()


def main_menu_keyboard(lang: str):
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"✈️ {t(lang, 'create_trip')}")
    kb.button(text=f"🧳 {t(lang, 'my_trips')}")
    kb.button(text=f"🔗 {t(lang, 'join_trip')}")
    kb.button(text=f"📂 {t(lang, 'open_trip')}")
    kb.button(text=f"🌐 {t(lang, 'language')}")
    kb.button(text=f"❓ {t(lang, 'help')}")
    kb.adjust(2, 2, 2)
    return kb.as_markup(resize_keyboard=True)


def trip_menu_keyboard(lang: str):
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"➕ {t(lang, 'add_expense')}")
    kb.button(text=f"👥 {t(lang, 'members')}")
    kb.button(text=f"🧾 {t(lang, 'expenses')}")
    kb.button(text=f"💸 {t(lang, 'calculate')}")
    kb.button(text=f"◀️ {t(lang, 'back')}")
    kb.adjust(2, 2, 1)
    return kb.as_markup(resize_keyboard=True)


def category_keyboard():
    builder = InlineKeyboardBuilder()
    for cat in EXPENSE_CATEGORIES:
        builder.button(text=cat, callback_data=f"cat:{cat}")
    builder.adjust(2)
    return builder.as_markup()


def split_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "split_all"), callback_data="split:all")
    builder.button(text=t(lang, "split_selected"), callback_data="split:selected")
    builder.adjust(1)
    return builder.as_markup()


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = TripDB(DATABASE_URL)


def current_lang(user_id: int) -> str:
    return db.get_user_language(user_id)


def current_trip(user_id: int) -> Optional[int]:
    return db.get_active_trip(user_id)


def format_money(amount, currency: str) -> str:
    return f"{float(amount):,.2f} {currency}".replace(",", " ")


def calculate_settlements(expenses, expense_participants):
    balances: dict[int, float] = {}

    for expense in expenses:
        expense_id, payer_user_id, amount, currency, category, note, created_at, payer_name = expense
        amount_f = float(amount)
        participants = expense_participants.get(expense_id, [])
        if not participants:
            continue

        share = amount_f / len(participants)
        balances[payer_user_id] = balances.get(payer_user_id, 0.0) + amount_f

        for participant_user_id, participant_name in participants:
            balances[participant_user_id] = balances.get(participant_user_id, 0.0) - share

    creditors = []
    debtors = []

    for user_id, balance in balances.items():
        rounded = round(balance, 2)
        if rounded > 0:
            creditors.append([user_id, rounded])
        elif rounded < 0:
            debtors.append([user_id, abs(rounded)])

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    settlements = []
    i = 0
    j = 0

    while i < len(debtors) and j < len(creditors):
        debtor_id, debt_amount = debtors[i]
        creditor_id, credit_amount = creditors[j]

        transfer = min(debt_amount, credit_amount)
        transfer = round(transfer, 2)

        if transfer > 0:
            settlements.append((debtor_id, creditor_id, transfer))

        debtors[i][1] = round(debtors[i][1] - transfer, 2)
        creditors[j][1] = round(creditors[j][1] - transfer, 2)

        if debtors[i][1] <= 0:
            i += 1
        if creditors[j][1] <= 0:
            j += 1

    return balances, settlements


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_lang = "en"
    db.upsert_user(
        telegram_user_id=message.from_user.id,
        display_name=message.from_user.full_name,
        username=message.from_user.username,
        language_code=user_lang,
    )
    await message.answer(t(user_lang, "welcome"), reply_markup=main_menu_keyboard(user_lang))
    await message.answer(t(user_lang, "choose_language"), reply_markup=language_keyboard())


@dp.callback_query(F.data.startswith("lang:"))
async def language_callback(query: CallbackQuery):
    lang = query.data.split(":", 1)[1]
    db.set_user_language(query.from_user.id, lang)
    await query.answer("OK")
    await query.message.answer(t(lang, "main_menu"), reply_markup=main_menu_keyboard(lang))


@dp.message(F.text.startswith("🌐"))
async def language_button(message: Message):
    lang = current_lang(message.from_user.id)
    await message.answer(t(lang, "choose_language"), reply_markup=language_keyboard())


@dp.message(F.text.startswith("✈️"))
async def create_trip_button(message: Message):
    lang = current_lang(message.from_user.id)
    PENDING_INPUTS[message.from_user.id] = {"flow": "create_trip", "step": "title"}
    await message.answer(t(lang, "enter_trip_name"), reply_markup=main_menu_keyboard(lang))


@dp.callback_query(F.data.startswith("triplang:"))
async def trip_language_callback(query: CallbackQuery):
    state = PENDING_INPUTS.get(query.from_user.id)
    lang = current_lang(query.from_user.id)

    if not state or state.get("flow") != "create_trip" or state.get("step") != "trip_language":
        await query.answer("Start trip creation first")
        return

    trip_lang = query.data.split(":", 1)[1]
    draft = TripCreateDraft(
        title=state["title"],
        currency=state["currency"],
        trip_language=trip_lang,
    )

    trip_id = db.create_trip(query.from_user.id, draft)
    db.set_active_trip(query.from_user.id, trip_id)
    PENDING_INPUTS.pop(query.from_user.id, None)

    await query.answer("OK")
    await query.message.answer(
        f"{t(lang, 'trip_created')}\nID: {trip_id}\n{draft.title} | {draft.currency} | {draft.trip_language.upper()}",
        reply_markup=trip_menu_keyboard(lang),
    )


@dp.message(F.text.startswith("🧳"))
async def my_trips_button(message: Message):
    lang = current_lang(message.from_user.id)
    trips = db.fetch_user_trips(message.from_user.id)

    if not trips:
        await message.answer(t(lang, "no_trips"), reply_markup=main_menu_keyboard(lang))
        return

    lines = [f"*{t(lang, 'my_trips')}*"]
    for trip_id, title, currency, trip_language, status, created_at in trips:
        lines.append(f"• #{trip_id} {title} | {currency} | {trip_language.upper()} | {status}")
    lines.append("")
    lines.append(t(lang, "your_trip_ids"))

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=main_menu_keyboard(lang))


@dp.message(F.text.startswith("🔗"))
async def join_trip_button(message: Message):
    lang = current_lang(message.from_user.id)
    PENDING_INPUTS[message.from_user.id] = {"flow": "join_trip", "step": "trip_id"}
    await message.answer(t(lang, "enter_trip_id"), reply_markup=main_menu_keyboard(lang))


@dp.message(F.text.startswith("📂"))
async def open_trip_button(message: Message):
    lang = current_lang(message.from_user.id)
    PENDING_INPUTS[message.from_user.id] = {"flow": "open_trip", "step": "trip_id"}
    await message.answer(t(lang, "enter_trip_id"), reply_markup=main_menu_keyboard(lang))


@dp.message(F.text.startswith("❓"))
async def help_button(message: Message):
    lang = current_lang(message.from_user.id)
    await message.answer(t(lang, "help_text"), reply_markup=main_menu_keyboard(lang))


@dp.message(F.text.startswith("➕"))
async def add_expense_button(message: Message):
    user_id = message.from_user.id
    lang = current_lang(user_id)
    trip_id = current_trip(user_id)

    if not trip_id:
        await message.answer(t(lang, "active_trip_missing"), reply_markup=main_menu_keyboard(lang))
        return

    PENDING_INPUTS[user_id] = {"flow": "add_expense", "step": "amount", "trip_id": trip_id}
    await message.answer(t(lang, "enter_amount"), reply_markup=trip_menu_keyboard(lang))


@dp.message(F.text.startswith("👥"))
async def members_button(message: Message):
    user_id = message.from_user.id
    lang = current_lang(user_id)
    trip_id = current_trip(user_id)

    if not trip_id:
        await message.answer(t(lang, "active_trip_missing"), reply_markup=main_menu_keyboard(lang))
        return

    members = db.fetch_trip_members(trip_id)
    if not members:
        await message.answer(t(lang, "no_members"), reply_markup=trip_menu_keyboard(lang))
        return

    lines = [f"*{t(lang, 'members_title')}*"]
    for member_user_id, member_name, role in members:
        lines.append(f"• {member_name} | ID: {member_user_id} | {role}")

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=trip_menu_keyboard(lang))


@dp.message(F.text.startswith("🧾"))
async def expenses_button(message: Message):
    user_id = message.from_user.id
    lang = current_lang(user_id)
    trip_id = current_trip(user_id)

    if not trip_id:
        await message.answer(t(lang, "active_trip_missing"), reply_markup=main_menu_keyboard(lang))
        return

    expenses = db.fetch_trip_expenses(trip_id)
    if not expenses:
        await message.answer(t(lang, "no_expenses"), reply_markup=trip_menu_keyboard(lang))
        return

    lines = [f"*{t(lang, 'expenses_title')}*"]
    for expense_id, payer_user_id, amount, currency, category, note, created_at, payer_name in expenses[:20]:
        lines.append(f"• #{expense_id} {format_money(amount, currency)} | {category} | paid by {payer_name}")
        if note:
            lines.append(f"  {note}")

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=trip_menu_keyboard(lang))


@dp.message(F.text.startswith("💸"))
async def calculate_button(message: Message):
    user_id = message.from_user.id
    lang = current_lang(user_id)
    trip_id = current_trip(user_id)

    if not trip_id:
        await message.answer(t(lang, "active_trip_missing"), reply_markup=main_menu_keyboard(lang))
        return

    expenses = db.fetch_trip_expenses(trip_id)
    if not expenses:
        await message.answer(t(lang, "no_expenses"), reply_markup=trip_menu_keyboard(lang))
        return

    members = {member_id: member_name for member_id, member_name, role in db.fetch_trip_members(trip_id)}
    expense_participants = {expense[0]: db.fetch_expense_participants(expense[0]) for expense in expenses}
    balances, settlements = calculate_settlements(expenses, expense_participants)

    trip = db.get_trip_by_id(trip_id)
    currency = trip[2] if trip else DEFAULT_TRIP_CURRENCY

    lines = [f"*{t(lang, 'debts_title')}*", ""]
    lines.append(f"*{t(lang, 'balances')}*")
    for member_id, balance in sorted(balances.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"• {members.get(member_id, str(member_id))}: {format_money(balance, currency)}")

    lines.append("")
    if not settlements:
        lines.append(t(lang, "nobody_owes"))
    else:
        lines.append(f"*{t(lang, 'who_owes')}*")
        for debtor_id, creditor_id, amount in settlements:
            lines.append(
                f"• {members.get(debtor_id, str(debtor_id))} → {members.get(creditor_id, str(creditor_id))}: {format_money(amount, currency)}"
            )

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=trip_menu_keyboard(lang))


@dp.message(F.text.startswith("◀️"))
async def back_button(message: Message):
    lang = current_lang(message.from_user.id)
    db.set_active_trip(message.from_user.id, None)
    PENDING_INPUTS.pop(message.from_user.id, None)
    await message.answer(t(lang, "active_trip_cleared"), reply_markup=main_menu_keyboard(lang))


@dp.callback_query(F.data.startswith("cat:"))
async def category_callback(query: CallbackQuery):
    state = PENDING_INPUTS.get(query.from_user.id)
    lang = current_lang(query.from_user.id)

    if not state or state.get("flow") != "add_expense" or state.get("step") != "category":
        await query.answer("Start add expense first")
        return

    category = query.data.split(":", 1)[1]
    state["category"] = category
    state["step"] = "note"

    await query.answer("OK")
    await query.message.answer(t(lang, "send_note"), reply_markup=trip_menu_keyboard(lang))


@dp.callback_query(F.data.startswith("split:"))
async def split_callback(query: CallbackQuery):
    state = PENDING_INPUTS.get(query.from_user.id)
    lang = current_lang(query.from_user.id)

    if not state or state.get("flow") != "add_expense" or state.get("step") != "split":
        await query.answer("Start add expense first")
        return

    split_mode = query.data.split(":", 1)[1]
    state["split_mode"] = split_mode
    trip_id = state["trip_id"]

    if split_mode == "all":
        trip = db.get_trip_by_id(trip_id)
        currency = trip[2] if trip else DEFAULT_TRIP_CURRENCY
        expense_id = db.add_expense(
            trip_id,
            query.from_user.id,
            state["amount"],
            currency,
            state["category"],
            state["note"],
        )
        participant_ids = db.fetch_trip_member_ids(trip_id)
        db.add_expense_participants(expense_id, participant_ids)
        PENDING_INPUTS.pop(query.from_user.id, None)

        await query.answer("OK")
        await query.message.answer(t(lang, "expense_saved"), reply_markup=trip_menu_keyboard(lang))
        return

    state["step"] = "participant_ids"
    members = db.fetch_trip_members(trip_id)
    lines = [t(lang, "send_member_ids")]
    for member_user_id, member_name, role in members:
        lines.append(f"• {member_name} | ID: {member_user_id}")

    await query.answer("OK")
    await query.message.answer("\n".join(lines), reply_markup=trip_menu_keyboard(lang))


@dp.message(F.text)
async def text_handler(message: Message):
    user_id = message.from_user.id
    lang = current_lang(user_id)
    state = PENDING_INPUTS.get(user_id)

    if state and state.get("flow") == "create_trip":
        if state.get("step") == "title":
            state["title"] = message.text.strip()
            state["step"] = "currency"
            await message.answer(t(lang, "enter_trip_currency"), reply_markup=main_menu_keyboard(lang))
            return

        if state.get("step") == "currency":
            state["currency"] = message.text.strip().upper() or DEFAULT_TRIP_CURRENCY
            state["step"] = "trip_language"
            await message.answer(t(lang, "choose_trip_language"), reply_markup=trip_language_keyboard())
            return

    if state and state.get("flow") == "join_trip":
        trip_id_raw = message.text.strip()
        if not trip_id_raw.isdigit():
            await message.answer(t(lang, "enter_trip_id"), reply_markup=main_menu_keyboard(lang))
            return

        trip_id = int(trip_id_raw)
        trip = db.get_trip_by_id(trip_id)
        if not trip:
            await message.answer(t(lang, "trip_not_found"), reply_markup=main_menu_keyboard(lang))
            return

        if db.is_trip_member(trip_id, user_id):
            PENDING_INPUTS.pop(user_id, None)
            await message.answer(t(lang, "already_member"), reply_markup=main_menu_keyboard(lang))
            return

        db.add_trip_member(trip_id, user_id, role="member")
        PENDING_INPUTS.pop(user_id, None)

        _, title, currency, trip_language, status, created_at = trip
        await message.answer(
            f"{t(lang, 'joined_trip')}\n#{trip_id} {title} | {currency} | {trip_language.upper()}",
            reply_markup=main_menu_keyboard(lang),
        )
        return

    if state and state.get("flow") == "open_trip":
        trip_id_raw = message.text.strip()
        if not trip_id_raw.isdigit():
            await message.answer(t(lang, "enter_trip_id"), reply_markup=main_menu_keyboard(lang))
            return

        trip_id = int(trip_id_raw)
        trip = db.get_trip_by_id(trip_id)
        if not trip:
            await message.answer(t(lang, "trip_not_found"), reply_markup=main_menu_keyboard(lang))
            return

        if not db.is_trip_member(trip_id, user_id):
            await message.answer(t(lang, "not_member"), reply_markup=main_menu_keyboard(lang))
            return

        db.set_active_trip(user_id, trip_id)
        PENDING_INPUTS.pop(user_id, None)

        _, title, currency, trip_language, status, created_at = trip
        await message.answer(
            f"{t(lang, 'trip_opened')}\n#{trip_id} {title} | {currency} | {trip_language.upper()}",
            reply_markup=trip_menu_keyboard(lang),
        )
        return

    if state and state.get("flow") == "add_expense":
        if state.get("step") == "amount":
            try:
                state["amount"] = parse_amount(message.text)
            except ValueError:
                await message.answer(t(lang, "invalid_amount"), reply_markup=trip_menu_keyboard(lang))
                return
            state["step"] = "category"
            await message.answer(t(lang, "choose_category"), reply_markup=category_keyboard())
            return

        if state.get("step") == "note":
            state["note"] = "" if message.text.strip() == "0" else message.text.strip()
            state["step"] = "split"
            await message.answer(t(lang, "choose_split"), reply_markup=split_keyboard(lang))
            return

        if state.get("step") == "participant_ids":
            raw_ids = [item.strip() for item in message.text.split(",") if item.strip()]
            valid_member_ids = set(db.fetch_trip_member_ids(state["trip_id"]))

            try:
                participant_ids = [int(item) for item in raw_ids]
            except ValueError:
                await message.answer(t(lang, "send_member_ids"), reply_markup=trip_menu_keyboard(lang))
                return

            participant_ids = [pid for pid in participant_ids if pid in valid_member_ids]
            if not participant_ids:
                await message.answer(t(lang, "send_member_ids"), reply_markup=trip_menu_keyboard(lang))
                return

            trip = db.get_trip_by_id(state["trip_id"])
            currency = trip[2] if trip else DEFAULT_TRIP_CURRENCY

            expense_id = db.add_expense(
                state["trip_id"],
                user_id,
                state["amount"],
                currency,
                state["category"],
                state["note"],
            )
            db.add_expense_participants(expense_id, participant_ids)
            PENDING_INPUTS.pop(user_id, None)

            await message.answer(t(lang, "expense_saved"), reply_markup=trip_menu_keyboard(lang))
            return

    await message.answer(t(lang, "unknown"), reply_markup=main_menu_keyboard(lang))


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())