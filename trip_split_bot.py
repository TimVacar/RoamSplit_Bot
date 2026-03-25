import asyncio
import os
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")

USERS = {}  # {user_id: {"lang": "en", "active_trip": None}}
TRIPS = {}
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
        "enter_name": "Enter trip name:",
        "enter_currency": "Enter currency (EUR/USD):",
        "invalid_currency": "Currency must be 3 letters (EUR)",
        "created": "Trip created!",
        "menu": "Use menu",
        "enter_trip_id": "Enter trip ID:",
        "trip_not_found": "Trip not found",
        "joined": "You joined the trip",
        "opened": "Trip opened",
    },
    "ru": {
        "welcome": "Добро пожаловать!",
        "choose_lang": "Выбери язык:",
        "create_trip": "Создать поездку",
        "join_trip": "Вступить",
        "open_trip": "Открыть поездку",
        "enter_name": "Введи название:",
        "enter_currency": "Введи валюту:",
        "invalid_currency": "3 буквы (EUR)",
        "created": "Поездка создана!",
        "menu": "Используй меню",
        "enter_trip_id": "Введи ID поездки:",
        "trip_not_found": "Поездка не найдена",
        "joined": "Ты вступил в поездку",
        "opened": "Поездка открыта",
    }
}

for l in ["ro", "fr", "es", "it"]:
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
    lang = get_lang(user_id)
    return TEXTS[lang].get(key, key)


# ========= UI =========

def lang_keyboard():
    kb = InlineKeyboardBuilder()
    for l in SUPPORTED_LANGS:
        kb.button(text=l.upper(), callback_data=f"lang:{l}")
    kb.adjust(3)
    return kb.as_markup()


def main_menu(user_id):
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"✈️ {t(user_id, 'create_trip')}")
    kb.button(text=f"🔗 {t(user_id, 'join_trip')}")
    kb.button(text=f"📂 {t(user_id, 'open_trip')}")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


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

    await callback.answer("OK")
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


# ===== TEXT HANDLER =====

@dp.message(F.text)
async def text_handler(message: Message):
    global trip_counter

    user_id = message.from_user.id
    state = PENDING.get(user_id)

    if state:

        # ===== CREATE =====
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
                f"{t(user_id, 'created')}\nID: {trip.id}\n{trip.title} | {trip.currency}",
                reply_markup=main_menu(user_id)
            )
            return

        # ===== JOIN =====
        elif state.get("step") == "join_trip":
            if not message.text.isdigit():
                await message.answer("Enter valid ID")
                return

            trip_id = int(message.text)

            if trip_id not in TRIPS:
                await message.answer(t(user_id, "trip_not_found"))
                return

            USERS[user_id]["active_trip"] = trip_id
            PENDING.pop(user_id)

            await message.answer(f"{t(user_id, 'joined')} #{trip_id}")
            return

        # ===== OPEN =====
        elif state.get("step") == "open_trip":
            if not message.text.isdigit():
                await message.answer("Enter valid ID")
                return

            trip_id = int(message.text)

            if trip_id not in TRIPS:
                await message.answer(t(user_id, "trip_not_found"))
                return

            USERS[user_id]["active_trip"] = trip_id
            PENDING.pop(user_id)

            await message.answer(f"{t(user_id, 'opened')} #{trip_id}")
            return

    await message.answer(t(user_id, "menu"))


# ========= RUN =========

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())