def migrate(migrator, database, fake=False, **kwargs):
    if fake or "schoolprofile" not in database.get_tables():
        return
    columns = {column.name for column in database.get_columns("schoolprofile")}
    if "school_start_time" not in columns:
        database.execute_sql(
            'ALTER TABLE "schoolprofile" ADD COLUMN "school_start_time" VARCHAR(5) NOT NULL DEFAULT \'07:30\''
        )
    if "school_end_time" not in columns:
        database.execute_sql(
            'ALTER TABLE "schoolprofile" ADD COLUMN "school_end_time" VARCHAR(5) NOT NULL DEFAULT \'13:30\''
        )


def rollback(migrator, database, fake=False, **kwargs):
    # SQLite cannot drop columns safely. Keep the stored values on rollback.
    return
