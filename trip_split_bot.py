import asyncio
import os
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
            title TEXT,
            invite_code TEXT
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
            amount FLOAT,
            note TEXT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            expense_id INT,
            user_id BIGINT
        );
        """)

# ---------------- HELPERS ----------------

async def get_user(uid):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", uid)

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

async def get_name(uid):
    u = await get_user(uid)
    return u["name"] if u else str(uid)

# ---------------- UI ----------------

def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Create trip")],
            [KeyboardButton(text="Join trip")],
            [KeyboardButton(text="Add expense")],
            [KeyboardButton(text="Calculate debts")]
        ],
        resize_keyboard=True
    )

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(m):
    await create_user(m.from_user.id, m.from_user.full_name)
    await m.answer("🚀 TripSplit ready", reply_markup=menu())

# ---------------- STATES ----------------

states = {}
select_states = {}

# ---------------- MAIN HANDLER ----------------

@dp.message()
async def handler(m):

    uid = m.from_user.id

    # CREATE TRIP
    if m.text == "Create trip":
        states[uid] = {"step": "title"}
        await m.answer("Enter trip name:")
        return

    # JOIN
    if m.text == "Join trip":
        states[uid] = {"step": "join"}
        await m.answer("Enter invite code:")
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

        # CREATE FLOW
        if s["step"] == "title":
            code = str(uuid.uuid4())[:6]

            async with pool.acquire() as conn:
                trip_id = await conn.fetchval(
                    "INSERT INTO trips (title,invite_code) VALUES ($1,$2) RETURNING id",
                    m.text, code
                )
                await conn.execute(
                    "INSERT INTO members VALUES ($1,$2)",
                    trip_id, uid
                )

            await set_trip(uid, trip_id)
            states.pop(uid)

            await m.answer(f"Trip created!\nInvite code: {code}")
            return

        # JOIN FLOW
        if s["step"] == "join":
            async with pool.acquire() as conn:
                trip = await conn.fetchrow(
                    "SELECT * FROM trips WHERE invite_code=$1",
                    m.text
                )

                if trip:
                    await conn.execute(
                        "INSERT INTO members VALUES ($1,$2)",
                        trip["id"], uid
                    )
                    await set_trip(uid, trip["id"])
                    await m.answer("Joined trip!")
                else:
                    await m.answer("Invalid code")

            states.pop(uid)
            return

        # EXPENSE FLOW
        if s["step"] == "amount":
            s["amount"] = float(m.text)
            s["step"] = "note"
            await m.answer("Enter comment:")
            return

        if s["step"] == "note":
            s["note"] = m.text
            await select_participants(m)
            return

# ---------------- SELECT PARTICIPANTS ----------------

async def select_participants(m):

    uid = m.from_user.id

    async with pool.acquire() as conn:
        u = await get_user(uid)
        members = await conn.fetch(
            "SELECT user_id FROM members WHERE trip_id=$1",
            u["active_trip"]
        )

    select_states[uid] = {m["user_id"]: True for m in members}

    await draw_select(m)

async def draw_select(m):

    uid = m.from_user.id
    state = select_states[uid]

    kb = []

    for user_id, selected in state.items():
        name = await get_name(user_id)
        kb.append([InlineKeyboardButton(
            text=("✅ " if selected else "❌ ") + name,
            callback_data=f"toggle_{user_id}"
        )])

    kb.append([InlineKeyboardButton(text="Done", callback_data="done")])

    await m.answer("Select participants:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(lambda c: c.data.startswith("toggle_"))
async def toggle(c):
    uid = c.from_user.id
    target = int(c.data.split("_")[1])

    select_states[uid][target] = not select_states[uid][target]

    await c.message.delete()
    await draw_select(c.message)

@dp.callback_query(lambda c: c.data == "done")
async def done(c):

    uid = c.from_user.id
    s = states[uid]

    selected = [u for u,v in select_states[uid].items() if v]

    async with pool.acquire() as conn:
        u = await get_user(uid)

        expense_id = await conn.fetchval(
            "INSERT INTO expenses (trip_id,payer,amount,note) VALUES ($1,$2,$3,$4) RETURNING id",
            u["active_trip"], uid, s["amount"], s["note"]
        )

        for user_id in selected:
            await conn.execute(
                "INSERT INTO participants VALUES ($1,$2)",
                expense_id, user_id
            )

    states.pop(uid)
    select_states.pop(uid)

    await c.message.answer("Expense added!")
    await c.answer()

# ---------------- CALCULATE ----------------

async def calculate(m):

    uid = m.from_user.id

    async with pool.acquire() as conn:

        u = await get_user(uid)

        expenses = await conn.fetch(
            "SELECT * FROM expenses WHERE trip_id=$1",
            u["active_trip"]
        )

        balances = {}

        for e in expenses:
            participants = await conn.fetch(
                "SELECT user_id FROM participants WHERE expense_id=$1",
                e["id"]
            )

            share = e["amount"] / len(participants)

            for p in participants:
                balances[p["user_id"]] = balances.get(p["user_id"], 0) - share

            balances[e["payer"]] = balances.get(e["payer"], 0) + e["amount"]

    creditors = []
    debtors = []

    for user_id, balance in balances.items():
        if balance > 0:
            creditors.append([user_id, balance])
        elif balance < 0:
            debtors.append([user_id, -balance])

    result = ""

    for d_id, d_amt in debtors:
        for c in creditors:
            if d_amt == 0:
                break

            c_id, c_amt = c
            pay = min(d_amt, c_amt)

            if pay > 0:
                result += f"{await get_name(d_id)} → {await get_name(c_id)}: {round(pay,2)}\n"
                c[1] -= pay
                d_amt -= pay

    await m.answer(result or "Nobody owes anyone")

# ---------------- RUN ----------------

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())