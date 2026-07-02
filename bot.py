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
            date TEXT,
            status TEXT DEFAULT 'active',
            user_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_booking(service, name, phone, time, user_id):
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO bookings (service, name, phone, time, date, user_id) VALUES (?, ?, ?, ?, ?, ?)",
        (service, name, phone, time, datetime.now().strftime("%d.%m.%Y %H:%M"), user_id)
    )
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return booking_id

def cancel_booking(booking_id):
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def get_booking_by_id(booking_id):
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, service, name, phone, time, date, status FROM bookings WHERE id = ?", (booking_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_users():
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM bookings WHERE user_id IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_all_bookings():
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, service, name, phone, time, date, status FROM bookings ORDER BY id DESC")
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
        "Я помогу записаться на съёмку к фотографу Анне Соколовой.\n\n"
"/portfolio — посмотреть услуги и цены\n"
"Или нажми кнопку ниже чтобы записаться 👇",
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
        status = "✅ Активна" if b[6] == "active" else "❌ Отменена"
        text += (
            f"#{b[0]} · {b[5]} · {status}\n"
            f"📸 Услуга: {b[1]}\n"
            f"👤 Имя: {b[2]}\n"
            f"📞 Телефон: {b[3]}\n"
            f"🕐 Время: {b[4]}\n"
            f"─────────────\n"
        )

    await message.answer(text)
@dp.message(Command("portfolio"))
async def cmd_portfolio(message: Message):
    await message.answer(
        "📸 Портфолио Анны Соколовой\n\n"
        "Вот примеры моих работ по каждой услуге:"
    )

    await message.answer(
        "👤 Портретная съёмка\n\n"
        "Студийные и уличные портреты.\n"
        "Индивидуальные и парные.\n\n"
        "💰 от 8 000 ₽ · 2 часа · 30 фото"
    )

    await message.answer(
        "💍 Свадебная съёмка\n\n"
        "Весь день рядом — от сборов до первого танца.\n"
        "Живые эмоции без постановок.\n\n"
        "💰 от 40 000 ₽ · весь день · 200+ фото"
    )

    await message.answer(
        "👶 Детская съёмка\n\n"
        "Снимаю игру, удивление и смех.\n"
        "Нахожу общий язык с детьми любого возраста.\n\n"
        "💰 от 6 000 ₽ · 1.5 часа · 25 фото"
    )

    await message.answer(
        "Хотите записаться на съёмку?\n"
        "Нажмите кнопку ниже 👇",
        reply_markup=main_menu
    )
@dp.message(F.text.startswith("❌ Отменить запись #"))
async def cancel_handler(message: Message):
    try:
        booking_id = int(message.text.split("#")[1])
        booking = get_booking_by_id(booking_id)

        if not booking:
            await message.answer("❌ Заявка не найдена.")
            return

        if booking[6] == "cancelled":
            await message.answer("⚠️ Эта заявка уже отменена.")
            return

        cancel_booking(booking_id)

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return

    # Получаем текст после команды /broadcast
    text = message.text.replace("/broadcast", "").strip()

    if not text:
        await message.answer(
            "📢 Чтобы отправить рассылку напиши:\n\n"
            "/broadcast текст сообщения\n\n"
            "Например:\n"
            "/broadcast Привет! В декабре скидка 20% на все съёмки 🎄"
        )
        return

    users = get_all_users()

    if not users:
        await message.answer("📭 Пока нет клиентов для рассылки.")
        return

    success = 0
    failed = 0

    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                f"📢 Сообщение от Анны Соколовой:\n\n{text}"
            )
            success += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {success}\n"
        f"❌ Не доставлено: {failed}"
    )

        # Уведомление владельцу
        await bot.send_message(
            ADMIN_ID,
            f"⚠️ Заявка #{booking_id} отменена!\n\n"
            f"📸 Услуга: {booking[1]}\n"
            f"👤 Имя: {booking[2]}\n"
            f"📞 Телефон: {booking[3]}\n"
            f"🕐 Время: {booking[4]}"
        )

        await message.answer(
            f"✅ Заявка #{booking_id} успешно отменена.\n\n"
            "Если захотите записаться снова — нажмите кнопку ниже 👇",
            reply_markup=main_menu
        )

    except Exception as e:
        await message.answer("❌ Что-то пошло не так. Попробуйте снова.")

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

    booking_id = save_booking(
        data['service'], data['name'],
        data['phone'], data['time'],
        message.from_user.id
    )

    # Уведомление владельцу
    await bot.send_message(
        ADMIN_ID,
        f"🔔 Новая заявка #{booking_id}!\n\n"
        f"📸 Услуга: {data['service']}\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"🕐 Время: {data['time']}\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    # Кнопка отмены
    cancel_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"❌ Отменить запись #{booking_id}")],
            [KeyboardButton(text="📅 Записаться")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"✅ Заявка #{booking_id} принята!\n\n"
        "📋 Ваши данные:\n"
        f"📸 Услуга: {data['service']}\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"🕐 Время: {data['time']}\n\n"
        "Анна свяжется с вами в течение 2 часов. Спасибо! 🙏",
        reply_markup=cancel_menu
    )

async def main():
    init_db()
    print("Бот запущен! База данных подключена.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
