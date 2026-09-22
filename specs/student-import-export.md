# Student Import / Export — Design

Bulk-onboard students from a spreadsheet at start of year, and export the current
roster view to a file. **Create-only** on import — no updates, no deletes. New
subsystem: there is no `student_ops.py` or import flow today; students are created
one at a time in `NewStudentDialog` (`students_page.py:162`).

## 1. Scope

**In:** `.xlsx` + `.csv` read/write, a four-column template, per-row validation,
a dry-run preview before commit, one audit event, `openpyxl` added as a core
dependency.

**Out:** upsert / updating existing students, editing or deactivating via file,
classroom auto-create, `major` / study-habit / ML columns, grades &
attendance import-export, national-id check-digit validation, fuzzy class-name
matching, threaded parsing. Files are hundreds of rows.

---

## 2. Template / file format

Four columns, Persian headers, this order:

| `نام` | `نام خانوادگی` | `کد ملی` | `کلاس` |
|---|---|---|---|

- Header row required. Columns are located by trimmed header text, not position,
  so column order in the actual file does not matter. A missing required header
  rejects the whole file before any row work (`ValueError`, e.g.
  «ستون «کد ملی» پیدا نشد»).
- `کلاس` = exact `Classroom.name` — the composed name
  (`Classroom.compose_name()`, e.g. `دهم ریاضی فیزیک - الف`).
- `major` is **not** in the file; it is taken from the resolved classroom
  (`major=classroom.major`), same as `NewStudentDialog._save`.
- `.csv` is `utf-8-sig` on both read and write (Excel + Persian).
- No separate "blank template" action — an export of an empty filtered view is a
  headers-only file, which is the template.

---

## 3. `src/storage/student_ops.py` — UI-free module

Sectioned like `grade_ops.py`: parse, write, commit. One file.

```python
ImportRow = namedtuple(
    "ImportRow", ("line", "first_name", "last_name", "national_id", "classroom_name")
)
RowError = namedtuple("RowError", ("line", "national_id", "reason"))  # reason: Persian str
ImportResult = namedtuple("ImportResult", ("created", "skipped", "errors"))
#   created: int                 -> rows written (or would-be-written when commit=False)
#   skipped: list[RowError]      -> national_id already exists, or duplicate line within the file
#   errors:  list[RowError]      -> blank name, invalid national_id, unknown class
```

### parse — `read_roster(path) -> list[ImportRow]`

- Dispatch on `path.suffix.lower()`:
  - `.xlsx` → `openpyxl.load_workbook(path, read_only=True, data_only=True)`, active
    sheet, iterate rows, **`wb.close()` in a `finally`** (read-only workbooks hold a
    file handle).
  - `.csv` → `csv.reader`, `encoding="utf-8-sig"`.
  - anything else → `ValueError("فرمت فایل پشتیبانی نمی‌شود")`.
- Resolve the header row to column indices; raise `ValueError` (Persian message) on
  a missing required header.
- Per data row: strip every cell; `to_ascii_digits` on the national-id cell; skip a
  row where all four cells are blank. `line` = spreadsheet row number (1-based, for
  the error report).
- No DB access, no validation beyond "which column is which".

### write — `write_roster(path, students) -> None`

- `students`: iterable of `Student`.
- `.xlsx` → new `openpyxl.Workbook()`, header row + one row per student
  (`student.classroom.name` for the `کلاس` cell), `wb.save(path)`.
- `.csv` → `csv.writer`, `newline=""`, `encoding="utf-8-sig"`.
- Extension picks the writer; unknown extension → `ValueError`.

### commit — `bulk_create_students(rows, *, commit=True, actor=None) -> ImportResult`

- `rows`: `list[ImportRow]` (already parsed). Pure DB work.
- Preload once: set of every existing `Student.national_id`; `{Classroom.name: Classroom}`.
- Walk `rows` in order, classify each (first failure wins, one `reason` per row):
  1. **error** — `first_name` or `last_name` blank; `national_id` not exactly 10
     ASCII digits (same rule as `NewStudentDialog._save`, no check digit);
     `classroom_name` not in the classroom map.
  2. **skipped** — `national_id` already in the existing set, **or** already seen
     earlier in this file (first valid occurrence wins; later ones skipped with
     «کد ملی تکراری در فایل»).
  3. **create** — otherwise; add its national_id to the seen-set.
- If `commit`: `with db.atomic():` `Student.create(first_name=…, last_name=…,
  national_id=…, classroom=room, major=room.major)` for every **create** row.
  If `commit=False`: no writes; `created` carries the would-create count.
- Return `ImportResult(created, skipped, errors)`.
- An `IntegrityError` at insert time (race between preload and commit) rolls the
  whole `atomic()` back and propagates; the caller shows a failure banner and
  nothing is imported. `ponytail: no partial-commit bookkeeping; a mid-import race is rare and retryable.`
- `actor` accepted for symmetry; auditing is the caller's job (same contract as
  `grade_ops` / `attendance_ops`).

---

## 4. UI — `src/views/pages/students_page.py`

Two `SecondaryButton`s in the header row, left of «دانش آموز جدید»:
«ورود از فایل» (icon `⬆`) and «خروجی فایل» (icon `⬇`).

### Export — `_export_roster`

- `QFileDialog.getSaveFileName`, filter `Excel (*.xlsx);;CSV (*.csv)`, default name
  `دانش‌آموزان.xlsx`.
- Build the **current** query as `reload()` does (search + `major` / `grade` /
  `class` filters + current sort) but **unpaginated**. Refactor: extract the
  query-builder half of `load_students_page` into a shared helper, add
  `load_all_students(...)` beside it that returns the full ordered tuple.
- Pass the result to `write_roster`. Success → transient message in the
  `result_label` style («۱۲۰ دانش‌آموز خروجی گرفته شد»); failure → the existing
  `error_banner`.
- Read-only operation → no audit.

### Import — `_open_import`

- `QFileDialog.getOpenFileName`, filter `Excel/CSV (*.xlsx *.csv)`.
- `read_roster(path)` in `try/except ValueError` → message box on bad format /
  missing header, stop.
- `rows` is parsed **once**. Preview = `bulk_create_students(rows, commit=False)`;
  on confirm = `bulk_create_students(rows, commit=True, actor=current_user)`.
- `ImportPreviewDialog(QDialog)`:
  - summary line — «۱۱۸ افزوده می‌شود · ۸ رد شده · ۴ خطا» (Persian digits).
  - read-only `QTableWidget` of `errors + skipped`, columns `ردیف · کد ملی · دلیل`.
  - «انصراف» / «افزودن» — «افزودن» disabled when would-create is 0.
  - confirm → commit, then `record_audit`, then `self.reload()`.

---

## 5. Wiring, audit, deps

- **Audit** — after a committed import, one event:
  `record_audit(current_user, "student.bulk_import", "Student", None,
  details=f"{result.created} افزوده، {len(result.skipped)} رد، {len(result.errors)} خطا")`.
- `security_panel.py`: `ACTION_LABELS["student.bulk_import"] = "ورود گروهی دانش‌آموزان"`.
- **Permissions** — none beyond what «دانش آموز جدید» already carries (none).
  Bulk and single add stay consistent; deliberate.
- **Deps** — `pyproject.toml` `[project].dependencies` += `openpyxl>=3.1`
  (small, pure-Python; currently only transitive). **No pandas.** `csv` is stdlib.
  Mirror into `requirements.txt`.

---

## 6. Tests — `tests/test_student_import.py`

pytest only, no extra framework.

- `read_roster`: a small `.xlsx` and a `.csv` fixture parse to the same
  `ImportRow` list; `utf-8-sig` Persian round-trips; all-blank rows skipped;
  reordered columns still parse; missing required header raises `ValueError`.
- `bulk_create_students` classification: blank name → error; 9-digit and
  Persian-digit national_id → error / normalized; unknown class → error;
  pre-existing national_id → skipped; in-file duplicate → skipped (first wins);
  clean rows → created. `commit=False` writes nothing and reports the same counts
  as the subsequent `commit=True`.
- `write_roster` → `read_roster` round-trip preserves the four fields.

---

## 7. File touch list

| File | Change |
|---|---|
| `src/storage/student_ops.py` | **new** — parse / write / commit |
| `src/views/pages/students_page.py` | two buttons, `_export_roster`, `_open_import`, `ImportPreviewDialog`, `load_all_students` helper |
| `pyproject.toml`, `requirements.txt` | add `openpyxl>=3.1` |
| `src/views/pages/settings/security_panel.py` | one `ACTION_LABELS` entry |
| `tests/test_student_import.py` | **new** |

No migration — no schema change.
