import asyncio
import os
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
            active_trip_id INT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id SERIAL PRIMARY KEY,
            title TEXT,
            currency TEXT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS trip_members (
            trip_id INT,
            user_id BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            trip_id INT,
            payer_id BIGINT,
            amount FLOAT,
            note TEXT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS expense_participants (
            expense_id INT,
            user_id BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS debts (
            id SERIAL PRIMARY KEY,
            trip_id INT,
            from_user BIGINT,
            to_user BIGINT,
            amount FLOAT,
            status TEXT DEFAULT 'pending'
        );
        """)

# ---------------- HELPERS ----------------

async def get_user(user_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", user_id)

async def create_user(user_id, name):
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users (telegram_id, name)
        VALUES ($1,$2)
        ON CONFLICT DO NOTHING
        """, user_id, name)

async def get_name(user_id):
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT name FROM users WHERE telegram_id=$1", user_id
        )
        return user["name"] if user else str(user_id)

async def set_active_trip(user_id, trip_id):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET active_trip_id=$1 WHERE telegram_id=$2",
            trip_id, user_id
        )

# ---------------- UI ----------------

def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Create trip")],
            [KeyboardButton(text="Join last trip")],
            [KeyboardButton(text="Add expense")],
            [KeyboardButton(text="Calculate debts")],
            [KeyboardButton(text="My debts")],
            [KeyboardButton(text="Final report")],
        ],
        resize_keyboard=True
    )

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(message: types.Message):
    await create_user(message.from_user.id, message.from_user.full_name)
    await message.answer("🚀 TripSplit ready", reply_markup=menu())

# ---------------- STATES ----------------

user_states = {}

# ---------------- MAIN ----------------

@dp.message()
async def handler(message: types.Message):

    user_id = message.from_user.id

    # JOIN
    if message.text == "Join last trip":
        async with pool.acquire() as conn:
            trip = await conn.fetchrow("SELECT * FROM trips ORDER BY id DESC LIMIT 1")

            await conn.execute(
                "INSERT INTO trip_members (trip_id,user_id) VALUES ($1,$2)",
                trip["id"], user_id
            )

        await set_active_trip(user_id, trip["id"])
        await message.answer(f"✅ Joined {trip['title']}")
        return

    # CREATE TRIP
    if message.text == "Create trip":
        user_states[user_id] = {"step": "title"}
        await message.answer("🧳 Trip name:")
        return

    # ADD EXPENSE
    if message.text == "Add expense":
        user_states[user_id] = {"step": "amount"}
        await message.answer("💰 Amount:")
        return

    # CALCULATE
    if message.text == "Calculate debts":
        await calculate_and_notify(message)
        return

    # MY DEBTS
    if message.text == "My debts":
        await show_my_debts(message)
        return

    # FINAL REPORT
    if message.text == "Final report":
        await final_report(message)
        return

    # STATES
    if user_id in user_states:
        state = user_states[user_id]

        if state["step"] == "title":
            state["title"] = message.text
            state["step"] = "currency"
            await message.answer("💱 Currency:")
            return

        if state["step"] == "currency":
            async with pool.acquire() as conn:
                trip_id = await conn.fetchval(
                    "INSERT INTO trips (title,currency) VALUES ($1,$2) RETURNING id",
                    state["title"], message.text
                )

                await conn.execute(
                    "INSERT INTO trip_members (trip_id,user_id) VALUES ($1,$2)",
                    trip_id, user_id
                )

            await set_active_trip(user_id, trip_id)
            user_states.pop(user_id)

            await message.answer("✅ Trip created")
            return

        # EXPENSE
        if state["step"] == "amount":
            state["amount"] = float(message.text)
            state["step"] = "note"
            await message.answer("📝 Comment:")
            return

        if state["step"] == "note":

            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT active_trip_id FROM users WHERE telegram_id=$1",
                    user_id
                )

                trip_id = user["active_trip_id"]

                expense_id = await conn.fetchval(
                    "INSERT INTO expenses (trip_id,payer_id,amount,note) VALUES ($1,$2,$3,$4) RETURNING id",
                    trip_id, user_id, state["amount"], message.text
                )

                members = await conn.fetch(
                    "SELECT user_id FROM trip_members WHERE trip_id=$1",
                    trip_id
                )

                for m in members:
                    await conn.execute(
                        "INSERT INTO expense_participants (expense_id,user_id) VALUES ($1,$2)",
                        expense_id, m["user_id"]
                    )

            user_states.pop(user_id)
            await message.answer("✅ Expense added")
            return

# ---------------- CALCULATE + NOTIFY ----------------

async def calculate_and_notify(message):

    user_id = message.from_user.id

    async with pool.acquire() as conn:

        user = await conn.fetchrow(
            "SELECT active_trip_id FROM users WHERE telegram_id=$1",
            user_id
        )

        trip_id = user["active_trip_id"]

        await conn.execute("DELETE FROM debts WHERE trip_id=$1", trip_id)

        expenses = await conn.fetch(
            "SELECT * FROM expenses WHERE trip_id=$1",
            trip_id
        )

        balances = {}

        for e in expenses:
            participants = await conn.fetch(
                "SELECT user_id FROM expense_participants WHERE expense_id=$1",
                e["id"]
            )

            share = e["amount"] / len(participants)

            for p in participants:
                balances[p["user_id"]] = balances.get(p["user_id"], 0) - share

            balances[e["payer_id"]] = balances.get(e["payer_id"], 0) + e["amount"]

        creditors = []
        debtors = []

        for uid, bal in balances.items():
            if bal > 0:
                creditors.append([uid, bal])
            elif bal < 0:
                debtors.append([uid, -bal])

        for d_uid, d_amt in debtors:
            for c in creditors:
                if d_amt == 0:
                    break

                c_uid, c_amt = c
                pay = min(d_amt, c_amt)

                if pay > 0:

                    await conn.execute(
                        "INSERT INTO debts (trip_id,from_user,to_user,amount) VALUES ($1,$2,$3,$4)",
                        trip_id, d_uid, c_uid, pay
                    )

                    # 🔔 уведомления
                    debtor_name = await get_name(d_uid)
                    creditor_name = await get_name(c_uid)

                    await bot.send_message(
                        d_uid,
                        f"💸 You owe {creditor_name}: {round(pay,2)}"
                    )

                    await bot.send_message(
                        c_uid,
                        f"💰 {debtor_name} owes you: {round(pay,2)}"
                    )

                    c[1] -= pay
                    d_amt -= pay

    await message.answer("✅ Debts calculated & sent")

# ---------------- SHOW MY DEBTS ----------------

async def show_my_debts(message):

    user_id = message.from_user.id

    async with pool.acquire() as conn:

        debts = await conn.fetch("""
        SELECT * FROM debts
        WHERE from_user=$1 OR to_user=$1
        """, user_id)

    if not debts:
        await message.answer("🎉 No debts")
        return

    for d in debts:
        from_name = await get_name(d["from_user"])
        to_name = await get_name(d["to_user"])

        text = f"{from_name} → {to_name}: {round(d['amount'],2)} ({d['status']})"

        kb = None

        if d["from_user"] == user_id and d["status"] == "pending":
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Agree", callback_data=f"agree_{d['id']}")
            ]])

        elif d["from_user"] == user_id and d["status"] == "accepted":
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="I paid", callback_data=f"paid_{d['id']}")
            ]])

        elif d["to_user"] == user_id and d["status"] == "paid":
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Confirm", callback_data=f"confirm_{d['id']}")
            ]])

        await message.answer(text, reply_markup=kb)

# ---------------- FINAL REPORT ----------------

async def final_report(message):

    async with pool.acquire() as conn:

        debts = await conn.fetch("""
        SELECT * FROM debts WHERE status != 'received'
        """)

    if not debts:
        await message.answer("🎉 Nobody owes anyone!")
        return

    text = "📊 Open debts:\n\n"

    for d in debts:
        from_name = await get_name(d["from_user"])
        to_name = await get_name(d["to_user"])

        text += f"{from_name} → {to_name}: {round(d['amount'],2)}\n"

    await message.answer(text)

# ---------------- CALLBACKS ----------------

@dp.callback_query(lambda c: c.data.startswith("agree_"))
async def agree(callback: types.CallbackQuery):
    debt_id = int(callback.data.split("_")[1])

    async with pool.acquire() as conn:
        await conn.execute("UPDATE debts SET status='accepted' WHERE id=$1", debt_id)

    await callback.answer("Accepted")

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def paid(callback: types.CallbackQuery):
    debt_id = int(callback.data.split("_")[1])

    async with pool.acquire() as conn:
        await conn.execute("UPDATE debts SET status='paid' WHERE id=$1", debt_id)

    await callback.answer("Marked as paid")

@dp.callback_query(lambda c: c.data.startswith("confirm_"))
async def confirm(callback: types.CallbackQuery):
    debt_id = int(callback.data.split("_")[1])

    async with pool.acquire() as conn:
        await conn.execute("UPDATE debts SET status='received' WHERE id=$1", debt_id)

    await callback.answer("Confirmed")

# ---------------- RUN ----------------

async def main():
    print("🔥 CLEAN BOT STARTED 🔥")

    # 💥 ВОТ ЭТУ СТРОКУ ДОБАВЛЯЕШЬ
    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())