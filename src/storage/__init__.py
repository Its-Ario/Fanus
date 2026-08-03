from src.storage.db import db
from src.storage.models import StudyPlan, User


def init_database():

    db.connect()

    db.create_tables([User, StudyPlan])

    db.close()
