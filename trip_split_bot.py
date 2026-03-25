import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== STORAGE =====

USERS = {}  
TRIPS = {}  
EXPENSES = []  
PENDING = {}

trip_counter = 1

# ===== LANG =====

TEXTS = {
    "en": {
        "welcome": "Welcome!",
        "choose_lang": "Choose language:",
        "menu": "Menu",
        "create": "Create trip",
        "join": "Join trip",
        "open": "Open trip",
        "add": "Add expense",
        "expenses": "Expenses",
        "calc": "Calculate",
        "name": "Enter trip name:",
        "currency": "Enter currency (EUR):",
        "id": "Enter trip ID:",
        "amount": "Enter amount:",
        "comment": "Enter comment:",
        "saved": "Saved",
        "no_trip": "Open trip first",
        "not_found": "Trip not found",
        "debts": "Debts"
    }
}

def t(user_id, key):
    return TEXTS["en"][key]

# ===== UI =====

def menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="✈️ Create trip")
    kb.button(text="🔗 Join trip")
    kb.button(text="📂 Open trip")
    kb.button(text="➕ Add expense")
    kb.button(text="📊 Expenses")
    kb.button(text="💸 Calculate")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

# ===== START =====

@dp.message(CommandStart())
async def start(message: Message):
    USERS[message.from_user.id] = {
        "name": message.from_user.first_name,
        "trip": None
    }
    await message.answer("Welcome!", reply_markup=menu())

# ===== CREATE =====

@dp.message(F.text == "✈️ Create trip")
async def create(message: Message):
    PENDING[message.from_user.id] = {"step": "name"}
    await message.answer("Enter trip name:")

# ===== JOIN =====

@dp.message(F.text == "🔗 Join trip")
async def join(message: Message):
    PENDING[message.from_user.id] = {"step": "join"}
    await message.answer("Enter trip ID:")

# ===== OPEN =====

@dp.message(F.text == "📂 Open trip")
async def open_trip(message: Message):
    PENDING[message.from_user.id] = {"step": "open"}
    await message.answer("Enter trip ID:")

# ===== ADD EXPENSE =====

@dp.message(F.text == "➕ Add expense")
async def add(message: Message):
    uid = message.from_user.id

    if USERS[uid]["trip"] is None:
        return await message.answer("Open trip first")

    PENDING[uid] = {"step": "amount"}
    await message.answer("Enter amount:")

# ===== SHOW EXPENSES =====

@dp.message(F.text == "📊 Expenses")
async def show(message: Message):
    uid = message.from_user.id
    trip = USERS[uid]["trip"]

    data = [e for e in EXPENSES if e["trip"] == trip]

    if not data:
        return await message.answer("No expenses")

    text = ""
    for e in data:
        name = USERS[e["user"]]["name"]
        text += f"{name}: {e['amount']} - {e['comment']}\n"

    await message.answer(text)

# ===== CALCULATE =====

@dp.message(F.text == "💸 Calculate")
async def calc(message: Message):
    uid = message.from_user.id
    trip = USERS[uid]["trip"]

    members = TRIPS[trip]["members"]
    data = [e for e in EXPENSES if e["trip"] == trip]

    balances = {m: 0 for m in members}

    for e in data:
        balances[e["user"]] += e["amount"]

    total = sum(e["amount"] for e in data)
    share = total / len(members)

    for m in members:
        balances[m] -= share

    debtors = []
    creditors = []

    for u, v in balances.items():
        if v < 0:
            debtors.append([u, abs(v)])
        elif v > 0:
            creditors.append([u, v])

    i = j = 0
    result = "Debts:\n\n"

    while i < len(debtors) and j < len(creditors):
        d, debt = debtors[i]
        c, credit = creditors[j]

        pay = min(debt, credit)

        result += f"{USERS[d]['name']} → {USERS[c]['name']}: {round(pay,2)}\n"

        debtors[i][1] -= pay
        creditors[j][1] -= pay

        if debtors[i][1] < 0.01:
            i += 1
        if creditors[j][1] < 0.01:
            j += 1

    await message.answer(result)

# ===== TEXT HANDLER =====

@dp.message(F.text)
async def text(message: Message):
    global trip_counter

    uid = message.from_user.id
    state = PENDING.get(uid)

    if not state:
        return

    if state["step"] == "name":
        state["name"] = message.text
        state["step"] = "currency"
        return await message.answer("Currency:")

    if state["step"] == "currency":
        TRIPS[trip_counter] = {
            "title": state["name"],
            "currency": message.text,
            "members": [uid]
        }

        USERS[uid]["trip"] = trip_counter
        trip_counter += 1
        PENDING.pop(uid)

        return await message.answer(f"Trip created ID: {trip_counter-1}")

    if state["step"] == "join":
        tid = int(message.text)

        if tid not in TRIPS:
            return await message.answer("Not found")

        TRIPS[tid]["members"].append(uid)
        USERS[uid]["trip"] = tid
        PENDING.pop(uid)

        return await message.answer("Joined")

    if state["step"] == "open":
        tid = int(message.text)

        if tid not in TRIPS:
            return await message.answer("Not found")

        USERS[uid]["trip"] = tid
        PENDING.pop(uid)

        return await message.answer("Opened")

    if state["step"] == "amount":
        state["amount"] = float(message.text)
        state["step"] = "comment"
        return await message.answer("Comment:")

    if state["step"] == "comment":
        EXPENSES.append({
            "trip": USERS[uid]["trip"],
            "user": uid,
            "amount": state["amount"],
            "comment": message.text
        })

        PENDING.pop(uid)
        return await message.answer("Saved")

# ===== RUN =====

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())