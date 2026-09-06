_SHARED = ("id", "created_at", "updated_at", "student_id", "subject_name", "score", "weight")


def _columns(database, table):
    try:
        return {c.name for c in database.get_columns(table)}
    except Exception:
        return set()


def _tables(database):
    try:
        return set(database.get_tables())
    except (TypeError, AttributeError):
        return set()


def migrate(migrator, database, **kwargs):
    if "academicgrade" not in _tables(database):
        return
    if "exam_id" in _columns(database, "academicgrade"):
        return

    from src.storage.models import AcademicGrade

    quoted = ", ".join(f'"{c}"' for c in _SHARED)
    database.execute_sql('DROP TABLE IF EXISTS "academicgrade__old"')
    database.execute_sql('ALTER TABLE "academicgrade" RENAME TO "academicgrade__old"')
    AcademicGrade.create_table(safe=False)
    database.execute_sql(
        f'INSERT INTO "academicgrade" ({quoted}) SELECT {quoted} FROM "academicgrade__old"'
    )
    database.execute_sql('DROP TABLE "academicgrade__old"')


def rollback(migrator, database, **kwargs):
    pass
