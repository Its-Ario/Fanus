def _tables(database):
    try:
        return set(database.get_tables())
    except (TypeError, AttributeError):
        return set()


def migrate(migrator, database, **kwargs):
    tables = _tables(database)
    if "classroom" not in tables or "exam" in tables:
        return
    from src.storage.models import Exam, ExamClassroom

    database.create_tables([Exam, ExamClassroom], safe=True)


def rollback(migrator, database, **kwargs):
    if "exam" in _tables(database):
        database.execute_sql('DROP TABLE IF EXISTS "examclassroom"')
        database.execute_sql('DROP TABLE IF EXISTS "exam"')
