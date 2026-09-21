from peewee import UUIDField


def _tables(database):
    try:
        return set(database.get_tables())
    except (TypeError, AttributeError):
        return set()


def migrate(migrator, database, **kwargs):
    if "auditlog" in _tables(database):
        migrator.add_fields(
            "auditlog",
            actor_id=UUIDField(null=True, index=True),
            student_id=UUIDField(null=True, index=True),
        )


def rollback(migrator, database, **kwargs):
    if "auditlog" in _tables(database):
        migrator.drop_columns("auditlog", ["actor_id", "student_id"])
