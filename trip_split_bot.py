import asyncio
import os
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")

# временная "база" в памяти
USERS = {}
TRIPS = {}
PENDING = {}

trip_counter = 1


@dataclass
class Trip:
    id: int
    title: str
    currency: str
    owner_id: int


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ================= UI =================

def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="✈️ Create trip")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def trip_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="👥 Members")
    kb.button(text="💸 Calculate")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


# ================= HANDLERS =================

@dp.message(CommandStart())
async def start(message: Message):
    USERS[message.from_user.id] = {}
    await message.answer("Welcome!", reply_markup=main_menu())


@dp.message(F.text == "✈️ Create trip")
async def create_trip_start(message: Message):
    PENDING[message.from_user.id] = {"step": "title"}
    await message.answer("Enter trip name:")


@dp.message(F.text)
async def text_handler(message: Message):
    user_id = message.from_user.id
    state = PENDING.get(user_id)

    # ===== CREATE TRIP FLOW =====
    if state:
        # шаг 1 — название
        if state["step"] == "title":
            state["title"] = message.text
            state["step"] = "currency"
            await message.answer("Enter currency (EUR/USD):")
            return

        # шаг 2 — валюта
        elif state["step"] == "currency":
            currency = message.text.upper()

            if len(currency) != 3:
                await message.answer("Currency must be 3 letters (EUR)")
                return

            global trip_counter

            trip = Trip(
                id=trip_counter,
                title=state["title"],
                currency=currency,
                owner_id=user_id
            )

            TRIPS[trip_counter] = trip
            trip_counter += 1

            PENDING.pop(user_id)

            await message.answer(
                f"Trip created!\nID: {trip.id}\n{trip.title} | {trip.currency}",
                reply_markup=trip_menu()
            )
            return

    # если ничего не понял
    await message.answer("Use menu")


# ================= RUN =================

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())