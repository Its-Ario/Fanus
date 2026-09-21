def _tables(database):
    try:
        return set(database.get_tables())
    except (TypeError, AttributeError):
        return set()


def migrate(migrator, database, **kwargs):
    tables = _tables(database)
    if "student" not in tables or "attendancerecord" in tables:
        return
    from src.storage.models import AttendanceRecord

    database.create_tables([AttendanceRecord], safe=True)


def rollback(migrator, database, **kwargs):
    if "attendancerecord" in _tables(database):
        database.execute_sql('DROP TABLE IF EXISTS "attendancerecord"')
