# Fanus Grade System — Design

## 1. Purpose & scope

An **analytical input layer** over student scores, plus basic in-app display. It feeds three
existing consumers: the counselor dashboard, the analytics GPA bands, and the planner's
weakness map. It is **not** a gradebook — no کارنامه generation, no transcripts, no
parent/PDF exports, no تک‌ماده / قبولی مشروط logic.

**Scale:** 0–20 numeric only. High school (grades 10–12) is the target; middle school (7–9)
works for free. Elementary توصیفی (descriptive, no معدل) is out of scope — the `score` type
leaves room for a `scale` kind later, but only `numeric_20` is implemented.

**This iteration delivers:** the model change, معدل + pass logic, validation, a thin
`grade_ops` write layer, the migration, seed data, display wiring, and the
planner-integration contract. **Deferred:** grade-entry UI, Excel import, multi-year history.

---

## 2. Data model — `AcademicGrade` (`src/storage/models.py:513`)

| Field | Type | Notes |
|---|---|---|
| `student` | FK → Student, CASCADE | unchanged |
| `subject_name` | `CharField(50)`, indexed | catalog value *or* free custom text; non-empty enforced |
| `score` | `DoubleField` | `0 <= score <= max_score` |
| `max_score` | `DoubleField(default=20.0)` | `0 < max_score <= 20` |
| `exam_date` | `DateField(default=today)`, indexed | unchanged |
| `term` | `CharField(30)`, **new** | one of the 5 values below; column default `"مستمر"` |
| `weight` | `DoubleField(default=1.0)`, **new** | معدل weighting escape hatch; `> 0` |
| ~~`exam_type`~~ | — | **dropped**, replaced by `term` |

- **No `academic_year` column** — derived from `student.classroom.academic_year`; grades are
  implicitly current-year.
  `ponytail: grades assumed current-year; add an explicit year field only if multi-year history is ever needed.`
- **New composite index** `(student, subject_name, exam_date)` for "latest per subject" and
  table queries.
- **No unique constraint** on `(subject_name, term)` — duplicates allowed, resolved at read
  (see §4).

`weight` here is for معدل only. It is unrelated to the planner's کنکور `coefficient_for()` in
`src/planner/catalog.py` — keep the two distinct.

---

## 3. Term taxonomy

```python
class GradeTerm:
    NOBAT_1 = "نوبت اول"
    NOBAT_2 = "نوبت دوم"
    MOSTAMAR = "مستمر"
    KELASI = "امتحان کلاسی"  # frequent weekly/daily in-school exams, non-official
    AZMAYESHI = "آزمون آزمایشی"  # external konkoor mocks
    VALUES = (NOBAT_1, NOBAT_2, MOSTAMAR, KELASI, AZMAYESHI)


MOADEL_TERMS = (GradeTerm.NOBAT_1, GradeTerm.NOBAT_2)  # only these feed معدل
_TERM_RANK = {GradeTerm.NOBAT_1: 1, GradeTerm.NOBAT_2: 2}
```

Everything outside `MOADEL_TERMS` is **tracking-only**: stored, displayed, fed to the
planner, but excluded from معدل.

---

## 4. معدل (GPA) — `Student.calculate_gpa()` (`src/storage/models.py:495`)

Zero-arg, returns a **running معدل**:

1. Take all rows where `term in MOADEL_TERMS`.
2. **Per subject**, keep one row: the highest `_TERM_RANK` available (نوبت دوم beats
   نوبت اول). On a tie (duplicate `(subject, term)`): latest `exam_date`, then latest
   `created_at`.
3. معدل = `Sum(score * weight) / Sum(weight)` over those per-subject rows. With all weights
   `1.0` this is the plain mean.
4. **Truncate** to 2 decimals. No rows → `0.0`.

```python
GPA_ROUNDING = (
    "truncate"  # ponytail: school کارنامه truncates; flip to "half_up" for a school that rounds
)


def _round2(x: float) -> float:
    if GPA_ROUNDING == "half_up":
        return math.floor(x * 100 + 0.5) / 100
    return math.floor(x * 100) / 100
```

`ponytail: duplicate (subject, term) rows tolerated, newest wins at read; no unique constraint.`

---

## 5. Pass / fail

```python
PASS_MARK = 10.0
```

Both **derived, never stored**:
- per subject: `score >= PASS_MARK`
- overall: `calculate_gpa() >= PASS_MARK`

Exposed as properties on the grade row and on `Student`. No status enum, no conditional-pass.

---

## 6. Planner integration — `_weakness_map()` (`src/planner/generator.py`)

Contract change:

- Input = **mean of the last 3 rows per `subject_name`** (by `exam_date` desc, then
  `created_at` desc), **across all term types** including `آزمون آزمایشی` — mocks are the
  strongest konkoor-prep weakness signal. Recent-weighted, single-outlier-damped.
- Each row starts as `raw_ratio = score / max_score` so a `/5` امتحان کلاسی and a `/20` نوبت
  combine correctly. For an exam-subject cohort of at least 8 non-absent students in the
  student's own classroom, its effective ratio is `raw_ratio / max(class_top_ratio, 0.50)`.
  Smaller cohorts use `raw_ratio` directly. The 50% floor prevents a universally failed exam
  from being treated as mastery.
- Effective-ratio mean → family via `subject_family()` → existing `weakness_bucket` thresholds →
  `1.0 / 1.5 / 2.0`. **Thresholds carried over unchanged.**
  `ponytail: weakness cut points not recalibrated against the new mean-of-3-ratios input; eyeball against seed data, adjust constants if visibly off.`
- **Custom subject** with no known family: `subject_family()` returns the raw name as a
  one-subject family; `type_for()` falls back to `"light"` (short blocks). The existing
  "≥1 block for any graded subject" guarantee still holds. No crash, no silent drop.

Per-subject معدل (§4) stays on raw `score` — its row set is `MOADEL_TERMS`, always `/20`.

---

## 7. Validation & write layer

### `AcademicGrade.save()` override — single choke point, raises

```python
class GradeValidationError(ValueError):
    pass


def save(self, *args, **kwargs):
    if not (self.subject_name or "").strip():
        raise GradeValidationError("نام درس نمی‌تواند خالی باشد.")
    if not (0 < self.max_score <= 20):
        raise GradeValidationError("سقف نمره باید بین ۰ تا ۲۰ باشد.")
    if not (0 <= self.score <= self.max_score):
        raise GradeValidationError("نمره باید بین ۰ و سقف نمره باشد.")
    if self.term not in GradeTerm.VALUES:
        raise GradeValidationError("نوع آزمون نامعتبر است.")
    if self.weight <= 0:
        raise GradeValidationError("ضریب باید بزرگ‌تر از صفر باشد.")
    return super().save(*args, **kwargs)
```

Raise, don't clamp — this is a data-integrity boundary. No catalog check on `subject_name`
(custom names are allowed).

### `src/storage/grade_ops.py` — new, thin, no UI

```python
create_grade(student, subject_name, score, *, term,
             max_score=20.0, weight=1.0, exam_date=None) -> AcademicGrade
update_grade(grade_id, **fields) -> AcademicGrade
delete_grade(grade_id) -> None
list_grades(student, *, terms=None, subject=None, limit=None) -> list[AcademicGrade]
```

Each write path normalizes Persian digits (`float()` after conversion) and lets
`GradeValidationError` propagate. No Excel import.

### `src/utils/persian_utils.py` — add

```python
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def to_ascii_digits(value) -> str:
    return str(value).translate(_FA_TO_EN)
```

Replaces the ad-hoc reverse map inlined in `src/utils/validators.py:14`.

---

## 8. Display surfaces

Rule: **معدل surfaces filter to `MOADEL_TERMS`; performance/trend surfaces use all term types.**

| Surface | File | Change |
|---|---|---|
| معدل tile | `student_panel.py:171` | `"—"` unless the student has ≥1 `MOADEL_TERMS` row; else `to_persian_digits(f"{gpa:.2f}")` |
| Grades table (new) | student panel | Columns: درس · نمره · نوع · تاریخ, newest first. Default filter: `نوبت اول/دوم` + `مستمر`. Checkbox "نمایش امتحان‌های کلاسی و آزمایشی" reveals the rest. Score cell red when `score < max_score / 2`. |
| "۵ امتحان اخیر" (new) | student panel | Always-visible list, last 5 rows of **any** term type |
| Analytics GPA bands | `analytics_page.py:191-236` | Add `.where(AcademicGrade.term << MOADEL_TERMS)` to the per-student `fn.AVG` aggregation. Students with no نوبت row simply fall out of all bands. |
| Dashboard per-subject % | `dashboard_page.py:96-105` | **Unchanged** — keeps all term types; it's a class-performance bar, not a معدل. |

No new charts. `GPA_BANDS` tuple at `analytics_page.py:43` unchanged.

---

## 9. Migration `005` (`src/storage/migrations/fanus/005_grade_system.py`)

```python
migrator.add_fields(
    "academicgrade",
    term=CharField(max_length=30, default="مستمر"),
    weight=DoubleField(default=1.0),
)
migrator.remove_fields("academicgrade", "exam_type")
migrator.add_index("academicgrade", "student", "subject_name", "exam_date")
```

No data backfill — the only existing `AcademicGrade` rows are in tests/seed. New code always
passes `term` explicitly; the column default only covers those legacy rows.

---

## 10. Seed — `src/storage/seed.py`

Currently seeds 20 students, **no grades**. Add mock grade generation so
dashboard/analytics/planner have realistic data on first run:

- Per student, per subject from `subject_options(grade_level, major)`:
  - `نوبت اول` for all; `نوبت دوم` for ~70% (mid-year feel)
  - 3–6 `امتحان کلاسی` rows over the last ~8 weeks, some `/10` or `/20`
  - 1–2 `آزمون آزمایشی` rows for grade 12
- Scores drawn to give a spread across all four `GPA_BANDS`.

`ponytail: mock distribution hand-tuned for band spread, not real data.`

---

## 11. Tests

**New — `tests/test_grades.py`** (asserts only, no framework):
- `save()` raises `GradeValidationError` on empty subject, `max_score` out of `(0, 20]`,
  `score` out of `[0, max_score]`, bad `term`, `weight <= 0`
- `_round2` truncates (`19.999 -> 19.99`); flips with `GPA_ROUNDING`
- `calculate_gpa`: per-subject نوبت دوم beats نوبت اول; subject with only نوبت اول still
  contributes; `مستمر` / `امتحان کلاسی` / `آزمون آزمایشی` excluded; weighted mean with a
  non-1 `weight`; duplicate `(subject, term)` -> latest `exam_date` wins; empty -> `0.0`
- `grade_ops.create_grade` with Persian-digit strings -> stored as floats
- weakness map: mean of last 3 ratios; mixed `max_score` normalized; custom subject -> own
  family, gets a block

**Fix existing:**
- `tests/test_auth_and_login.py:121-123` — tag the `AcademicGrade.create(...)` rows
  `term="نوبت اول"` so they still land in analytics bands
- `tests/test_planner.py` `_seed()` (`:131`) — tag seed grade rows `term="نوبت اول"`;
  re-verify the three weakness/plan assertions, adjust expected weakness values for the
  mean-of-3 logic

---

## 12. `ponytail:` markers to leave in code

| Location | Marker |
|---|---|
| `AcademicGrade` (no year field) | `grades assumed current-year; add explicit year field only if multi-year history is needed` |
| `calculate_gpa` dup handling | `duplicate (subject, term) rows tolerated, newest wins at read; no unique constraint` |
| `_round2` / `GPA_ROUNDING` | `school کارنامه truncates; flip to half_up for a school that rounds` |
| weakness thresholds | `cut points not recalibrated against the dual-anchor effective-ratio input; adjust if seed data looks off` |
| seed grade generation | `mock distribution hand-tuned for band spread, not real data` |

---

## 13. Not in scope

Grade-entry UI (bulk class x subject x exam grid is the likely later shape —
`subject_options(grade, major)` already exists for the dropdown), Excel/کارنامه import,
descriptive/توصیفی scale, تک‌ماده / مشروط, multi-year transcripts, PDF export, per-subject
unit (واحد) catalog.
