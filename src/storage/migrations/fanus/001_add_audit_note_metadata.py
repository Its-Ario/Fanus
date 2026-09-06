"""Add durable actor and student identifiers to audit events."""

from peewee import UUIDField


def _tables(database):
    # peewee_migrate replays applied migrations with fake=True, which mocks
    # execute_sql; get_tables() then raises on the Mock cursor. Treat that as
    # "nothing to introspect" so the fake replay is a clean no-op.
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
