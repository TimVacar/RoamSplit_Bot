import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

import psycopg
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
DEFAULT_TRIP_CURRENCY = os.getenv("DEFAULT_TRIP_CURRENCY", "EUR")
DEFAULT_TRIP_LANGUAGE = os.getenv("DEFAULT_TRIP_LANGUAGE", "en")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["en", "ru", "ro", "it", "fr", "es"]

TRANSLATIONS = {
    "en": {
        "welcome": "Hi. I help groups track trip expenses and settlements.",
        "choose_language": "Choose your language:",
        "main_menu": "Main menu",
        "create_trip": "Create trip",
        "my_trips": "My trips",
        "join_trip": "Join trip",
        "language": "Language",
        "help": "Help",
        "trip_created": "Trip created successfully.",
        "enter_trip_name": "Send trip name.",
        "enter_trip_currency": "Send trip currency. Example: EUR",
        "choose_trip_language": "Choose trip language:",
        "no_trips": "You have no trips yet.",
        "unknown": "I didn't understand that. Use menu buttons.",
        "help_text": "MVP actions: create trip, list trips, join by ID, change language.",
        "enter_trip_id": "Send trip ID. Example: 1",
        "trip_not_found": "Trip not found.",
        "already_member": "You are already a member of this trip.",
        "joined_trip": "You joined the trip:",
    },
    "ru": {
        "welcome": "Привет. Я помогаю группам вести расходы в поездках и взаиморасчёты.",
        "choose_language": "Выбери язык:",
        "main_menu": "Главное меню",
        "create_trip": "Создать поездку",
        "my_trips": "Мои поездки",
        "join_trip": "Вступить в поездку",
        "language": "Язык",
        "help": "Помощь",
        "trip_created": "Поездка успешно создана.",
        "enter_trip_name": "Отправь название поездки.",
        "enter_trip_currency": "Отправь валюту поездки. Например: EUR",
        "choose_trip_language": "Выбери язык поездки:",
        "no_trips": "У тебя пока нет поездок.",
        "unknown": "Не понял сообщение. Используй кнопки меню.",
        "help_text": "MVP-действия: создать поездку, посмотреть поездки, вступить по ID, сменить язык.",
        "enter_trip_id": "Введи ID поездки. Например: 1",
        "trip_not_found": "Поездка не найдена.",
        "already_member": "Ты уже состоишь в этой поездке.",
        "joined_trip": "Ты вступил в поездку:",
    },
    "ro": {
        "welcome": "Salut. Te ajut să gestionezi cheltuielile de grup din călătorii.",
        "choose_language": "Alege limba:",
        "main_menu": "Meniu principal",
        "create_trip": "Creează călătorie",
        "my_trips": "Călătoriile mele",
        "join_trip": "Intră în călătorie",
        "language": "Limbă",
        "help": "Ajutor",
        "trip_created": "Călătoria a fost creată.",
        "enter_trip_name": "Trimite numele călătoriei.",
        "enter_trip_currency": "Trimite valuta călătoriei. Exemplu: EUR",
        "choose_trip_language": "Alege limba călătoriei:",
        "no_trips": "Încă nu ai călătorii.",
        "unknown": "Nu am înțeles mesajul. Folosește butoanele.",
        "help_text": "Acțiuni MVP: creează călătorie, vezi călătoriile, intră după ID, schimbă limba.",
        "enter_trip_id": "Trimite ID-ul călătoriei. Exemplu: 1",
        "trip_not_found": "Călătoria nu a fost găsită.",
        "already_member": "Ești deja membru în această călătorie.",
        "joined_trip": "Ai intrat în călătorie:",
    },
    "it": {
        "welcome": "Ciao. Ti aiuto a gestire le spese di gruppo in viaggio.",
        "choose_language": "Scegli la lingua:",
        "main_menu": "Menu principale",
        "create_trip": "Crea viaggio",
        "my_trips": "I miei viaggi",
        "join_trip": "Unisciti al viaggio",
        "language": "Lingua",
        "help": "Aiuto",
        "trip_created": "Viaggio creato con successo.",
        "enter_trip_name": "Invia il nome del viaggio.",
        "enter_trip_currency": "Invia la valuta del viaggio. Esempio: EUR",
        "choose_trip_language": "Scegli la lingua del viaggio:",
        "no_trips": "Non hai ancora viaggi.",
        "unknown": "Messaggio non riconosciuto. Usa i pulsanti.",
        "help_text": "Azioni MVP: crea viaggio, vedi viaggi, entra tramite ID, cambia lingua.",
        "enter_trip_id": "Invia l'ID del viaggio. Esempio: 1",
        "trip_not_found": "Viaggio non trovato.",
        "already_member": "Sei già membro di questo viaggio.",
        "joined_trip": "Ti sei unito al viaggio:",
    },
    "fr": {
        "welcome": "Bonjour. Je t'aide à gérer les dépenses de groupe en voyage.",
        "choose_language": "Choisissez la langue :",
        "main_menu": "Menu principal",
        "create_trip": "Créer un voyage",
        "my_trips": "Mes voyages",
        "join_trip": "Rejoindre un voyage",
        "language": "Langue",
        "help": "Aide",
        "trip_created": "Voyage créé avec succès.",
        "enter_trip_name": "Envoie le nom du voyage.",
        "enter_trip_currency": "Envoie la devise du voyage. Exemple : EUR",
        "choose_trip_language": "Choisissez la langue du voyage :",
        "no_trips": "Tu n'as pas encore de voyages.",
        "unknown": "Je n'ai pas compris. Utilise les boutons.",
        "help_text": "Actions MVP : créer un voyage, voir les voyages, rejoindre via ID, changer la langue.",
        "enter_trip_id": "Envoie l'ID du voyage. Exemple : 1",
        "trip_not_found": "Voyage introuvable.",
        "already_member": "Tu fais déjà partie de ce voyage.",
        "joined_trip": "Tu as rejoint le voyage :",
    },
    "es": {
        "welcome": "Hola. Te ayudo a gestionar gastos grupales de viaje.",
        "choose_language": "Elige idioma:",
        "main_menu": "Menú principal",
        "create_trip": "Crear viaje",
        "my_trips": "Mis viajes",
        "join_trip": "Unirse al viaje",
        "language": "Idioma",
        "help": "Ayuda",
        "trip_created": "Viaje creado correctamente.",
        "enter_trip_name": "Envía el nombre del viaje.",
        "enter_trip_currency": "Envía la moneda del viaje. Ejemplo: EUR",
        "choose_trip_language": "Elige el idioma del viaje:",
        "no_trips": "Todavía no tienes viajes.",
        "unknown": "No entendí el mensaje. Usa los botones.",
        "help_text": "Acciones MVP: crear viaje, ver viajes, unirse por ID, cambiar idioma.",
        "enter_trip_id": "Envía el ID del viaje. Ejemplo: 1",
        "trip_not_found": "Viaje no encontrado.",
        "already_member": "Ya formas parte de este viaje.",
        "joined_trip": "Te uniste al viaje:",
    },
}

PENDING_INPUTS: dict[int, dict] = {}


@dataclass
class TripCreateDraft:
    title: str
    currency: str
    trip_language: str


def t(lang: str, key: str) -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


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
                    role TEXT NOT NULL DEFAULT 'admin',
                    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    UNIQUE (trip_id, user_id)
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
            return row[0] if row else DEFAULT_TRIP_LANGUAGE

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


def language_keyboard():
    builder = InlineKeyboardBuilder()
    for lang in ["en", "ru", "ro", "it", "fr", "es"]:
        builder.button(text=lang.upper(), callback_data=f"lang:{lang}")
    builder.adjust(3)
    return builder.as_markup()


def trip_language_keyboard():
    builder = InlineKeyboardBuilder()
    for lang in ["en", "ru", "ro", "it", "fr", "es"]:
        builder.button(text=lang.upper(), callback_data=f"triplang:{lang}")
    builder.adjust(3)
    return builder.as_markup()


def main_menu_keyboard(lang: str):
    kb = ReplyKeyboardBuilder()
    kb.button(text=f"✈️ {t(lang, 'create_trip')}")
    kb.button(text=f"🧳 {t(lang, 'my_trips')}")
    kb.button(text=f"🔗 {t(lang, 'join_trip')}")
    kb.button(text=f"🌐 {t(lang, 'language')}")
    kb.button(text=f"❓ {t(lang, 'help')}")
    kb.adjust(2, 2, 1)
    return kb.as_markup(resize_keyboard=True)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = TripDB(DATABASE_URL)


def current_lang(user_id: int) -> str:
    return db.get_user_language(user_id)


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_lang = "en"

    db.upsert_user(
        telegram_user_id=message.from_user.id,
        display_name=message.from_user.full_name,
        username=message.from_user.username,
        language_code=user_lang,
    )

    await message.answer(
        t(user_lang, "welcome"),
        reply_markup=main_menu_keyboard(user_lang),
    )
    await message.answer(
        t(user_lang, "choose_language"),
        reply_markup=language_keyboard(),
    )


@dp.callback_query(F.data.startswith("lang:"))
async def language_callback(query: CallbackQuery):
    lang = query.data.split(":", 1)[1]
    db.set_user_language(query.from_user.id, lang)
    await query.answer("OK")
    await query.message.answer(t(lang, "main_menu"), reply_markup=main_menu_keyboard(lang))


@dp.message(Command("language"))
async def language_command(message: Message):
    lang = current_lang(message.from_user.id)
    await message.answer(t(lang, "choose_language"), reply_markup=language_keyboard())


@dp.message(F.text.startswith("🌐"))
async def language_button(message: Message):
    lang = current_lang(message.from_user.id)
    await message.answer(t(lang, "choose_language"), reply_markup=language_keyboard())


@dp.message(F.text.startswith("✈️"))
async def create_trip_button(message: Message):
    lang = current_lang(message.from_user.id)
    PENDING_INPUTS[message.from_user.id] = {"flow": "create_trip", "step": "title"}
    await message.answer(t(lang, "enter_trip_name"), reply_markup=main_menu_keyboard(lang))


@dp.message(Command("newtrip"))
async def create_trip_command(message: Message):
    lang = current_lang(message.from_user.id)
    PENDING_INPUTS[message.from_user.id] = {"flow": "create_trip", "step": "title"}
    await message.answer(t(lang, "enter_trip_name"), reply_markup=main_menu_keyboard(lang))


@dp.callback_query(F.data.startswith("triplang:"))
async def trip_language_callback(query: CallbackQuery):
    state = PENDING_INPUTS.get(query.from_user.id)
    user_lang = current_lang(query.from_user.id)
    if not state or state.get("flow") != "create_trip" or state.get("step") != "trip_language":
        await query.answer("Start trip creation first")
        return

    trip_lang = query.data.split(":", 1)[1]
    state["trip_language"] = trip_lang

    draft = TripCreateDraft(
        title=state["title"],
        currency=state["currency"],
        trip_language=state["trip_language"],
    )

    trip_id = db.create_trip(query.from_user.id, draft)
    PENDING_INPUTS.pop(query.from_user.id, None)

    await query.answer("OK")
    await query.message.answer(
        f"{t(user_lang, 'trip_created')}\nID: {trip_id}\n{draft.title} | {draft.currency} | {draft.trip_language.upper()}",
        reply_markup=main_menu_keyboard(user_lang),
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

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=main_menu_keyboard(lang))


@dp.message(Command("mytrips"))
async def my_trips_command(message: Message):
    await my_trips_button(message)


@dp.message(F.text.startswith("🔗"))
async def join_trip_button(message: Message):
    lang = current_lang(message.from_user.id)
    PENDING_INPUTS[message.from_user.id] = {"flow": "join_trip", "step": "trip_id"}
    await message.answer(t(lang, "enter_trip_id"), reply_markup=main_menu_keyboard(lang))


@dp.message(Command("jointrip"))
async def join_trip_command(message: Message):
    lang = current_lang(message.from_user.id)
    PENDING_INPUTS[message.from_user.id] = {"flow": "join_trip", "step": "trip_id"}
    await message.answer(t(lang, "enter_trip_id"), reply_markup=main_menu_keyboard(lang))


@dp.message(F.text.startswith("❓"))
async def help_button(message: Message):
    lang = current_lang(message.from_user.id)
    await message.answer(t(lang, "help_text"), reply_markup=main_menu_keyboard(lang))


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

    await message.answer(t(lang, "unknown"), reply_markup=main_menu_keyboard(lang))


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())