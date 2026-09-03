"""Settings structural columns and label normalization."""

MAJOR_MAP = {
    "\u062a\u062c\u0631\u0628\u06cc": "\u0639\u0644\u0648\u0645 \u062a\u062c\u0631\u0628\u06cc",
    "\u0641\u0646\u06cc \u0648 \u062d\u0631\u0641\u0647 \u0627\u06cc": "\u0641\u0646\u06cc \u0648 \u062d\u0631\u0641\u0647\u200c\u0627\u06cc",
    "\u0639\u0645\u0648\u0645\u06cc": "\u0639\u0645\u0648\u0645\u06cc/\u0645\u0639\u0627\u0631\u0641",
}
ORDINALS = {
    1:"\u0627\u0648\u0644",2:"\u062f\u0648\u0645",3:"\u0633\u0648\u0645",4:"\u0686\u0647\u0627\u0631\u0645",5:"\u067e\u0646\u062c\u0645",6:"\u0634\u0634\u0645",
    7:"\u0647\u0641\u062a\u0645",8:"\u0647\u0634\u062a\u0645",9:"\u0646\u0647\u0645",10:"\u062f\u0647\u0645",11:"\u06cc\u0627\u0632\u062f\u0647\u0645",12:"\u062f\u0648\u0627\u0632\u062f\u0647\u0645",
}

def migrate(migrator, database, fake=False, **kwargs):
    if "classroom" not in database.get_tables():
        return
    columns = {column.name for column in database.get_columns("classroom")}
    if "code" not in columns:
        database.execute_sql('ALTER TABLE "classroom" ADD COLUMN "code" VARCHAR(30)')
        database.execute_sql('UPDATE "classroom" SET "code" = "name"')
    for old, new in MAJOR_MAP.items():
        database.execute_sql('UPDATE "students" SET "major" = ? WHERE "major" = ?', (new, old))
        database.execute_sql('UPDATE "classroom" SET "major" = ? WHERE "major" = ?', (new, old))
    duplicates = database.execute_sql('SELECT grade_level, major, code, academic_year, COUNT(*) FROM classroom GROUP BY 1,2,3,4 HAVING COUNT(*) > 1').fetchall()
    if duplicates:
        raise RuntimeError("Duplicate classrooms prevent Settings migration: " + repr(duplicates))
    rows = database.execute_sql('SELECT id, grade_level, major, code FROM classroom').fetchall()
    for identifier, grade, major, code in rows:
        prefix = ORDINALS.get(grade, str(grade))
        name = f"{prefix} - {code}" if major == "\u0639\u0645\u0648\u0645\u06cc/\u0645\u0639\u0627\u0631\u0641" else f"{prefix} {major} - {code}"
        database.execute_sql('UPDATE classroom SET name = ? WHERE id = ?', (name, identifier))
    database.execute_sql('CREATE UNIQUE INDEX IF NOT EXISTS classroom_grade_level_major_code_academic_year ON classroom (grade_level, major, code, academic_year)')
    database.execute_sql('CREATE INDEX IF NOT EXISTS auditlog_created_at ON auditlog (created_at)')

def rollback(migrator, database, fake=False, **kwargs):
    # SQLite cannot safely drop the added column; restore previous labels/indexes only.
    database.execute_sql('DROP INDEX IF EXISTS classroom_grade_level_major_code_academic_year')
    database.execute_sql('DROP INDEX IF EXISTS auditlog_created_at')
