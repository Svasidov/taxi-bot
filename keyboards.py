from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard(has_profile: bool):
    buttons = [
        [
            KeyboardButton(text="Открыть путевой лист"),
            KeyboardButton(text="Закрыть путевой лист")
        ],
        [KeyboardButton(text="Последний путевой лист")],
        [KeyboardButton(text="Получить путевой лист по дате")],
        [KeyboardButton(text="Редактировать данные")],
        [KeyboardButton(text="Мои данные")],
        [KeyboardButton(text="Список водителей")],
    ]

    if not has_profile:
        buttons = [
            [KeyboardButton(text="Открыть путевой лист")],
            [KeyboardButton(text="Закрыть путевой лист")],
            [KeyboardButton(text="Последний путевой лист")],
            [KeyboardButton(text="Получить путевой лист по дате")],
            [KeyboardButton(text="Мои данные")]
        ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )
def get_edit_keyboard():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ФИО")],
            [KeyboardButton(text="Автомобиль")],
            [KeyboardButton(text="Госномер")],
            [KeyboardButton(text="Серия/номер")],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )
def get_drivers_keyboard(drivers):
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

    buttons = []

    for user_id, full_name in drivers:
        buttons.append([KeyboardButton(text=f"{user_id} | {full_name}")])

    buttons.append([KeyboardButton(text="Назад")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )
def get_drivers_keyboard(drivers):
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

    buttons = []

    for user_id, full_name in drivers:
        buttons.append([KeyboardButton(text=f"{user_id} | {full_name}")])

    buttons.append([KeyboardButton(text="Назад")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


def get_driver_actions_keyboard():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Смотреть данные водителя")],
            [KeyboardButton(text="Последний лист водителя")],
            [KeyboardButton(text="Лист водителя по дате")],
            [KeyboardButton(text="Изменить данные водителя")],
            [KeyboardButton(text="Открыть лист за водителя")],
            [KeyboardButton(text="Закрыть лист за водителя")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )