print("🔥 NEW VERSION LOADED 🔥")
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncpg
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pool = None

# ---------------- DB ----------------

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            name TEXT,
            active_trip INT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id SERIAL PRIMARY KEY,
            title TEXT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS members (
            trip_id INT,
            user_id BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            trip_id INT,
            payer BIGINT,
            amount FLOAT
        );
        """)

# ---------------- HELPERS ----------------

async def get_user(uid):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id=$1", uid
        )

async def create_user(uid, name):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (telegram_id,name) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            uid, name
        )

async def set_trip(uid, trip):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET active_trip=$1 WHERE telegram_id=$2",
            trip, uid
        )

# ---------------- UI ----------------

def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Create trip")],
            [KeyboardButton(text="Join last trip")],
            [KeyboardButton(text="Add expense")],
            [KeyboardButton(text="Calculate debts")]
        ],
        resize_keyboard=True
    )

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(m):
    await create_user(m.from_user.id, m.from_user.full_name)
    await m.answer("Ready", reply_markup=menu())

# ---------------- STATES ----------------

states = {}

# ---------------- HANDLER ----------------

@dp.message()
async def handler(m):

    uid = m.from_user.id

    # CREATE TRIP
    if m.text == "Create trip":
        states[uid] = {"step": "title"}
        await m.answer("Enter trip name:")
        return

    # JOIN
    if m.text == "Join last trip":
        async with pool.acquire() as conn:
            trip = await conn.fetchrow(
                "SELECT * FROM trips ORDER BY id DESC LIMIT 1"
            )

            if trip:
                await conn.execute(
                    "INSERT INTO members VALUES ($1,$2)",
                    trip["id"], uid
                )
                await set_trip(uid, trip["id"])
                await m.answer("Joined trip")
            else:
                await m.answer("No trips found")

        return

    # ADD EXPENSE
    if m.text == "Add expense":
        states[uid] = {"step": "amount"}
        await m.answer("Enter amount:")
        return

    # CALCULATE
    if m.text == "Calculate debts":
        await calculate(m)
        return

    # FLOW
    if uid in states:
        s = states[uid]

        if s["step"] == "title":
            async with pool.acquire() as conn:
                trip_id = await conn.fetchval(
                    "INSERT INTO trips (title) VALUES ($1) RETURNING id",
                    m.text
                )
                await conn.execute(
                    "INSERT INTO members VALUES ($1,$2)",
                    trip_id, uid
                )

            await set_trip(uid, trip_id)
            states.pop(uid)

            await m.answer("Trip created")
            return

        if s["step"] == "amount":
            amount = float(m.text)

            async with pool.acquire() as conn:
                user = await get_user(uid)

                await conn.execute(
                    "INSERT INTO expenses (trip_id,payer,amount) VALUES ($1,$2,$3)",
                    user["active_trip"], uid, amount
                )

            states.pop(uid)
            await m.answer("Expense added")
            return

# ---------------- CALCULATE ----------------

async def calculate(m):

    uid = m.from_user.id

    async with pool.acquire() as conn:

        user = await get_user(uid)

        expenses = await conn.fetch(
            "SELECT * FROM expenses WHERE trip_id=$1",
            user["active_trip"]
        )

        members = await conn.fetch(
            "SELECT user_id FROM members WHERE trip_id=$1",
            user["active_trip"]
        )

        balances = {m["user_id"]: 0 for m in members}

        for e in expenses:
            share = e["amount"] / len(members)

            for member in members:
                balances[member["user_id"]] -= share

            balances[e["payer"]] += e["amount"]

    creditors = []
    debtors = []

    for u, b in balances.items():
        if b > 0:
            creditors.append([u, b])
        elif b < 0:
            debtors.append([u, -b])

    result = ""

    for d, da in debtors:
        for c in creditors:
            if da == 0:
                break

            cu, ca = c
            pay = min(da, ca)

            if pay > 0:
                result += f"{d} → {cu}: {round(pay,2)}\n"
                c[1] -= pay
                da -= pay

    await m.answer(result or "Nobody owes anyone")

# ---------------- RUN ----------------

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())