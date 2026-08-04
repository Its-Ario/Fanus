from pathlib import Path

from peewee import SqliteDatabase

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = BASE_DIR / "data" / "app.db"

DB_PATH.parent.mkdir(exist_ok=True)


db = SqliteDatabase(
    DB_PATH,
    pragmas={
        "journal_mode": "wal",
        "foreign_keys": 1,
        "cache_size": -1024 * 64,
        "synchronous": "normal",
        "temp_store": "RAM",
    },
)


def connect_database():
    if db.is_closed():
        db.connect(reuse_if_open=True)


def close_database():
    if not db.is_closed():
        db.close()
