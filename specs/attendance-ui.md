# Daily Attendance — Design

Roll-call for one class on one day. The **assistant** (`معاون`) enters and edits
records; the **principal** and **counselor** open the same page read-only. The
`AttendanceRecord` model and its `(student, date)` unique index already exist — no
schema change, no migration.

## Data

`AttendanceRecord(student, date, status, reason)`. `status` ∈
`AttendanceStatus.VALUES` = `present / absent / late / excused` (Persian labels in
`AttendanceStatus.PERSIAN`). `AttendanceRecord.save()` rejects any other status
(`AttendanceValidationError`) and normalizes a blank `reason` to `NULL`. One row
per student per day; `present` is the implied default and is not stored unless a
reason is attached or a prior row exists.

## `src/storage/attendance_ops.py` (UI-free, mirrors `grade_ops`)

- `save_attendance_bulk(record_date, entries, *, actor=None) -> SaveResult(created, updated)`
  — `entries` = `{student, status, reason}`, keyed `(student, record_date)`. One
  `db.atomic()`. `present` + no reason + no existing row → skipped. A row whose
  `(status, reason)` is unchanged is not counted. Any model
  `AttendanceValidationError` rolls the whole batch back. `actor` accepted for
  symmetry; auditing is the caller's job.
- `list_attendance(student, *, since=None, statuses=None, limit=None)` — read
  helper, ordered by date desc. Not yet wired to a UI surface.

## `src/views/pages/attendance_page.py` — `AttendancePage(QWidget)`

- `read_only = bool(current_user and current_user.role != "assistant")`.
- Selectors: class `Dropdown` + `PersianDatePicker` (Jalali, defaults today).
- Grid `QTableWidget`: `ردیف · دانش‌آموز · وضعیت · توضیح`. `وضعیت` is a per-row
  `Dropdown` cell widget (defaults `حاضر`); `توضیح` is a free-text cell. Rows =
  active students of the class, ordered by name. Pre-filled from existing rows for
  the chosen class+date. `EmptyState` when the class has no active students.
- `read_only`: status combos disabled, reason cells non-editable, no save button.
- Footer: exception counter («۲ غایب · ۱ تأخیر» / «همه حاضر»), `انصراف`, and
  `ثبت حضور و غیاب` (enabled only while dirty).
- Dirty tracking compares each row's `(status, reason)` to its loaded baseline;
  `has_unsaved_changes()` / `confirm_navigation_away()` gate class/date switches,
  the back button, `main_window._navigate_to`, and `closeEvent` — same shape as
  `GradeEntryPage`.
- Save → `attendance_ops.save_attendance_bulk` in a try/except (banner on failure),
  then one `record_audit(user, "attendance.bulk_save", "AttendanceRecord", …)`, then
  reload + re-baseline.

## Wiring

- `students_page.py`: `open_attendance = pyqtSignal()` + a «حضور و غیاب»
  `SecondaryButton` beside «ثبت نمرات».
- `main_window.py`: page added to the stack, wired like `grade_entry_page`
  (open/back + the two navigation guards). Reached from the students-page button;
  no sidebar item (matches grade entry).
- `security_panel.py`: `ACTION_LABELS["attendance.bulk_save"] = "ثبت گروهی حضور و غیاب"`.

## Not in scope

Per-period/hourly attendance, bulk "mark all absent", attendance summaries or
absence counts in the student panel or analytics (the analytics absence query
already treats every non-`present` status as an absence), CSV export, editing
another day from within the grid (use the date picker).

## Tests — `tests/test_attendance.py` (asserts + `qtbot`, no framework)

Model rejects unknown status; bulk create then in-place update with no duplicate
row; `present`+no-reason writes nothing; reason cleared on return to `present`;
`list_attendance` `since` / `statuses` filters; page is read-only for a
non-assistant (combos disabled, no save button); an assistant's status change is
dirty, saves an `absent` row, and re-baselines.
