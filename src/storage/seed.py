from src.storage import init_database
from src.storage.db import db
from src.storage.models import StudyPlan, User


def seed():

    init_database()

    db.connect()

    User.delete().execute()

    ario = User.create(username="ario", full_name="Ario", age=16)

    StudyPlan.create(student=ario, subject="Math", hours=5)

    StudyPlan.create(student=ario, subject="Physics", hours=3)

    db.close()


if __name__ == "__main__":
    seed()
