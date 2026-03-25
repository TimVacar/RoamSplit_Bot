import asyncio
import os
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")

USERS = {}  # user_id: {lang, active_trip, name}
TRIPS = {}  # trip_id: {title, currency, members}
EXPENSES = []
PENDING = {}

trip_counter = 1

SUPPORTED_LANGS = ["en", "ru"]

TEXTS = {
    "en": {
        "welcome": "Welcome!",
        "choose_lang": "Choose language:",
        "create_trip": "Create trip",
        "join_trip": "Join trip",
        "open_trip": "Open trip",
        "add_expense": "Add expense",
        "show_expenses": "Expenses",
        "calculate": "Calculate",
        "enter_name": "Enter trip name:",
        "enter_currency": "Enter currency:",
        "invalid_currency": "Currency must be 3 letters",
        "created": "Trip created!",
        "enter_trip_id": "Enter trip ID:",
        "trip_not_found": "Trip not found",
        "joined": "Joined trip",
        "opened": "Opened trip",
        "enter_amount": "Enter amount:",
        "enter_comment": "Enter comment:",
        "expense_saved": "Expense saved",
        "no_trip": "Open a trip first",
        "debts": "Debts",
        "no_expenses": "No expenses",
        "members": "Members"
    },
    "ru": {
        "welcome": "Добро пожаловать!",
        "choose_lang": "Выбери язык:",
        "create_trip": "Создать поездку",
        "join_trip": "Вступить",
        "open_trip": "Открыть",
        "add_expense": "Добавить расход",
        "show_expenses": "Расходы",
        "calculate": "Рассчитать",
        "enter_name": "Введи название:",
        "enter_currency": "Введи валюту:",
        "invalid_currency": "3 буквы",
        "created": "Поездка создана!",
        "enter_trip_id": "Введи ID:",
        "trip_not_found": "Не найдено",
        "joined": "Ты вступил",
        "opened": "Открыто",
        "enter_amount": "Сумма:",
        "enter_comment": "Комментарий:",
        "expense_saved": "Сохранено",
        "no_trip": "Сначала открой поездку",
        "debts": "Долги",
        "no_expenses": "Нет расходов",
        "members": "Участники"
    }
}


@dataclass
class Trip:
    id: int
    title: str
    currency: str
    owner_id: int


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ========= HELPERS =========

def get_lang(user_id):
    return USERS.get(user_id, {}).get("lang", "en")


def t(user_id, key):
    return TEXTS[get_lang(user_id)].get(key, key)


def get_name(user_id):
    return USERS.get(user_id, {}).get("name", str(user_id))


def main_menu(user_id):
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"✈️ {t(user_id, 'create_trip')}")
    kb.button(text=f"🔗 {t(user_id, 'join_trip')}")
    kb.button(text=f"📂 {t(user_id, 'open_trip')}")
    kb.button(text=f"➕ {t(user_id, 'add_expense')}")
    kb.button(text=f"📊 {t(user_id, 'show_expenses')}")
    kb.button(text=f"💸 {t(user_id, 'calculate')}")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def lang_keyboard():
    kb = InlineKeyboardBuilder()
    for l in SUPPORTED_LANGS:
        kb.button(text=l.upper(), callback_data=f"lang:{l}")
    kb.adjust(2)
    return kb.as_markup()


# ========= HANDLERS =========

@dp.message(CommandStart())
async def start(message: Message):
    USERS[message.from_user.id] = {
        "lang": "en",
        "active_trip": None,
        "name": message.from_user.first_name
    }

    await message.answer("Welcome!")
    await message.answer("Choose language:", reply_markup=lang_keyboard())


@dp.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    USERS[callback.from_user.id]["lang"] = lang

    await callback.answer()
    await callback.message.answer(
        t(callback.from_user.id, "welcome"),
        reply_markup=main_menu(callback.from_user.id)
    )


# ===== CREATE =====

@dp.message(F.text.startswith("✈️"))
async def create_trip_start(message: Message):
    PENDING[message.from_user.id] = {"step": "title"}
    await message.answer(t(message.from_user.id, "enter_name"))


# ===== JOIN =====

@dp.message(F.text.startswith("🔗"))
async def join_trip_start(message: Message):
    PENDING[message.from_user.id] = {"step": "join_trip"}
    await message.answer(t(message.from_user.id, "enter_trip_id"))


# ===== OPEN =====

@dp.message(F.text.startswith("📂"))
async def open_trip_start(message: Message):
    PENDING[message.from_user.id] = {"step": "open_trip"}
    await message.answer(t(message.from_user.id, "enter_trip_id"))


# ===== ADD EXPENSE =====

@dp.message(F.text.startswith("➕"))
async def add_expense_start(message: Message):
    user_id = message.from_user.id

    if USERS[user_id]["active_trip"] is None:
        await message.answer(t(user_id, "no_trip"))
        return

    PENDING[user_id] = {"step": "amount"}
    await message.answer(t(user_id, "enter_amount"))


# ===== SHOW EXPENSES =====

@dp.message(F.text.startswith("📊"))
async def show_expenses(message: Message):
    user_id = message.from_user.id
    trip_id = USERS[user_id]["active_trip"]

    if trip_id is None:
        await message.answer(t(user_id, "no_trip"))
        return

    trip_expenses = [e for e in EXPENSES if e["trip_id"] == trip_id]

    if not trip_expenses:
        await message.answer(t(user_id, "no_expenses"))
        return

    text = "Expenses:\n\n"
    for e in trip_expenses:
        name = get_name(e["user_id"])
        text += f"{name}: {e['amount']} - {e['comment']}\n"

    await message.answer(text)


# ===== PRO CALCULATE =====

@dp.message(F.text.startswith("💸"))
async def calculate(message: Message):
    user_id = message.from_user.id
    trip_id = USERS[user_id]["active_trip"]

    if trip_id is None:
        await message.answer(t(user_id, "no_trip"))
        return

    trip = TRIPS.get(trip_id)
    members = trip["members"]

    trip_expenses = [e for e in EXPENSES if e["trip_id"] == trip_id]

    if not trip_expenses:
        await message.answer(t(user_id, "no_expenses"))
        return

    balances = {m: 0 for m in members}

    for e in trip_expenses:
        balances[e["user_id"]] += e["amount"]

    total = sum(e["amount"] for e in trip_expenses)
    share = total / len(members)

    for m in members:
        balances[m] -= share

    debtors = []
    creditors = []

    for u, val in balances.items():
        if val < 0:
            debtors.append([u, abs(val)])
        elif val > 0:
            creditors.append([u, val])

    i = j = 0
    result = f"{t(user_id, 'debts')}:\n\n"

    while i < len(debtors) and j < len(creditors):
        d_id, debt = debtors[i]
        c_id, credit = creditors[j]

        pay = min(debt, credit)

        result += f"{get_name(d_id)} → {get_name(c_id)}: {round(pay,2)}\n"

        debtors[i][1] -= pay
        creditors[j][1] -= pay

        if debtors[i][1] < 0.01:
            i += 1
        if creditors[j][1] < 0.01:
            j += 1

    await message.answer(result)


# ===== TEXT HANDLER =====

@dp.message(F.text)
async def text_handler(message: Message):
    global trip_counter

    user_id = message.from_user.id
    state = PENDING.get(user_id)

    if state:

        if state.get("step") == "title":
            state["title"] = message.text
            state["step"] = "currency"
            return await message.answer(t(user_id, "enter_currency"))

        elif state.get("step") == "currency":
            currency = message.text.upper()

            if len(currency) != 3:
                return await message.answer(t(user_id, "invalid_currency"))

            TRIPS[trip_counter] = {
                "title": state["title"],
                "currency": currency,
                "members": [user_id]
            }

            USERS[user_id]["active_trip"] = trip_counter
            trip_counter += 1
            PENDING.pop(user_id)

            return await message.answer(
                f"{t(user_id, 'created')} ID: {trip_counter-1}",
                reply_markup=main_menu(user_id)
            )

        elif state.get("step") == "join_trip":
            trip_id = int(message.text)

            if trip_id not in TRIPS:
                return await message.answer(t(user_id, "trip_not_found"))

            TRIPS[trip_id]["members"].append(user_id)
            USERS[user_id]["active_trip"] = trip_id
            PENDING.pop(user_id)

            return await message.answer(f"{t(user_id, 'joined')} #{trip_id}")

        elif state.get("step") == "open_trip":
            trip_id = int(message.text)

            if trip_id not in TRIPS:
                return await message.answer(t(user_id, "trip_not_found"))

            USERS[user_id]["active_trip"] = trip_id
            PENDING.pop(user_id)

            return await message.answer(f"{t(user_id, 'opened')} #{trip_id}")

        elif state.get("step") == "amount":
            try:
                state["amount"] = float(message.text)
            except:
                return

            state["step"] = "comment"
            return await message.answer(t(user_id, "enter_comment"))

        elif state.get("step") == "comment":
            trip_id = USERS[user_id]["active_trip"]

            EXPENSES.append({
                "trip_id": trip_id,
                "user_id": user_id,
                "amount": state["amount"],
                "comment": message.text
            })

            PENDING.pop(user_id)
            return await message.answer(t(user_id, "expense_saved"))

    await message.answer(t(user_id, "menu"))


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())