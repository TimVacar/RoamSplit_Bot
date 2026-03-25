import asyncio
import os
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")

USERS = {}
TRIPS = {}
EXPENSES = []
PENDING = {}

trip_counter = 1


SUPPORTED_LANGS = ["en", "ru", "ro", "fr", "es", "it"]

TEXTS = {
    "en": {
        "welcome": "Welcome!",
        "choose_lang": "Choose language:",
        "create_trip": "Create trip",
        "join_trip": "Join trip",
        "open_trip": "Open trip",
        "add_expense": "Add expense",
        "enter_name": "Enter trip name:",
        "enter_currency": "Enter currency (EUR/USD):",
        "invalid_currency": "Currency must be 3 letters (EUR)",
        "created": "Trip created!",
        "menu": "Use menu",
        "enter_trip_id": "Enter trip ID:",
        "trip_not_found": "Trip not found",
        "joined": "You joined the trip",
        "opened": "Trip opened",
        "enter_amount": "Enter amount:",
        "enter_comment": "Enter comment:",
        "expense_saved": "Expense saved"
    }
}

for l in ["ru", "ro", "fr", "es", "it"]:
    TEXTS[l] = TEXTS["en"]


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


def main_menu(user_id):
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"✈️ {t(user_id, 'create_trip')}")
    kb.button(text=f"🔗 {t(user_id, 'join_trip')}")
    kb.button(text=f"📂 {t(user_id, 'open_trip')}")
    kb.button(text=f"➕ {t(user_id, 'add_expense')}")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def lang_keyboard():
    kb = InlineKeyboardBuilder()
    for l in SUPPORTED_LANGS:
        kb.button(text=l.upper(), callback_data=f"lang:{l}")
    kb.adjust(3)
    return kb.as_markup()


# ========= HANDLERS =========

@dp.message(CommandStart())
async def start(message: Message):
    USERS[message.from_user.id] = {"lang": "en", "active_trip": None}
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
        await message.answer("Open a trip first")
        return

    PENDING[user_id] = {"step": "amount"}
    await message.answer(t(user_id, "enter_amount"))


# ===== TEXT HANDLER =====

@dp.message(F.text)
async def text_handler(message: Message):
    global trip_counter

    user_id = message.from_user.id
    state = PENDING.get(user_id)

    if state:

        # CREATE
        if state.get("step") == "title":
            state["title"] = message.text
            state["step"] = "currency"
            await message.answer(t(user_id, "enter_currency"))
            return

        elif state.get("step") == "currency":
            currency = message.text.upper()

            if len(currency) != 3:
                await message.answer(t(user_id, "invalid_currency"))
                return

            trip = Trip(
                id=trip_counter,
                title=state["title"],
                currency=currency,
                owner_id=user_id
            )

            TRIPS[trip_counter] = trip
            USERS[user_id]["active_trip"] = trip_counter

            trip_counter += 1
            PENDING.pop(user_id)

            await message.answer(
                f"{t(user_id, 'created')}\nID: {trip.id}",
                reply_markup=main_menu(user_id)
            )
            return

        # JOIN
        elif state.get("step") == "join_trip":
            if not message.text.isdigit():
                return

            trip_id = int(message.text)

            if trip_id not in TRIPS:
                await message.answer(t(user_id, "trip_not_found"))
                return

            USERS[user_id]["active_trip"] = trip_id
            PENDING.pop(user_id)
            await message.answer(f"{t(user_id, 'joined')} #{trip_id}")
            return

        # OPEN
        elif state.get("step") == "open_trip":
            if not message.text.isdigit():
                return

            trip_id = int(message.text)

            if trip_id not in TRIPS:
                await message.answer(t(user_id, "trip_not_found"))
                return

            USERS[user_id]["active_trip"] = trip_id
            PENDING.pop(user_id)
            await message.answer(f"{t(user_id, 'opened')} #{trip_id}")
            return

        # EXPENSE STEP 1
        elif state.get("step") == "amount":
            try:
                amount = float(message.text)
            except:
                await message.answer("Invalid number")
                return

            state["amount"] = amount
            state["step"] = "comment"
            await message.answer(t(user_id, "enter_comment"))
            return

        # EXPENSE STEP 2
        elif state.get("step") == "comment":
            trip_id = USERS[user_id]["active_trip"]

            EXPENSES.append({
                "trip_id": trip_id,
                "user_id": user_id,
                "amount": state["amount"],
                "comment": message.text
            })

            PENDING.pop(user_id)

            await message.answer(t(user_id, "expense_saved"))
            return

    await message.answer(t(user_id, "menu"))


# ========= RUN =========

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())