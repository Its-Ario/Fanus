"""Add author ownership metadata to confidential notes."""

def migrate(migrator, database, **kwargs):
    if "counselornote" not in database.get_tables():
        return
    columns = {column.name for column in database.get_columns("counselornote")}
    if "author_id" not in columns:
        migrator.sql('ALTER TABLE "counselornote" ADD COLUMN "author_id" UUID')
    migrator.sql(
        'CREATE INDEX IF NOT EXISTS "counselornote_author_id" ON "counselornote" ("author_id")'
    )


def rollback(migrator, database, **kwargs):
    # SQLite cannot safely drop a column on every supported version. The forward
    # migration is additive and legacy records intentionally fail closed.
    return
