# FINAL STARTUP VERSION (INVITE + SPLIT + LANG)

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

# ---------------- I18N ----------------

T = {
    "en": {
        "choose_lang": "Choose language",
        "menu": "Menu",
        "create": "Create trip",
        "join": "Join trip",
        "add": "Add expense",
        "calc": "Calculate debts",
        "invite": "Invite code:",
        "enter_code": "Enter code:",
        "amount": "Amount:",
        "comment": "Comment:",
        "select": "Select participants:",
        "done": "Done",
        "created": "Trip created",
        "joined": "Joined trip",
        "added": "Expense added",
        "no_debts": "Nobody owes anyone"
    },
    "ru": {
        "choose_lang": "Выбери язык",
        "menu": "Меню",
        "create": "Создать поездку",
        "join": "Ввести код",
        "add": "Добавить расход",
        "calc": "Посчитать долги",
        "invite": "Код приглашения:",
        "enter_code": "Введи код:",
        "amount": "Сумма:",
        "comment": "Комментарий:",
        "select": "Выбери участников:",
        "done": "Готово",
        "created": "Поездка создана",
        "joined": "Вы присоединились",
        "added": "Расход добавлен",
        "no_debts": "Никто никому не должен"
    }
}

def t(lang, key):
    return T.get(lang, T["en"]).get(key, key)

# ---------------- DB ----------------

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            name TEXT,
            lang TEXT DEFAULT 'en',
            active_trip INT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id SERIAL PRIMARY KEY,
            title TEXT,
            currency TEXT,
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

async def user(uid):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", uid)

async def create_user(uid, name):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO users (telegram_id,name) VALUES ($1,$2) ON CONFLICT DO NOTHING", uid, name)

async def set_lang(uid, lang):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET lang=$1 WHERE telegram_id=$2", lang, uid)

async def set_trip(uid, trip):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET active_trip=$1 WHERE telegram_id=$2", trip, uid)

async def name(uid):
    u = await user(uid)
    return u["name"] if u else str(uid)

# ---------------- UI ----------------

def lang_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="English"), KeyboardButton(text="Русский")]
    ], resize_keyboard=True)

def menu(lang):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t(lang,"create"))],
        [KeyboardButton(text=t(lang,"join"))],
        [KeyboardButton(text=t(lang,"add"))],
        [KeyboardButton(text=t(lang,"calc"))],
    ], resize_keyboard=True)

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(m):
    await create_user(m.from_user.id, m.from_user.full_name)
    await m.answer("🌍", reply_markup=lang_kb())

# ---------------- LANG ----------------

@dp.message(lambda m: m.text in ["English","Русский"])
async def lang(m):
    lang = "en" if m.text=="English" else "ru"
    await set_lang(m.from_user.id, lang)
    await m.answer(t(lang,"menu"), reply_markup=menu(lang))

# ---------------- STATES ----------------

states = {}
select_states = {}

# ---------------- HANDLER ----------------

@dp.message()
async def h(m):

    u = await user(m.from_user.id)
    lang = u["lang"]

    # CREATE
    if m.text == t(lang,"create"):
        states[m.from_user.id] = {"step":"title"}
        await m.answer("Name:")
        return

    # JOIN
    if m.text == t(lang,"join"):
        states[m.from_user.id] = {"step":"join"}
        await m.answer(t(lang,"enter_code"))
        return

    # ADD
    if m.text == t(lang,"add"):
        states[m.from_user.id] = {"step":"amount"}
        await m.answer(t(lang,"amount"))
        return

    # CALC
    if m.text == t(lang,"calc"):
        await calc(m)
        return

    # FLOW
    if m.from_user.id in states:
        s = states[m.from_user.id]

        if s["step"] == "title":
            code = str(uuid.uuid4())[:6]

            async with pool.acquire() as conn:
                trip = await conn.fetchval(
                    "INSERT INTO trips (title,invite_code) VALUES ($1,$2) RETURNING id",
                    m.text, code
                )
                await conn.execute("INSERT INTO members VALUES ($1,$2)", trip, m.from_user.id)

            await set_trip(m.from_user.id, trip)
            states.pop(m.from_user.id)

            await m.answer(f"{t(lang,'created')}\n{t(lang,'invite')} {code}")
            return

        if s["step"] == "join":
            async with pool.acquire() as conn:
                trip = await conn.fetchrow("SELECT * FROM trips WHERE invite_code=$1", m.text)

                if trip:
                    await conn.execute("INSERT INTO members VALUES ($1,$2)", trip["id"], m.from_user.id)
                    await set_trip(m.from_user.id, trip["id"])
                    await m.answer(t(lang,"joined"))
                else:
                    await m.answer("Invalid code")

            states.pop(m.from_user.id)
            return

        if s["step"] == "amount":
            s["amount"] = float(m.text)
            s["step"] = "note"
            await m.answer(t(lang,"comment"))
            return

        if s["step"] == "note":
            s["note"] = m.text
            await select_users(m)
            return

# ---------------- SELECT ----------------

async def select_users(m):

    uid = m.from_user.id

    async with pool.acquire() as conn:
        u = await user(uid)
        members = await conn.fetch("SELECT user_id FROM members WHERE trip_id=$1", u["active_trip"])

    select_states[uid] = {m["user_id"]:True for m in members}

    await draw_select(m)

async def draw_select(m):

    uid = m.from_user.id
    state = select_states[uid]

    kb = []

    for u, v in state.items():
        n = await name(u)
        kb.append([InlineKeyboardButton(text=("✅ " if v else "❌ ")+n, callback_data=f"tog_{u}")])

    kb.append([InlineKeyboardButton(text="Done", callback_data="done")])

    await m.answer("Select:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(lambda c: c.data.startswith("tog_"))
async def tog(c):
    uid = c.from_user.id
    u = int(c.data.split("_")[1])
    select_states[uid][u] = not select_states[uid][u]
    await c.message.delete()
    await draw_select(c.message)

@dp.callback_query(lambda c: c.data=="done")
async def done(c):

    uid = c.from_user.id
    s = states[uid]
    selected = [u for u,v in select_states[uid].items() if v]

    async with pool.acquire() as conn:
        u = await user(uid)
        e = await conn.fetchval(
            "INSERT INTO expenses (trip_id,payer,amount,note) VALUES ($1,$2,$3,$4) RETURNING id",
            u["active_trip"], uid, s["amount"], s["note"]
        )

        for u in selected:
            await conn.execute("INSERT INTO participants VALUES ($1,$2)", e, u)

    states.pop(uid)
    select_states.pop(uid)

    await c.message.answer("Added")
    await c.answer()

# ---------------- CALC ----------------

async def calc(m):

    uid = m.from_user.id

    async with pool.acquire() as conn:

        u = await user(uid)

        ex = await conn.fetch("SELECT * FROM expenses WHERE trip_id=$1", u["active_trip"])

        bal = {}

        for e in ex:
            parts = await conn.fetch("SELECT user_id FROM participants WHERE expense_id=$1", e["id"])

            share = e["amount"]/len(parts)

            for p in parts:
                bal[p["user_id"]] = bal.get(p["user_id"],0) - share

            bal[e["payer"]] = bal.get(e["payer"],0) + e["amount"]

    cred = []
    debt = []

    for u,b in bal.items():
        if b>0: cred.append([u,b])
        if b<0: debt.append([u,-b])

    res=""

    for d,da in debt:
        for c in cred:
            if da==0: break
            cu,ca = c
            pay = min(da,ca)
            if pay>0:
                res += f"{await name(d)} → {await name(cu)}: {round(pay,2)}\n"
                c[1]-=pay
                da-=pay

    await m.answer(res or t((await user(uid))["lang"],"no_debts"))

# ---------------- RUN ----------------

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())