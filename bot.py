import os
import asyncio
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ─── БАЗА ДАННЫХ ───
def init_db():
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT,
            name TEXT,
            phone TEXT,
            time TEXT,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_booking(service, name, phone, time):
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO bookings (service, name, phone, time, date) VALUES (?, ?, ?, ?, ?)",
        (service, name, phone, time, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()
    conn.close()

def get_all_bookings():
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, service, name, phone, time, date FROM bookings ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ─── ШАГИ ЗАПИСИ ───
class Booking(StatesGroup):
    service = State()
    name = State()
    phone = State()
    time = State()

# ─── МЕНЮ ───
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📅 Записаться")]],
    resize_keyboard=True
)

service_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Портретная съёмка")],
        [KeyboardButton(text="💍 Свадебная съёмка")],
        [KeyboardButton(text="👶 Детская съёмка")]
    ],
    resize_keyboard=True
)

time_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Утро (9:00–12:00)"), KeyboardButton(text="День (12:00–17:00)")],
        [KeyboardButton(text="Вечер (17:00–21:00)")]
    ],
    resize_keyboard=True
)

# ─── КОМАНДЫ ───
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я помогу записаться на съёмку к фотографу Анне Соколовой.\n"
        "Нажми кнопку ниже чтобы начать.",
        reply_markup=main_menu
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return

    bookings = get_all_bookings()

    if not bookings:
        await message.answer("📭 Заявок пока нет.")
        return

    text = "📋 Все заявки:\n\n"
    for b in bookings:
        text += (
            f"#{b[0]} · {b[5]}\n"
            f"📸 Услуга: {b[1]}\n"
            f"👤 Имя: {b[2]}\n"
            f"📞 Телефон: {b[3]}\n"
            f"🕐 Время: {b[4]}\n"
            f"─────────────\n"
        )

    await message.answer(text)

# ─── ЗАПИСЬ ───
@dp.message(F.text == "📅 Записаться")
async def start_booking(message: Message, state: FSMContext):
    await state.set_state(Booking.service)
    await message.answer(
        "Шаг 1 из 4\n\n"
        "Какая съёмка вас интересует?",
        reply_markup=service_menu
    )

@dp.message(Booking.service)
async def get_service(message: Message, state: FSMContext):
    await state.update_data(service=message.text)
    await state.set_state(Booking.name)
    await message.answer(
        f"Отличный выбор! ✨\n\n"
        "Шаг 2 из 4\n\n"
        "Как вас зовут?",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Booking.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Booking.phone)
    await message.answer(
        f"Приятно познакомиться, {message.text}! 😊\n\n"
        "Шаг 3 из 4\n\n"
        "Напишите свой номер телефона:"
    )

@dp.message(Booking.phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(Booking.time)
    await message.answer(
        "Шаг 4 из 4\n\n"
        "Выберите удобное время:",
        reply_markup=time_menu
    )

@dp.message(Booking.time)
async def get_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    data = await state.get_data()
    await state.clear()

    save_booking(data['service'], data['name'], data['phone'], data['time'])

    # Уведомление владельцу
    await bot.send_message(
        ADMIN_ID,
        f"🔔 Новая заявка!\n\n"
        f"📸 Услуга: {data['service']}\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"🕐 Время: {data['time']}\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    await message.answer(
        "✅ Заявка принята!\n\n"
        "📋 Ваши данные:\n"
        f"📸 Услуга: {data['service']}\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"🕐 Время: {data['time']}\n\n"
        "Анна свяжется с вами в течение 2 часов. Спасибо! 🙏",
        reply_markup=main_menu
    )

async def main():
    init_db()
    print("Бот запущен! База данных подключена.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
