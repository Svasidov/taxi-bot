import asyncio
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from keyboards import get_main_keyboard, get_edit_keyboard, get_drivers_keyboard, get_driver_actions_keyboard
from keyboards import get_drivers_keyboard

from config import BOT_TOKEN, ADMIN_ID
from db import (
    init_db,
    get_open_sheet,
    create_sheet,
    close_sheet,
    get_sheet_by_date,
    save_driver,
    get_driver,
    get_last_closed_sheet,
    get_last_end_mileage
)
from keyboards import get_main_keyboard, get_edit_keyboard
from pdf_generator import generate_pdf

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
selected_driver = {}
@dp.message(F.text == "Список водителей")
async def list_drivers(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    import aiosqlite
    from db import DB_NAME

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT user_id, full_name
            FROM drivers
            ORDER BY full_name
        """)
        drivers = await cursor.fetchall()

    if not drivers:
        await message.answer("Нет водителей.")
        return

    await message.answer(
        "Выберите водителя:",
        reply_markup=get_drivers_keyboard(drivers)
    )
@dp.message(F.text.regexp(r"^\d+ \|"))
async def select_driver(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.strip()
    user_id = int(text.split("|")[0].strip())
    selected_driver[message.from_user.id] = user_id

    driver = await get_driver(user_id)
    if not driver:
        await message.answer("Данные водителя не найдены.")
        return

    await message.answer(
        "Водитель выбран.\nВыберите действие:",
        reply_markup=get_driver_actions_keyboard()
    )
@dp.message(F.text == "Смотреть данные водителя")
async def admin_view_driver(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        return

    driver = await get_driver(target_user_id)
    if not driver:
        await message.answer("Данные водителя не найдены.")
        return

    full_name, car_model, car_number, car_series = driver
    open_sheet = await get_open_sheet(target_user_id)

    text = (
        f"ID: {target_user_id}\n"
        f"ФИО: {full_name}\n"
        f"Автомобиль: {car_model}\n"
        f"Госномер: {car_number}\n"
        f"Серия/номер: {car_series}\n"
    )

    if open_sheet:
        sheet_id, date_str, start_mileage = open_sheet
        text += (
            f"\nОткрытый лист:\n"
            f"ID листа: {sheet_id}\n"
            f"Дата: {date_str}\n"
            f"Начальный пробег: {start_mileage}"
        )
    else:
        text += "\nОткрытого листа нет."

    await message.answer(text, reply_markup=get_driver_actions_keyboard())
@dp.message(F.text == "Последний лист водителя")
async def admin_last_sheet(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        return

    result = await get_last_closed_sheet(target_user_id)
    if not result:
        await message.answer("У этого водителя нет закрытых путевых листов.")
        return

    _, date_str, pdf_path = result

    if not pdf_path:
        await message.answer("Файл не найден.")
        return

    pdf_file = FSInputFile(pdf_path)
    await message.answer_document(
        pdf_file,
        caption=f"Последний путевой лист водителя за {date_str}",
        reply_markup=get_driver_actions_keyboard()
    )
@dp.message(F.text == "Изменить данные водителя")
async def admin_edit_driver(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        return

    driver = await get_driver(target_user_id)
    if not driver:
        await message.answer("Данные водителя не найдены.")
        return

    await state.update_data(target_user_id=target_user_id)

    await message.answer(
        format_driver_data(driver) + "\n\nВыберите, что изменить:",
        reply_markup=get_edit_keyboard()
    )
    await state.set_state(SheetState.admin_waiting_edit_choice)

class SheetState(StatesGroup):

    waiting_start_mileage = State()
    waiting_end_mileage = State()
    waiting_date = State()

    waiting_full_name = State()
    waiting_car_model = State()
    waiting_car_number = State()
    waiting_car_series = State()

    waiting_edit_choice = State()
    waiting_new_value = State()
    admin_waiting_edit_choice = State()
    admin_waiting_new_value = State()
    admin_waiting_start_mileage = State()
    admin_waiting_end_mileage = State()
    admin_waiting_date = State()
@dp.message(F.text == "Лист водителя по дате")
async def admin_sheet_by_date_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        return

    await message.answer(
        "Введите дату.\n"
        "Примеры:\n"
        "21.04.2026\n"
        "21042026\n"
        "21-04-2026"
    )
    await state.set_state(SheetState.admin_waiting_date)
@dp.message(SheetState.admin_waiting_date)
async def admin_sheet_by_date_send(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        await state.clear()
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        await state.clear()
        return

    raw_date = message.text.strip()
    normalized_date = normalize_date(raw_date)

    if not normalized_date:
        await message.answer(
            "Неверный формат даты.\n"
            "Введите дату в одном из форматов:\n"
            "21.04.2026\n"
            "21042026\n"
            "21-04-2026"
        )
        return

    result = await get_sheet_by_date(target_user_id, normalized_date)

    if not result:
        await message.answer(
            f"За дату {normalized_date} путевой лист не найден.",
            reply_markup=get_driver_actions_keyboard()
        )
        await state.clear()
        return

    _, pdf_path, status = result

    if status != "closed" or not pdf_path:
        await message.answer(
            f"Путевой лист за {normalized_date} ещё не закрыт.",
            reply_markup=get_driver_actions_keyboard()
        )
        await state.clear()
        return

    pdf_file = FSInputFile(pdf_path)
    await message.answer_document(
        pdf_file,
        caption=f"Путевой лист водителя за {normalized_date}",
        reply_markup=get_driver_actions_keyboard()
    )
    await state.clear()

@dp.message(F.text == "Открыть лист за водителя")
async def admin_open_sheet_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        return

    driver = await get_driver(target_user_id)
    if not driver:
        await message.answer("Данные водителя не найдены.")
        return

    open_sheet = await get_open_sheet(target_user_id)
    if open_sheet:
        await message.answer(
            "У этого водителя уже есть открытый путевой лист.",
            reply_markup=get_driver_actions_keyboard()
        )
        return

    await message.answer("Введите начальный пробег для выбранного водителя:")
    await state.set_state(SheetState.admin_waiting_start_mileage)
@dp.message(SheetState.admin_waiting_start_mileage)
async def admin_open_sheet_save(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        await state.clear()
        return

    if not message.text.isdigit():
        await message.answer("Введите только число.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        await state.clear()
        return

    start_mileage = int(message.text)

    last_end = await get_last_end_mileage(target_user_id)
    if last_end is not None and start_mileage < last_end:
        await message.answer(
            f"Ошибка.\n"
            f"Начальный пробег не может быть меньше предыдущего конечного ({last_end} км)."
        )
        return

    driver = await get_driver(target_user_id)
    if not driver:
        await message.answer("Данные водителя не найдены.")
        await state.clear()
        return

    full_name, car_model, car_number, car_series = driver

    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    opened_at = now.strftime("%d.%m.%Y %H:%M:%S")

    await create_sheet(
        user_id=target_user_id,
        date=date_str,
        opened_at=opened_at,
        start_mileage=start_mileage
    )

    open_sheet = await get_open_sheet(target_user_id)
    if not open_sheet:
        await message.answer("Не удалось открыть путевой лист.")
        await state.clear()
        return

    sheet_id, _, _ = open_sheet

    pdf_path = generate_pdf(
        sheet_id=sheet_id,
        date=date_str,
        start_mileage=start_mileage,
        end_mileage=None,
        full_name=full_name,
        car_model=car_model,
        car_number=car_number,
        car_series=car_series,
        status="ОТКРЫТ"
    )

    # водителю
    try:
        user_pdf = FSInputFile(pdf_path)
        await bot.send_document(
            target_user_id,
            user_pdf,
            caption=f"Ваш путевой лист открыт.\nДата: {date_str}\nНачальный пробег: {start_mileage}"
        )
    except Exception:
        pass

    # админу
    admin_pdf = FSInputFile(pdf_path)
    await message.answer_document(
        admin_pdf,
        caption=(
            f"Путевой лист открыт за водителя.\n"
            f"ФИО: {full_name}\n"
            f"Дата: {date_str}\n"
            f"Начальный пробег: {start_mileage}"
        ),
        reply_markup=get_driver_actions_keyboard()
    )

    await state.clear()
@dp.message(F.text == "Закрыть лист за водителя")
async def admin_close_sheet_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        return

    open_sheet = await get_open_sheet(target_user_id)
    if not open_sheet:
        await message.answer(
            "У этого водителя нет открытого путевого листа.",
            reply_markup=get_driver_actions_keyboard()
        )
        return

    await message.answer("Введите конечный пробег для выбранного водителя:")
    await state.set_state(SheetState.admin_waiting_end_mileage)
@dp.message(F.text == "Закрыть лист за водителя")
async def admin_close_sheet_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        return

    open_sheet = await get_open_sheet(target_user_id)
    if not open_sheet:
        await message.answer(
            "У этого водителя нет открытого путевого листа.",
            reply_markup=get_driver_actions_keyboard()
        )
        return

    await message.answer("Введите конечный пробег для выбранного водителя:")
    await state.set_state(SheetState.admin_waiting_end_mileage)
@dp.message(SheetState.admin_waiting_end_mileage)
async def admin_close_sheet_save(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        await state.clear()
        return

    if not message.text.isdigit():
        await message.answer("Введите только число.")
        return

    target_user_id = selected_driver.get(message.from_user.id)
    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        await state.clear()
        return

    end_mileage = int(message.text)

    open_sheet = await get_open_sheet(target_user_id)
    if not open_sheet:
        await message.answer("Открытый путевой лист не найден.")
        await state.clear()
        return

    driver = await get_driver(target_user_id)
    if not driver:
        await message.answer("Данные водителя не найдены.")
        await state.clear()
        return

    sheet_id, date_str, start_mileage = open_sheet
    full_name, car_model, car_number, car_series = driver

    if end_mileage < start_mileage:
        await message.answer("Конечный пробег не может быть меньше начального.")
        return

    pdf_path = generate_pdf(
        sheet_id=sheet_id,
        date=date_str,
        start_mileage=start_mileage,
        end_mileage=end_mileage,
        full_name=full_name,
        car_model=car_model,
        car_number=car_number,
        car_series=car_series,
        status="ЗАКРЫТ"
    )

    closed_at = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    await close_sheet(sheet_id, closed_at, end_mileage, pdf_path)

    # водителю
    try:
        user_pdf = FSInputFile(pdf_path)
        await bot.send_document(
            target_user_id,
            user_pdf,
            caption=(
                f"Ваш путевой лист закрыт.\n"
                f"Дата: {date_str}\n"
                f"Конечный пробег: {end_mileage}"
            )
        )
    except Exception:
        pass

    # админу
    admin_pdf = FSInputFile(pdf_path)
    await message.answer_document(
        admin_pdf,
        caption=(
            f"Путевой лист закрыт за водителя.\n"
            f"ФИО: {full_name}\n"
            f"Дата: {date_str}\n"
            f"Начальный пробег: {start_mileage}\n"
            f"Конечный пробег: {end_mileage}\n"
            f"Пробег за смену: {end_mileage - start_mileage}"
        ),
        reply_markup=get_driver_actions_keyboard()
    )

    await state.clear()



@dp.message(SheetState.admin_waiting_edit_choice)
async def admin_process_edit_choice(message: Message, state: FSMContext):
    choice = message.text.strip()

    if choice == "Отмена":
        await state.clear()
        await message.answer(
            "Редактирование отменено.",
            reply_markup=get_driver_actions_keyboard()
        )
        return

    if choice not in ["ФИО", "Автомобиль", "Госномер", "Серия/номер"]:
        await message.answer("Выбери кнопку.")
        return

    await state.update_data(edit_choice=choice)
    await message.answer("Введите новое значение:")
    await state.set_state(SheetState.admin_waiting_new_value)
@dp.message(SheetState.admin_waiting_new_value)
async def admin_process_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    choice = data.get("edit_choice")

    if not target_user_id:
        await message.answer("Сначала выбери водителя.")
        await state.clear()
        return

    driver = await get_driver(target_user_id)
    if not driver:
        await message.answer("Данные водителя не найдены.")
        await state.clear()
        return

    full_name, car_model, car_number, car_series = driver
    new_value = message.text.strip()

    if choice == "ФИО":
        full_name = new_value
    elif choice == "Автомобиль":
        car_model = new_value
    elif choice == "Госномер":
        car_number = new_value
    elif choice == "Серия/номер":
        car_series = new_value

    await save_driver(
        user_id=target_user_id,
        full_name=full_name,
        car_model=car_model,
        car_number=car_number,
        car_series=car_series
    )

    await message.answer(
        "Данные водителя обновлены.\n\n" +
        format_driver_data((full_name, car_model, car_number, car_series)),
        reply_markup=get_driver_actions_keyboard()
    )
    await state.clear()



@dp.message(F.text == "Назад")
async def back_handler(message: Message, state: FSMContext):
    await state.clear()
    driver = await get_driver(message.from_user.id)
    kb = get_main_keyboard(has_profile=bool(driver))
    await message.answer("Возврат в главное меню.", reply_markup=kb)

def format_driver_data(driver):
    full_name, car_model, car_number, car_series = driver
    return (
        "Ваши данные:\n"
        f"ФИО: {full_name}\n"
        f"Автомобиль: {car_model}\n"
        f"Госномер: {car_number}\n"
        f"Серия/номер: {car_series}"
    )


def normalize_date(date_text: str):
    date_text = date_text.strip()

    try:
        return datetime.strptime(date_text, "%d.%m.%Y").strftime("%d.%m.%Y")
    except ValueError:
        pass

    try:
        return datetime.strptime(date_text, "%d-%m-%Y").strftime("%d.%m.%Y")
    except ValueError:
        pass

    if re.fullmatch(r"\d{8}", date_text):
        try:
            return datetime.strptime(date_text, "%d%m%Y").strftime("%d.%m.%Y")
        except ValueError:
            pass

    return None
@dp.message(F.text == "Список водителей")
async def list_drivers(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    import aiosqlite
    from db import DB_NAME

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT user_id, full_name FROM drivers
        """)
        drivers = await cursor.fetchall()

    if not drivers:
        await message.answer("Нет водителей.")
        return

    kb = get_drivers_keyboard(drivers)
    await message.answer("Выберите водителя:", reply_markup=kb)
selected_driver = {}
@dp.message(F.text.regexp(r"^\d+ \|"))
async def select_driver(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text
    user_id = int(text.split("|")[0].strip())

    selected_driver[message.from_user.id] = user_id

    await message.answer(
        f"Выбран водитель ID: {user_id}\n"
        f"(дальше будем работать с ним)"
    )

@dp.message(CommandStart())
async def start_handler(message: Message):
    driver = await get_driver(message.from_user.id)
    kb = get_main_keyboard(has_profile=bool(driver))
    await message.answer("Бот готов к работе.", reply_markup=kb)


@dp.message(F.text == "Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    driver = await get_driver(message.from_user.id)
    kb = get_main_keyboard(has_profile=bool(driver))
    await message.answer("Действие отменено.", reply_markup=kb)


@dp.message(F.text == "Мои данные")
async def profile_handler(message: Message, state: FSMContext):
    driver = await get_driver(message.from_user.id)

    if driver:
        kb = get_main_keyboard(has_profile=True)
        await message.answer(format_driver_data(driver), reply_markup=kb)
        return

    await message.answer("Введите ФИО водителя:")
    await state.set_state(SheetState.waiting_full_name)


@dp.message(SheetState.waiting_full_name)
async def save_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer("Введите марку машины:")
    await state.set_state(SheetState.waiting_car_model)


@dp.message(SheetState.waiting_car_model)
async def save_car_model_step(message: Message, state: FSMContext):
    await state.update_data(car_model=message.text.strip())
    await message.answer("Введите госномер машины:")
    await state.set_state(SheetState.waiting_car_number)


@dp.message(SheetState.waiting_car_number)
async def save_car_number_step(message: Message, state: FSMContext):
    await state.update_data(car_number=message.text.strip())
    await message.answer("Введите серию/номер:")
    await state.set_state(SheetState.waiting_car_series)


@dp.message(SheetState.waiting_car_series)
async def save_car_series_step(message: Message, state: FSMContext):
    data = await state.get_data()

    await save_driver(
        user_id=message.from_user.id,
        full_name=data["full_name"],
        car_model=data["car_model"],
        car_number=data["car_number"],
        car_series=message.text.strip()
    )

    kb = get_main_keyboard(has_profile=True)
    await message.answer("Данные сохранены.", reply_markup=kb)
    await state.clear()


@dp.message(F.text == "Редактировать данные")
async def edit_profile_handler(message: Message, state: FSMContext):
    driver = await get_driver(message.from_user.id)

    if not driver:
        kb = get_main_keyboard(has_profile=False)
        await message.answer("Сначала заполни «Мои данные».", reply_markup=kb)
        return

    await message.answer(
        format_driver_data(driver) + "\n\nВыберите, что изменить:",
        reply_markup=get_edit_keyboard()
    )
    await state.set_state(SheetState.waiting_edit_choice)


@dp.message(SheetState.waiting_edit_choice)
async def process_edit_choice(message: Message, state: FSMContext):
    choice = message.text.strip()

    if choice == "Отмена":
        await state.clear()
        driver = await get_driver(message.from_user.id)
        kb = get_main_keyboard(has_profile=bool(driver))
        await message.answer("Редактирование отменено.", reply_markup=kb)
        return

    if choice not in ["ФИО", "Автомобиль", "Госномер", "Серия/номер"]:
        await message.answer("Выбери кнопку.")
        return

    await state.update_data(edit_choice=choice)
    await message.answer("Введите новое значение:")
    await state.set_state(SheetState.waiting_new_value)


@dp.message(SheetState.waiting_new_value)
async def process_new_value(message: Message, state: FSMContext):
    driver = await get_driver(message.from_user.id)

    if not driver:
        kb = get_main_keyboard(has_profile=False)
        await message.answer("Данные не найдены.", reply_markup=kb)
        await state.clear()
        return

    full_name, car_model, car_number, car_series = driver
    data = await state.get_data()
    choice = data["edit_choice"]
    new_value = message.text.strip()

    if choice == "ФИО":
        full_name = new_value
    elif choice == "Автомобиль":
        car_model = new_value
    elif choice == "Госномер":
        car_number = new_value
    elif choice == "Серия/номер":
        car_series = new_value

    await save_driver(
        user_id=message.from_user.id,
        full_name=full_name,
        car_model=car_model,
        car_number=car_number,
        car_series=car_series
    )

    kb = get_main_keyboard(has_profile=True)
    await message.answer(
        "Данные обновлены.\n\n" + format_driver_data((full_name, car_model, car_number, car_series)),
        reply_markup=kb
    )
    await state.clear()


@dp.message(F.text == "Открыть путевой лист")
async def open_sheet_handler(message: Message, state: FSMContext):
    driver = await get_driver(message.from_user.id)
    kb = get_main_keyboard(has_profile=bool(driver))

    if not driver:
        await message.answer("Сначала заполни «Мои данные».", reply_markup=kb)
        return

    open_sheet = await get_open_sheet(message.from_user.id)
    if open_sheet:
        await message.answer("У вас уже есть открытый путевой лист. Сначала закройте его.", reply_markup=kb)
        return

    await message.answer("Введите начальный пробег:")
    await state.set_state(SheetState.waiting_start_mileage)


@dp.message(SheetState.waiting_start_mileage)
async def save_start_mileage(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите только число.")
        return

    start_mileage = int(message.text)

    last_end = await get_last_end_mileage(message.from_user.id)
    if last_end is not None and start_mileage < last_end:
        await message.answer(
            f"Ошибка.\n"
            f"Начальный пробег не может быть меньше предыдущего конечного ({last_end} км).\n"
            f"Введите корректный пробег."
        )
        return

    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    opened_at = now.strftime("%d.%m.%Y %H:%M:%S")

    await create_sheet(
        user_id=message.from_user.id,
        date=date_str,
        opened_at=opened_at,
        start_mileage=start_mileage
    )

    open_sheet = await get_open_sheet(message.from_user.id)
    driver = await get_driver(message.from_user.id)

    if not open_sheet or not driver:
        kb = get_main_keyboard(has_profile=bool(driver))
        await message.answer("Ошибка при создании путевого листа.", reply_markup=kb)
        await state.clear()
        return

    sheet_id, _, _ = open_sheet
    full_name, car_model, car_number, car_series = driver

    pdf_path = generate_pdf(
        sheet_id=sheet_id,
        date=date_str,
        start_mileage=start_mileage,
        end_mileage=None,
        full_name=full_name,
        car_model=car_model,
        car_number=car_number,
        car_series=car_series,
        status="ОТКРЫТ"
    )

    pdf_file = FSInputFile(pdf_path)
    kb = get_main_keyboard(has_profile=True)

    await message.answer_document(
        pdf_file,
        caption=f"Путевой лист открыт.\nДата: {date_str}\nНачальный пробег: {start_mileage}",
        reply_markup=kb
    )

    admin_text = (
        f"Водитель открыл путевой лист.\n"
        f"ФИО: {full_name}\n"
        f"Автомобиль: {car_model}\n"
        f"Госномер: {car_number}\n"
        f"Дата: {date_str}\n"
        f"Начальный пробег: {start_mileage}"
    )

    await bot.send_message(ADMIN_ID, admin_text)

    admin_pdf = FSInputFile(pdf_path)
    await bot.send_document(
        ADMIN_ID,
        admin_pdf,
        caption=f"Открытый путевой лист: {full_name} ({date_str})"
    )

    await state.clear()
@dp.message(F.text == "Список водителей")
async def list_drivers(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    import aiosqlite
    from db import DB_NAME

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT user_id, full_name, car_model, car_number
            FROM drivers
        """)
        rows = await cursor.fetchall()

    if not rows:
        await message.answer("Водителей нет.")
        return

    text = "Список водителей:\n\n"

    for user_id, full_name, car_model, car_number in rows:
        text += (
            f"ID: {user_id}\n"
            f"{full_name}\n"
            f"{car_model} | {car_number}\n\n"
        )

    await message.answer(text)

@dp.message(F.text == "Закрыть путевой лист")
async def close_sheet_handler(message: Message, state: FSMContext):
    open_sheet = await get_open_sheet(message.from_user.id)
    driver = await get_driver(message.from_user.id)
    kb = get_main_keyboard(has_profile=bool(driver))

    if not open_sheet:
        await message.answer("У вас нет открытого путевого листа.", reply_markup=kb)
        return

    await message.answer("Введите конечный пробег:")
    await state.set_state(SheetState.waiting_end_mileage)


@dp.message(SheetState.waiting_end_mileage)
async def save_end_mileage(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите только число.")
        return

    end_mileage = int(message.text)
    open_sheet = await get_open_sheet(message.from_user.id)
    driver = await get_driver(message.from_user.id)

    if not open_sheet:
        kb = get_main_keyboard(has_profile=bool(driver))
        await message.answer("Открытый путевой лист не найден.", reply_markup=kb)
        await state.clear()
        return

    if not driver:
        kb = get_main_keyboard(has_profile=False)
        await message.answer("Сначала заполни «Мои данные».", reply_markup=kb)
        await state.clear()
        return

    sheet_id, date_str, start_mileage = open_sheet
    full_name, car_model, car_number, car_series = driver

    if end_mileage < start_mileage:
        await message.answer("Конечный пробег не может быть меньше начального.")
        return

    pdf_path = generate_pdf(
        sheet_id=sheet_id,
        date=date_str,
        start_mileage=start_mileage,
        end_mileage=end_mileage,
        full_name=full_name,
        car_model=car_model,
        car_number=car_number,
        car_series=car_series,
        status="ЗАКРЫТ"
    )
    closed_at = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    await close_sheet(sheet_id, closed_at, end_mileage, pdf_path)

    pdf_file = FSInputFile(pdf_path)
    kb = get_main_keyboard(has_profile=True)
    await message.answer_document(
        pdf_file,
        caption="Путевой лист закрыт и сохранён.",
        reply_markup=kb
    )
    await state.clear()


@dp.message(F.text == "Последний путевой лист")
async def last_sheet_handler(message: Message):
    driver = await get_driver(message.from_user.id)
    kb = get_main_keyboard(has_profile=bool(driver))

    result = await get_last_closed_sheet(message.from_user.id)

    if not result:
        await message.answer("У вас ещё нет закрытых путевых листов.", reply_markup=kb)
        return

    _, date_str, pdf_path = result

    if not pdf_path:
        await message.answer("Файл не найден.", reply_markup=kb)
        return

    pdf_file = FSInputFile(pdf_path)
    await message.answer_document(
        pdf_file,
        caption=f"Последний путевой лист за {date_str}",
        reply_markup=kb
    )


@dp.message(F.text == "Получить путевой лист по дате")
async def get_by_date_handler(message: Message, state: FSMContext):
    await message.answer(
        "Введите дату.\n"
        "Примеры:\n"
        "21.04.2026\n"
        "21042026\n"
        "21-04-2026"
    )
    await state.set_state(SheetState.waiting_date)


@dp.message(SheetState.waiting_date)
async def send_sheet_by_date(message: Message, state: FSMContext):
    raw_date = message.text.strip()
    normalized_date = normalize_date(raw_date)

    driver = await get_driver(message.from_user.id)
    kb = get_main_keyboard(has_profile=bool(driver))

    if not normalized_date:
        await message.answer(
            "Неверный формат даты.\n"
            "Введите дату в одном из форматов:\n"
            "21.04.2026\n"
            "21042026\n"
            "21-04-2026",
            reply_markup=kb
        )
        return

    result = await get_sheet_by_date(message.from_user.id, normalized_date)

    if not result:
        await message.answer(
            f"За дату {normalized_date} путевой лист не найден.",
            reply_markup=kb
        )
        await state.clear()
        return

    _, pdf_path, status = result

    if status != "closed" or not pdf_path:
        await message.answer(
            f"Путевой лист за {normalized_date} ещё не закрыт.",
            reply_markup=kb
        )
        await state.clear()
        return

    pdf_file = FSInputFile(pdf_path)
    await message.answer_document(
        pdf_file,
        caption=f"Путевой лист за {normalized_date}",
        reply_markup=kb
    )
    await state.clear()


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())