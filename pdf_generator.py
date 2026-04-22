from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "font.ttf")

pdfmetrics.registerFont(TTFont("ArialRU", FONT_PATH))


def draw_line(c, x1, y1, x2, y2):
    c.line(x1, y1, x2, y2)


def draw_box(c, x, y, w, h):
    c.rect(x, y, w, h)


def generate_pdf(
    sheet_id,
    date,
    start_mileage,
    end_mileage,
    full_name,
    car_model,
    car_number,
    car_series,
    status="ОТКРЫТ"
):
    archive_dir = os.path.join(BASE_DIR, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    file_path = os.path.join(archive_dir, f"putevoy_{sheet_id}_{date}.pdf")

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    left = 40
    right = width - 40
    top = height - 40

    c.setFont("ArialRU", 16)
    c.drawCentredString(width / 2, top, "ПУТЕВОЙ ЛИСТ")

    c.setFont("ArialRU", 10)
    c.drawCentredString(width / 2, top - 18, "Легковой автомобиль / такси")

    draw_box(c, 30, 60, width - 60, height - 110)

    y = top - 50

    c.setFont("ArialRU", 11)
    c.drawString(left, y, f"Номер путевого листа: {sheet_id}")
    c.drawString(width / 2, y, f"Дата: {date}")

    y -= 25
    c.drawString(left, y, f"Статус: {status}")

    y -= 25
    draw_line(c, left, y, right, y)

    y -= 25
    c.drawString(left, y, f"Водитель: {full_name}")

    y -= 25
    c.drawString(left, y, f"Автомобиль: {car_model}")

    y -= 25
    c.drawString(left, y, f"Госномер: {car_number}")

    y -= 25
    c.drawString(left, y, f"Серия/номер: {car_series}")

    y -= 30
    draw_line(c, left, y, right, y)

    y -= 30
    c.setFont("ArialRU", 12)
    c.drawString(left, y, "Данные по пробегу")

    y -= 25
    draw_box(c, left, y - 70, right - left, 80)

    c.setFont("ArialRU", 11)
    c.drawString(left + 10, y - 20, f"Начальный пробег: {start_mileage} км")

    if end_mileage is None:
        c.drawString(left + 10, y - 45, "Конечный пробег: —")
        c.drawString(left + 260, y - 20, "Пробег за смену: —")
    else:
        c.drawString(left + 10, y - 45, f"Конечный пробег: {end_mileage} км")
        c.drawString(left + 260, y - 20, f"Пробег за смену: {end_mileage - start_mileage} км")

    y -= 100
    draw_line(c, left, y, right, y)

    y -= 30
    c.setFont("ArialRU", 12)
    c.drawString(left, y, "Отметки")

    y -= 25
    c.setFont("ArialRU", 11)
    c.drawString(left, y, "Медосмотр: ______________________________")

    y -= 25
    c.drawString(left, y, "Тех. осмотр: _____________________________")

    y -= 30
    draw_line(c, left, y, right, y)

    y -= 35
    c.setFont("ArialRU", 12)
    c.drawString(left, y, "Подписи")

    y -= 30
    c.setFont("ArialRU", 11)
    c.drawString(left, y, "Подпись водителя: ________________________")

    y -= 30
    c.drawString(left, y, "Подпись ответственного: __________________")

    c.setFont("ArialRU", 9)
    c.drawString(left, 75, "Документ сформирован автоматически Telegram-ботом")

    c.save()
    return file_path