import aiosqlite

DB_NAME = "database.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS trip_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            opened_at TEXT,
            closed_at TEXT,
            start_mileage INTEGER,
            end_mileage INTEGER,
            status TEXT,
            pdf_path TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            car_model TEXT,
            car_number TEXT,
            car_series TEXT
        )
        """)
        await db.commit()


async def get_open_sheet(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id, date, start_mileage
            FROM trip_sheets
            WHERE user_id=? AND status='open'
            ORDER BY id DESC LIMIT 1
        """, (user_id,))
        return await cursor.fetchone()


async def create_sheet(user_id, date, opened_at, start_mileage):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO trip_sheets (user_id, date, opened_at, start_mileage, status)
            VALUES (?, ?, ?, ?, 'open')
        """, (user_id, date, opened_at, start_mileage))
        await db.commit()


async def close_sheet(sheet_id, closed_at, end_mileage, pdf_path):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE trip_sheets
            SET closed_at=?, end_mileage=?, status='closed', pdf_path=?
            WHERE id=?
        """, (closed_at, end_mileage, pdf_path, sheet_id))
        await db.commit()


async def get_sheet_by_date(user_id, date):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id, pdf_path, status
            FROM trip_sheets
            WHERE user_id=? AND date=?
            ORDER BY id DESC LIMIT 1
        """, (user_id, date))
        return await cursor.fetchone()


async def save_driver(user_id, full_name, car_model, car_number, car_series):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO drivers (user_id, full_name, car_model, car_number, car_series)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name=excluded.full_name,
                car_model=excluded.car_model,
                car_number=excluded.car_number,
                car_series=excluded.car_series
        """, (user_id, full_name, car_model, car_number, car_series))
        await db.commit()


async def get_driver(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT full_name, car_model, car_number, car_series
            FROM drivers
            WHERE user_id=?
        """, (user_id,))
        return await cursor.fetchone()


async def get_last_closed_sheet(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id, date, pdf_path
            FROM trip_sheets
            WHERE user_id=? AND status='closed'
            ORDER BY id DESC
            LIMIT 1
        """, (user_id,))
        return await cursor.fetchone()


async def get_last_end_mileage(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT end_mileage
            FROM trip_sheets
            WHERE user_id=? AND status='closed'
            ORDER BY id DESC
            LIMIT 1
        """, (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None