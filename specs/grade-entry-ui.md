# Fanus Exam Model & Grade Entry UI — Design

Supersedes the earlier single-class / single-subject selector grid (same file, uncommitted).
Introduces a first-class **`Exam`** entity: a teacher defines an exam once (name, نوبت, date,
سقف نمره, one or more classes, one or more subjects), then enters every score for it in a
tabbed multi-subject grid.

**Assumption (correct before building if false):** there is **no production grade data**.
`specs/grade-system.md` §9 states the only `AcademicGrade` rows live in seed/tests, and the
model landed one commit ago (`a3a5a88`). Migration `006` therefore drops the moved columns
with **no backfill**, and `seed.py` + four test files are rewritten to create grades through
`Exam`. If real schools have entered grades, the migration needs a data-migration pass
instead.

**In scope:** the `Exam` / `ExamClassroom` models, the `AcademicGrade` reshape, migration
`006`, an Exams list page, a New Exam modal, a tabbed grade grid with column-wise / row-wise
keyboard entry and Persian-digit normalization, batch write + audit, and the downstream
read-site updates.

**Not in scope:** editing an exam definition after creation, Excel/CSV import, کارنامه/PDF,
descriptive (توصیفی) scale, per-subject `max_score`, per-row `weight` editing, hard grade
deletion (stays in the student panel), multi-year history, multi-class exams that mix
grade level or major.

---

## 1. Data model

### 1.1 `Exam` — new (`src/storage/models.py`)

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(100)` | non-empty |
| `exam_date` | `DateField`, indexed | Gregorian `date`; UI shows/parses Persian-digit `YYYY/MM/DD` |
| `term` | `CharField(30)` | one of `GradeTerm.VALUES`; drives معدل vs tracking-only |
| `max_score` | `DoubleField(default=20.0)` | **one per exam**, applied to every subject column; `0 < x <= 20` |
| `grade_level` | `IntegerField` | frozen at creation from the chosen classes |
| `major` | `CharField(50)` | frozen at creation; `(grade_level, major)` gates which classes may join |
| `subjects_json` | `TextField(default="[]")` | ordered JSON list of `subject_name` strings — the grid's score columns |

```python
@property
def subjects(self) -> list[str]:
    try:
        return list(json.loads(self.subjects_json or "[]"))
    except (ValueError, TypeError):
        return []

@subjects.setter
def subjects(self, value):
    self.subjects_json = json.dumps(list(value or []), ensure_ascii=False)
```

Mirrors the `PlannerSettings.weights` / `Student.risk_factors_json` pattern already in the
codebase. Subjects are a render-order list, never queried relationally, so JSON — not a link
table.

`Exam.save()` validation (raise, don't clamp — data-integrity boundary):

```python
def save(self, *args, **kwargs):
    if not (self.name or "").strip():
        raise GradeValidationError("نام آزمون نمی‌تواند خالی باشد.")
    if not self.subjects:
        raise GradeValidationError("حداقل یک درس برای آزمون لازم است.")
    if self.term not in GradeTerm.VALUES:
        raise GradeValidationError("نوبت نامعتبر است.")
    if not (0 < self.max_score <= 20):
        raise GradeValidationError("سقف نمره باید بین ۰ تا ۲۰ باشد.")
    if self.exam_date is None:
        raise GradeValidationError("تاریخ آزمون لازم است.")
    self.name = self.name.strip()
    return super().save(*args, **kwargs)
```

### 1.2 `ExamClassroom` — new link table

| Field | Type | Notes |
|---|---|---|
| `exam` | `ForeignKeyField(Exam, backref="exam_classrooms", on_delete="CASCADE")` | |
| `classroom` | `ForeignKeyField(Classroom, on_delete="CASCADE")` | |

```python
class Meta:
    indexes = ((("exam", "classroom"), True),)   # unique
```

One row per class the exam covers → one tab in the grid. A real FK (not JSON) because a
classroom can be deleted and the exam's class set must stay referentially clean.

### 1.3 `AcademicGrade` — reshaped (`src/storage/models.py`)

| Field | Change |
|---|---|
| `exam` | **new** `ForeignKeyField(Exam, backref="grades", null=True, on_delete="CASCADE")` |
| `score` | **now `DoubleField(null=True)`** — `NULL` = absent/exempt; never written as `0` |
| `subject_name` | **kept** — identifies which subject column a score belongs to |
| `weight` | **kept**, `DoubleField(default=1.0)`, `> 0` — still the معدل weighting escape hatch, still unexposed in the UI |
| `student` | unchanged (`FK Student`, CASCADE) |
| ~~`term`~~ | **dropped** → read through `grade.exam.term` |
| ~~`max_score`~~ | **dropped** → `grade.exam.max_score` |
| ~~`exam_date`~~ | **dropped** → `grade.exam.exam_date` |

Index: drop `(student, subject_name, exam_date)`; add **`(exam, student, subject_name)` unique**.
That triple is the upsert key — one row per student per subject per exam, corrected in place.

`AcademicGrade.save()` after the reshape:

```python
def save(self, *args, **kwargs):
    if not (self.subject_name or "").strip():
        raise GradeValidationError("نام درس نمی‌تواند خالی باشد.")
    if self.weight <= 0:
        raise GradeValidationError("ضریب باید بزرگ‌تر از صفر باشد.")
    if self.score is not None:
        ceiling = self.exam.max_score if self.exam_id else 20.0
        if not (0 <= self.score <= ceiling):
            raise GradeValidationError("نمره باید بین ۰ و سقف نمره باشد.")
    self.subject_name = self.subject_name.strip()
    return super().save(*args, **kwargs)
```

`term` / `max_score` validation moves entirely to `Exam.save()`.

### 1.4 `PUBLIC_MODELS`

Add `Exam`, `ExamClassroom` (before `AcademicGrade` so table creation order resolves the FK).

---

## 2. Migration `006_exam_model.py` (`src/storage/migrations/fanus/`)

```python
# create the two new tables
migrator.create_model(Exam)
migrator.create_model(ExamClassroom)

# reshape academicgrade
migrator.add_fields("academicgrade", exam=ForeignKeyField(Exam, null=True, on_delete="CASCADE"))
migrator.drop_index("academicgrade", "academicgrade_student_id_subject_name_exam_date")
migrator.remove_fields("academicgrade", "term", "max_score", "exam_date")
migrator.add_index("academicgrade", "exam", "student", "subject_name", unique=True)
# score -> nullable
migrator.change_fields("academicgrade", score=DoubleField(null=True))
```

No data backfill (§ assumption). Confirm the exact `peewee_migrate` helper names against an
existing migration in `src/storage/migrations/fanus/` when writing it — `change_fields` /
`drop_index` spelling varies by version. `ponytail: naive drop-and-recreate migration; a
data-migration path is only needed if a school has already entered grades.`

---

## 3. Navigation & Exams list page

`students_page.py` is **unchanged** — keeps the `ثبت نمرات` `SecondaryButton` and the
`open_grade_entry = pyqtSignal()`. `main_window` keeps one page widget wired to that signal;
only the internal class is rewritten.

### `GradeEntryPage` — a `QStackedWidget` of two views

Keeping it one widget means `main_window._navigate_to` / `closeEvent` / the unsaved-changes
guard wiring from the current spec is untouched.

**`ExamListView`** (default):

```
┌───────────────────────────────────────────────────────────────┐
│  ثبت نمرات                                    [ + آزمون جدید ]  │
├───────────────────────────────────────────────────────────────┤
│  نام آزمون        تاریخ       نوبت      کلاس‌ها    درس‌ها   پیشرفت │
│  میان‌ترم زیست    ۱۴۰۵/۰۹/۱۵  نوبت اول  ۲ کلاس    ۱ درس   ۴۲ از ۶۰ │
│  ...                                                            │
└───────────────────────────────────────────────────────────────┘
```

- `QTableView` + a small `QAbstractTableModel` (same idiom as `StudentTableModel`).
- Rows: `Exam.select().order_by(Exam.exam_date.desc())`.
- پیشرفت = filled (non-null score) `/ (Σ active students over the exam's classes × len(subjects))`,
  `to_persian_digits`.
- `EmptyState` "هنوز آزمونی ثبت نشده است" + CTA "آزمون جدید" when none.
- Double-click a row → `ExamGridView` for that exam.
- `+ آزمون جدید` (`PrimaryButton`) → `NewExamDialog`; on accept → `ExamGridView` for the
  new exam.

**`ExamGridView`:** the grid (§5). Header `SecondaryButton("بازگشت", icon="←")` → back to
the list, through the dirty guard.

### Role behaviour

`read_only = bool(current_user and current_user.role == "principal")`:

- list visible; `+ آزمون جدید` hidden.
- grid cells `setReadOnly(True)`, greyed; `ثبت نمرات` hidden; footer shows only the counter.
- no dirty tracking, guard is a no-op.

`counselor` and `assistant` are fully equal.

### Unsaved-changes guard

`GradeEntryPage.has_unsaved_changes()` / `confirm_navigation_away()` behave as in the current
spec, but span **all tabs** of the open exam. Switching list↔grid, or opening a different
exam, runs the guard first. `main_window` integration unchanged.

---

## 4. New Exam modal — `NewExamDialog(QDialog)`

Layout idiom follows `NewStudentDialog`. `setMinimumWidth(430)`.

| Field | Widget | Rule |
|---|---|---|
| نام آزمون | `FormField` | non-empty |
| نوبت | `Dropdown` | `GradeTerm.VALUES` (5 items) |
| تاریخ آزمون | `QLineEdit` (`_field`), Persian-digit `YYYY/MM/DD`, defaults to today | `to_ascii_digits` + `date.fromisoformat`; `ponytail: naive YYYY/MM/DD parse — wire to a Jalali helper if one lands` |
| سقف نمره | `QLineEdit` (`_field`), default `۲۰` | `0 < x <= 20` |
| کلاس‌ها | checkable `QListWidget` | all `Classroom` rows. **When the first class is checked, every classroom whose `(grade_level, major)` differs is disabled + greyed.** Unchecking all re-enables the full list. |
| درس‌ها | checkable `QListWidget` | disabled + empty until ≥1 class is checked; then populated from `subject_options(grade_level, major)` of the checked set. Repopulates (and drops now-invalid checks) if the class selection changes the `(grade_level, major)`. |

Validation on save: name non-empty, ≥1 class, ≥1 subject, date parses, `0 < max_score <= 20`.
Inline `error` `QLabel` (`Colors.ERROR`), same as `NewStudentDialog`.

On accept, in one `db.atomic()`:

```python
exam = Exam(name=…, exam_date=…, term=…, max_score=…,
            grade_level=gl, major=mj)
exam.subjects = checked_subjects            # ordered as subject_options returns them
exam.save(force_insert=True)
for room in checked_classrooms:
    ExamClassroom.create(exam=exam, classroom=room)
```

Then `record_audit(actor, "exam.create", "Exam", target_id=exam.id, details=f"{exam.name} · …")`.

**An exam definition is immutable after creation** for v1 — no edit dialog.
`ponytail: exam definition immutable post-create; add an edit dialog only if schools need to
fix a name typo or add a late class.`

---

## 5. The grade grid — `ExamGridView`

```
┌───────────────────────────────────────────────────────────────┐
│  [← بازگشت]   میان‌ترم زیست     نوبت اول · ۱۴۰۵/۰۹/۱۵ · سقف ۲۰   │
├───────────────────────────────────────────────────────────────┤
│  [ دهم تجربی ۱ ]  [ دهم تجربی ۲ ]        ← tabs (one per class) │
├───────────────────────────────────────────────────────────────┤
│  ردیف  دانش‌آموز            زیست ۱      شیمی ۱                    │
│   ۱    احمدی، سارا         [ ۱۸.۵ ]    [ ۱۶  ]                  │
│   ۲    رضایی، علی          [ ____ ]    [ ۱۴  ]                  │
│   ...                                                           │
├───────────────────────────────────────────────────────────────┤
│  ۴۲ از ۶۰ نمره وارد شده          [ انصراف ]      [ ثبت نمرات ]  │
└───────────────────────────────────────────────────────────────┘
```

### Structure

- Header: back button, `exam.name`, and a read-only `نوبت · تاریخ · سقف` label.
- `QTabWidget`, one tab per `ExamClassroom` (label = `classroom.name`). **No tab bar when
  the exam has a single class** (`tabBar().setVisible(len == 1)` → hidden, single page still
  shown).
- Footer: live `«{filled} از {total} نمره وارد شده»` counter (`to_persian_digits`) summed
  across all tabs; `انصراف` (`SecondaryButton` → `bازگشت` through guard); `ثبت نمرات`
  (`PrimaryButton`, hidden when `read_only`, disabled while any cell on any tab is invalid).

### Each tab = one `_ScoreGrid(QTableWidget)` (existing subclass, reused)

- Columns: `ردیف` · `دانش‌آموز` · then **one score column per `exam.subjects`**, in stored
  order, header = subject name. `SCORE_COLS = range(2, 2 + len(subjects))`.
- Rows: `Student.select().where(Student.classroom == room, Student.is_active)
  .order_by(Student.last_name, Student.first_name)` — not paginated, viewport scrolls.
- Pre-fill: `AcademicGrade.select().where(AcademicGrade.exam == exam,
  AcademicGrade.student << [ids])` → `{(student_id, subject_name): grade}`. Cell text =
  `to_persian_digits(f"{g.score:g}")` when `g.score is not None`, else `""`. A missing row
  and a row with `score IS NULL` both render blank — the difference only matters on save.
- Per-row model: `{student, cells: {subject_name: {"grade_id": id|None, "loaded": str}}}`.
- `EmptyState` per tab when the class has no active students:
  "دانش‌آموزی در این کلاس نیست".
- `read_only`: `setEditTriggers(NoEditTriggers)`, cells greyed (`Colors.TEXT_MUTED` on
  `Colors.SURFACE_HOVER`).

### Keyboard — `_ScoreDelegate`, extended to 2-D movement

The editor's `eventFilter` maps a keypress to a `(row_step, col_step)`, then: `commitData`,
`closeEditor`, and `QTimer.singleShot(0, …)` to select + `editItem` the target score cell
(the one-tick defer is the existing mechanism so the closed editor tears down first).

| Key(s) | Move | Use case |
|---|---|---|
| `Enter` / `Return` / `Down` | next **row**, same subject column | grade all Biology papers top-to-bottom |
| `Shift+Enter` / `Up` | previous row, same column | correct upward |
| `Tab` / `Left` *(RTL: Left = forward)* | next **subject column**, same student | enter one student's whole report card |
| `Shift+Tab` / `Right` | previous subject column, same student | |

- Moves **clamp** at the grid's edges — no wrap, no crossing into another tab.
- A target that isn't a score column is skipped (there are none between score columns, but
  the guard keeps `ردیف`/`دانش‌آموز` non-editable — they already carry `Qt.ItemIsEnabled`
  only).
- On tab activation and on grid load, park the cursor on row 0 / first subject column so
  typing starts entry immediately (existing `AnyKeyPressed` edit trigger + `setCurrentCell`).
- `_ScoreGrid.keyPressEvent` already opens the editor when `Enter` is pressed on a selected
  score cell not being edited — extend its column check from `== SCORE_COL` to
  `in SCORE_COLS`.

`ponytail: QTableWidget + delegate keyboard flow; fall back to a per-cell VBox grid only if
it fights fast entry.`

### Persian numpad normalization — on the fly

The score editor (`createEditor`) gets a `QValidator`:

```python
class _PersianNumberValidator(QValidator):
    def validate(self, text, pos):
        ascii_text = to_ascii_digits(text)
        if ascii_text != text:
            return (QValidator.Acceptable, ascii_text, pos)   # rewrite in place
        if ascii_text == "" or re.fullmatch(r"\d*\.?\d*", ascii_text):
            return (QValidator.Acceptable, ascii_text, pos)
        return (QValidator.Invalid, text, pos)
```

So typing `۱۸.۵` displays `18.5` as it is typed. `commit` re-runs `to_ascii_digits` as the
belt to this brace.

### Empty vs zero

| Cell | On save |
|---|---|
| blank, **no** existing row | not written (student had no score for this subject) |
| blank, existing row | `score` set to `NULL` — student absent/exempt after previously having a score; **row kept, never `0`** |
| `۰` / `0` typed | stored as `0.0` |

`_cell_error(text, max_score)`: blank → `None` (valid, skipped); else `to_ascii_digits` →
`float` → must be in `[0, exam.max_score]`; on failure the cell gets `Colors.ERROR_BG` +
a tooltip and `ثبت نمرات` is disabled until every invalid cell across every tab is fixed or
cleared. No silent clamping (mirrors the model boundary).

### Dirty tracking

A cell is dirty when `to_ascii_digits(text) != to_ascii_digits(cell["loaded"])`. Spans all
tabs. A successful save re-baselines every cell to its saved value and clears dirty. Drives
the footer counter and the §3 navigation guard.

---

## 6. Batch write — `src/storage/grade_ops.py`

```python
SaveResult = namedtuple("SaveResult", ("created", "updated", "cleared"))

def save_grades_bulk(exam, entries, *, actor=None) -> SaveResult:
    """entries: iterable of {student, subject_name, score}
        score: float (incl. 0.0)  -> create or update the (exam, student, subject_name) row
        score: None               -> if a row exists, set score = NULL; else skip
    All writes run in one db.atomic(). A GradeValidationError from the model rolls the
    whole batch back — nothing persists. actor is accepted for symmetry; auditing is the
    caller's job so this module stays UI-free (unchanged rationale).
    """
```

Per entry, keyed `(exam, student, subject_name)`:

| `score` | Existing row? | Action |
|---|---|---|
| number | no | `AcademicGrade.create(exam=exam, student=…, subject_name=…, score=…, weight=1.0)` → `created += 1` |
| number | yes | update `score` in place → `updated += 1` |
| `None` | yes | set `score = NULL` in place → `cleared += 1` |
| `None` | no | skip |

`max_score` and `term` are read from `exam` inside the model — no per-row max field.
Existing-row lookup: one query up front,
`AcademicGrade.select().where(AcademicGrade.exam == exam)` → `{(student_id, subject_name): row}`.

The page builds `entries` from **changed** cells across all tabs, calls `save_grades_bulk`,
then on success writes one audit entry:

```python
record_audit(
    current_user, "grade.bulk_save", "AcademicGrade", target_id=exam.id,
    details="{} · {} ثبت، {} ویرایش، {} غایب".format(
        exam.name,
        to_persian_digits(result.created),
        to_persian_digits(result.updated),
        to_persian_digits(result.cleared),
    ),
)
```

On `GradeValidationError` / db failure the page keeps every typed value and shows the message
in the banner (`_show_banner`), same as the current page.

Add to `ACTION_LABELS` in `src/views/pages/settings/security_panel.py`:

```python
"exam.create": "ایجاد آزمون",
"grade.bulk_save": "ثبت گروهی نمرات",
```

Hard deletion of a grade row stays a student-panel action — out of scope here.
`ponytail: clearing a cell nulls the score but keeps the row; hard delete lives in the
student panel.`

---

## 7. Downstream read sites (the moved columns)

Every read that referenced `term` / `max_score` / `exam_date` on `AcademicGrade` now joins
`Exam`. **Rows with `score IS NULL` are excluded everywhere.**

| Surface | File | Change |
|---|---|---|
| `Student.calculate_gpa()` | `models.py` | iterate `self.grades` with `exam` joined; keep rows where `row.score is not None and row.exam.term in MOADEL_TERMS`; per `subject_name` keep the highest `_TERM_RANK`, tie-break latest `row.exam.exam_date` then `row.created_at`; معدل = `Σ(score·weight)/Σ(weight)`; same `_round2`; no rows → `0.0` |
| weakness map `_weakness_map()` | `src/planner/generator.py` | last 3 rows per `subject_name` with `score is not None`, ordered by `exam.exam_date desc` then `created_at desc`, **all term types**; each contributes `score / exam.max_score`; family / bucket / thresholds unchanged |
| analytics GPA bands | `analytics_page.py:191-236` | the per-student `fn.AVG` query joins `Exam`, adds `.where(Exam.term << MOADEL_TERMS, AcademicGrade.score.is_null(False))` |
| dashboard per-subject % | `dashboard_page.py:96-105` | join `Exam` only to add `AcademicGrade.score.is_null(False)`; still all term types |
| student panel grades table + "۵ امتحان اخیر" | `student_panel.py` | rows read `grade.exam.name` / `.term` / `.exam_date`; `score is None` renders `«غایب»`; score cell red when `score < exam.max_score / 2` |
| `list_grades()` | `grade_ops.py` | `.join(Exam)`; `terms` filter → `Exam.term`; order → `Exam.exam_date.desc(), AcademicGrade.created_at.desc()` |

`weight` stays on `AcademicGrade`, default `1.0`, still not surfaced in any UI.

`ponytail: weakness cut points still not recalibrated (carried from grade-system.md §6);
eyeball against seed data.`

---

## 8. Seed — `src/storage/seed.py`

Rewrite the grade generation from `grade-system.md` §10 to go through `Exam`:

- For each class, create a **نوبت اول** `Exam` covering that class with all
  `subject_options(grade_level, major)` as its subjects, `max_score=20`, a date ~10 weeks
  back; a **نوبت دوم** `Exam` for ~70% of classes, more recent.
- 3–6 **امتحان کلاسی** `Exam`s per class over the last ~8 weeks, each 1–2 subjects,
  `max_score` sometimes `10`.
- 1–2 **آزمون آزمایشی** `Exam`s for grade-12 classes.
- Then `AcademicGrade` rows per (exam, student, subject); leave ~5% of scores `NULL`
  (absent) so the null path has coverage on first run.
- Scores drawn to spread students across all four `GPA_BANDS`.

`ponytail: mock distribution hand-tuned for band spread, not real data (carried over).`

---

## 9. Testing (`tests/`, asserts-only, no framework)

### Rewrites — these construct `AcademicGrade` with `term=` / `exam_date=` directly

- `tests/test_grades.py`, `tests/test_grade_entry.py`, `tests/test_planner.py::_seed`
  (`:131`), `tests/test_auth_and_login.py:121-123`
- Shared helper: `_exam(classroom, subjects, *, term=GradeTerm.NOBAT_1, max_score=20.0,
  exam_date=EXAM)` → creates `Exam` + `ExamClassroom`, returns it; grade helpers take an
  `exam` instead of `term` / `exam_date`.

### New coverage

- `Exam.save()` raises `GradeValidationError` on: empty name, empty subjects, bad `term`,
  `max_score` outside `(0, 20]`, `exam_date=None`.
- `save_grades_bulk`: mixed batch (create + update + clear) → `SaveResult(created, updated,
  cleared)` correct; the `(exam, student, subject_name)` key updates **in place**,
  `AcademicGrade.select().count()` unchanged (no duplicate).
- explicit `0` → stored `0.0`; blank over an existing row → that row's `score IS NULL`,
  row count unchanged; blank with no existing row → nothing written.
- Persian-digit score string `"۱۸.۵"` → stored `18.5`.
- one invalid cell (`score=25`, `exam.max_score=20`) → `GradeValidationError`, and every
  other row in the same batch is absent afterwards (atomic rollback).
- `calculate_gpa`: `score is None` rows skipped; `exam.term` drives the `MOADEL_TERMS`
  filter; across two exams, نوبت دوم beats نوبت اول per subject; a subject with only
  نوبت اول still contributes; `مستمر` / `امتحان کلاسی` / `آزمون آزمایشی` excluded; empty →
  `0.0`.
- widget (`qtbot`): grid for a 2-subject / 2-class exam →
  - cursor starts at row 0, first subject column;
  - `Enter` commits and moves down the **same** subject column; `Shift+Enter` moves up;
  - `Tab` commits and moves to the **next subject column, same row**; `Shift+Tab` back;
  - moves clamp at grid edges, do not cross tabs;
  - `_PersianNumberValidator`: setting `"۱۸.۵"` in the editor yields `"18.5"`.

### Manual checks

- switching class tabs preserves unsaved cells on the tab left behind;
- clearing a cell over an existing grade nulls the score, keeps the row (no delete);
- principal opens the list and a grid read-only, no `ثبت نمرات`, no `آزمون جدید`.

---

## 10. Files touched

| File | Change |
|---|---|
| `src/storage/models.py` | new `Exam`, `ExamClassroom`; reshape `AcademicGrade` (`exam` FK, nullable `score`, drop `term`/`max_score`/`exam_date`, swap index); move `term`/`max_score` validation to `Exam.save()`; rewrite `Student.calculate_gpa()`; register both models in `PUBLIC_MODELS` |
| `src/storage/migrations/fanus/006_exam_model.py` | **new** |
| `src/storage/grade_ops.py` | `save_grades_bulk(exam, entries, …)` rework; `SaveResult` gains `cleared`; `list_grades` joins `Exam` |
| `src/views/pages/grade_entry_page.py` | **rewrite** — `GradeEntryPage` = stack of `ExamListView` + `ExamGridView`; new `NewExamDialog`; tabbed multi-subject grid; `_ScoreDelegate` extended to 2-D keyboard movement; `_PersianNumberValidator` |
| `src/storage/seed.py` | generate `Exam`s then grades; ~5% `NULL` scores |
| `src/planner/generator.py` | `_weakness_map` joins `Exam`; skip null scores |
| `src/views/pages/analytics_page.py` | GPA-band `fn.AVG` joins `Exam`, filters `MOADEL_TERMS` + non-null score |
| `src/views/pages/dashboard_page.py` | per-subject % joins `Exam` for the non-null-score filter |
| `src/views/pages/student_panel.py` | grades table + "۵ امتحان اخیر" read `grade.exam.*`; render `«غایب»` for null score |
| `src/views/pages/settings/security_panel.py` | `ACTION_LABELS` += `exam.create`, `grade.bulk_save` |
| `src/views/main_window.py` | page still wired to `open_grade_entry`; guard/`closeEvent` unchanged |
| `tests/test_grades.py`, `tests/test_grade_entry.py`, `tests/test_planner.py`, `tests/test_auth_and_login.py` | rewrite grade creation via `Exam`; add the new cases in §9 |
| `specs/grade-entry-ui.md` | this document |

---

## 11. `ponytail:` markers to leave in code

| Location | Marker |
|---|---|
| migration `006` | `naive drop-and-recreate; a data-migration path is only needed if a school has already entered grades` |
| `NewExamDialog` date parse | `naive YYYY/MM/DD parse — wire to a Jalali helper if one lands` |
| `Exam` (immutability) | `exam definition immutable post-create; add an edit dialog only if schools need to fix a name typo or add a late class` |
| `_ScoreDelegate` keyboard flow | `QTableWidget + delegate keyboard flow; fall back to a per-cell VBox grid only if it fights fast entry` |
| `save_grades_bulk` cleared-cell path | `clearing a cell nulls the score but keeps the row; hard delete lives in the student panel` |
| `_weakness_map` thresholds | `weakness cut points not recalibrated against the mean-of-3-ratios input; adjust if seed data looks off` |
