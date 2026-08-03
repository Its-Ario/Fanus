from src.storage.db import close_database, connect_database, db
from src.storage.models import ALL_MODELS


def init_database():

    connect_database()
    db.create_tables(ALL_MODELS)

    close_database()
