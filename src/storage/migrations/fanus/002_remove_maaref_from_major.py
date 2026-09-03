OLD_GENERAL_MAJOR = "\u0639\u0645\u0648\u0645\u06cc/\u0645\u0639\u0627\u0631\u0641"
NEW_GENERAL_MAJOR = "\u0639\u0645\u0648\u0645\u06cc"


def _replace_major(database, old, new):
    tables = set(database.get_tables())
    for table in ("classroom", "students"):
        if table in tables:
            database.execute_sql(
                f'UPDATE "{table}" SET "major" = ? WHERE "major" = ?',
                (new, old),
            )


def migrate(migrator, database, fake=False, **kwargs):
    if fake:
        return
    _replace_major(database, OLD_GENERAL_MAJOR, NEW_GENERAL_MAJOR)


def rollback(migrator, database, fake=False, **kwargs):
    if fake:
        return
    _replace_major(database, NEW_GENERAL_MAJOR, OLD_GENERAL_MAJOR)
