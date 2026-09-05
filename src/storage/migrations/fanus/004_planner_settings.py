def migrate(migrator, database, fake=False, **kwargs):
    if fake or "plannersettings" in database.get_tables():
        return
    database.execute_sql(
        'CREATE TABLE "plannersettings" ('
        '"id" INTEGER NOT NULL PRIMARY KEY, '
        '"block_minutes" INTEGER NOT NULL DEFAULT 90, '
        '"weights_json" TEXT NOT NULL DEFAULT \'{}\', '
        '"updated_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)'
    )


def rollback(migrator, database, fake=False, **kwargs):
    if fake:
        return
    database.execute_sql('DROP TABLE IF EXISTS "plannersettings"')
