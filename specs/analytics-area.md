# Spec — Analytics Page (آمار — School Overview)

Status: agreed design, frontier fully explored. Ready to implement. Four data blockers
(see "Pre-existing conditions") mean some panels ship showing empty/default states until
separate work lands — this is expected and accepted for v1.

## Context

FANUS is an offline-first PyQt5 (`5.15.9`) desktop app, Python 3.8-compatible, Peewee `3.17.0`
+ SQLite WAL, peewee-migrate, RTL Persian UI (Vazir font, `Qt.RightToLeft` set globally in
`main.py`). The Analytics page is a new primary destination reached from the existing `📊 آمار`
sidebar item, currently `lambda: print("TODO")` in `main_window._setup_navigation`
(`src/views/main_window.py:82`).

The page shows aggregate data for all students in the school, to help the counselor and the
principal spot macro trends, evaluate academic risk, and measure study-plan adherence. It reads
`src/data/fanus.db` only — no network, no vault.

## Goals

- Four read-only analytics panels over school-wide data, filterable by grade and major.
- All aggregation done SQL-side (Peewee `fn.COUNT` / `fn.AVG` / `GROUP BY`); no Python
  iteration over student sets.
- Runs acceptably on a dual-core Windows 7 / 2 GB machine.

## Non-goals (deferred, not this build)

- **Cross-page click-through** — clicking a bar does not navigate to or filter the Student
  Directory. (`load_students_page` has no grade/major param; adding one is out of scope.)
- **Interactive time window** — no month/term/year filter. Panel 2 is locked to a trailing
  8-week window; the other panels are all-time within the grade/major filter.
- **Hover tooltips** on bars.
- **QtCharts** — not a dependency (see below). No new runtime dependency of any kind.
- **Worker-thread queries** — queries run synchronously on the UI thread.
- Building the ML risk-persist job, attendance capture, per-subject check-ins, or a CSP solver
  (all named as blockers below).

## Pre-existing conditions this spec must work around

- **`QtChart` is not available.** `import PyQt5.QtChart` fails in the project venv and system
  Python; `PyQt5-Qt5==5.15.2` does **not** bundle it (that needs a separate `PyQtChart`
  package). Charts are custom `QPainter` widgets — the app already paints custom widgets
  (`ui_kit.py:450` `ProgressBar`, `students_page.py:104` `RiskBadgeDelegate`).
- **Nothing populates `Student.risk_level`.** The field exists (`CharField`, default `"Low"`,
  indexed) but `src/models/predictor.py:RiskPredictor.predict_student_risk` is only ever called
  from tests. No scheduler or hook recomputes and persists it. **Panel 1 will show every real
  student as LOW** until a recompute-and-persist job exists (separate work). Panel ships anyway,
  reading the field per the single-source-of-risk rule.
- **`AttendanceRecord` has no readers or writers and no excused/unexcused enum.** `status` is
  free text (default `"present"`), `reason` is nullable free text. The table is likely empty.
  **Panel 3 will show its "insufficient data" overlay** until attendance capture is built.
- **GPA / معدل is never stored.** `Student.calculate_gpa()` computes a Python mean of
  `academicgrade.score` on demand. Panel 3 must derive it in SQL via a subquery (§Panel 3).
- **No CSP solver, no per-subject planned/actual hours stored.** `grep csp|solver|planned_hours`
  → zero hits. Planned hours are recoverable from `StudySession.duration_minutes`; per-subject
  *actual* hours do not exist anywhere. **Panel 4 is planned-hours-only.**
- **`DailyCheckIn` is a day-level aggregate**, not linked to individual `StudySession` rows:
  `total_sessions` / `completed_sessions` / `completion_rate` per student per day. Rows exist
  only for days a student actually checked in.
- **No terms/periods table, no Jalali calendar library.** `academic_year` is free text on
  `SchoolProfile` (singleton `id=1`) and `Classroom`. "Current week" is derived ad hoc in
  `dashboard_page.py:50` (`_week_start` — Gregorian, Saturday-based); reuse that.
- **`src/storage/seed.py` is stale/broken** (`StudyPlan.create(subject=, hours=)` — those kwargs
  don't exist on the model). Unrelated to this build, but it blocks seeding demo data.

---

## 1. Shell & integration

- New `AnalyticsPage(QWidget)` added to `MainWindow`'s `QStackedWidget` at a new index; the
  `📊 آمار` nav item's `lambda: print("TODO")` (`main_window.py:82`) becomes
  `lambda: self._navigate_to(N)`, matching the pattern used for other pages
  (`_setup_navigation`, `main_window.py:71-85`). Navigation is already guarded by the
  unsaved-settings check in `_navigate_to`.
- **Lazy load:** override `showEvent`, gate first build on a `self._loaded` flag, then call
  `self.reload()` — same pattern as `students_page.py:373-376` and `settings_page.py:158-163`.
- **Refresh:** `reload()` runs on **every** `showEvent` (not just the first) and on every filter
  change. Aggregates are cheap; a counselor returning to the tab expects current numbers. No
  session cache.
- **Threading:** `reload()` runs the four queries synchronously on the UI thread. Budget: four
  indexed Peewee aggregates on a single-school dataset, expected < 200 ms. Revisit only if
  profiling on the target hardware says otherwise.

### Files

```
src/views/pages/
├── analytics_page.py        # AnalyticsPage(QWidget) + load_analytics_data()
└── components/
    ├── bar_chart.py          # BarChartWidget (vertical-grouped + horizontal modes)
    └── line_chart.py         # LineChartWidget
tests/
└── test_analytics.py         # Panel 3 band bucketing + Panel 2 week aggregation
```

`bar_chart.py` / `line_chart.py` may live in `src/views/components/` alongside `ui_kit.py`
if that reads better; they are generic and reusable.

## 2. Data layer

Module-level loader in `analytics_page.py`, mirroring `load_dashboard_data`
(`dashboard_page.py:54-121`):

```python
@dataclass(frozen=True)
class AnalyticsData:
    panel1: ...  # per-class or school-wide risk counts + `collapsed: bool`
    panel2: ...  # 8 weekly completion points (value or None for gap) + labels
    panel3: ...  # per-band {avg_absences, n} + `enough_data: bool`
    panel4: ...  # per-subject planned hours, descending


def load_analytics_data(grade: int | None = None, major: str | None = None) -> AnalyticsData: ...
```

- **Filter application:** every panel query does `.join(Classroom)` and applies
  `Classroom.grade_level == grade` (if not None) and `Classroom.major == major` (if not None).
  Filter on `Classroom.*`, **not** the denormalised `Student.major` (the two can drift).
- **Student scope:** every aggregate and every `n` counts `Student.is_active == True` only,
  matching `load_dashboard_data`.
- All maths in SQL. No `for student in ...` loops over query results.

## 3. Layout

- Top: a filter bar with two `QComboBox`es.
- Body: a 2×2 `QGridLayout` of `Card` panels (`ui_kit.py:597`), each panel a chart widget with
  a `SectionHeader` title (`ui_kit.py:478`).
- The whole page sits in a `QScrollArea` so small screens can scroll rather than clip.
- Panel titles carry the unit, since the charts have no y-axis: e.g.
  `پنل ۳: میانگین غیبت بر حسب بازه معدل`, `پنل ۴: ساعت برنامه‌ریزی‌شده هفتگی به تفکیک درس`.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 📈 تحلیل و آمار کلی مدرسه                                                  │
├──────────────────────────────────────────────────────────────────────────┤
│ [ پایه تحصیلی: همه ▾ ]            [ رشته تحصیلی: همه ▾ ]                   │
├────────────────────────────────────┬─────────────────────────────────────┤
│ پنل ۱: توزیع سطح ریسک به تفکیک کلاس │ پنل ۲: روند پایبندی به برنامه        │
│ (میله‌ای گروهی)                     │ (خطی — ۸ هفته اخیر)                 │
├────────────────────────────────────┼─────────────────────────────────────┤
│ پنل ۳: میانگین غیبت بر حسب بازه معدل│ پنل ۴: ساعات برنامه‌ریزی‌شده دروس    │
│ (میله‌ای — همراه با n=تعداد)         │ (میله‌ای افقی)                      │
└────────────────────────────────────┴─────────────────────────────────────┘
```

## 4. Filter bar

| Filter | Widget | Items |
| --- | --- | --- |
| پایه تحصیلی | `QComboBox` | `همه` (`data=None`) + one item per int from `grade_options(SchoolProfile.get_instance().type)` (`models.py:65`). |
| رشته تحصیلی | `QComboBox` | `همه` (`data=None`) + one item per `AcademicMajor` value (`models.py:39-46`). |

- Populate with `addItem(label, data)` (same as `students_page.py:169-177`).
- `currentIndexChanged` on either combo → `self.reload()`. No apply button.
- Combined filter is **AND**. Page opens at همه / همه.

## 5. Chart widgets

Custom `QPainter`. Both inherit the app font (Vazir), RTL, and theme colours
(`src/styles/theme.py`). All displayed numbers pass through
`src/utils/persian_utils.py:to_persian_digits`; percent uses the literal `٪` (U+066A); hours
show one decimal.

### `BarChartWidget`

- Modes: **vertical grouped** (Panels 1, 3) and **horizontal** (Panel 4).
- Draws: baseline, category labels, and one painted value label per bar. **No y-axis ticks, no
  gridlines** — every bar is already labelled, so an axis scale is redundant.
- Bar scaling: longest bar = a fixed fraction of the plot area; round the implied max up to a
  "nice" number internally for stable layout, but don't render it.
- Accepts a list of category groups, each with 1–3 `(value, colour, label)` series entries.

### `LineChartWidget`

- Single polyline, marker per point, painted value label per point.
- Baseline + x category labels, no y-axis.
- A `None` value = **gap**: break the line, draw no marker.

### Empty-state overlay

Both widgets accept an `overlay_text: str | None`. When set, the widget paints the panel frame
with a centered rounded box (see `students_page.py:104` `RiskBadgeDelegate` for the rounded-box
paint idiom) and skips all data drawing:

- zero rows / no students in filter → `اطلاعاتی برای نمایش وجود ندارد`
- below-threshold N → `داده کافی موجود نیست` + a second line naming the threshold, e.g.
  `حداقل ۱۰ دانش‌آموز برای محاسبه لازم است`

## 6. Panels

### Panel 1 — Burnout risk distribution by class

- **Source:** `Student.risk_level` (`"High"` / `"Medium"` / `"Low"`) counted per
  `Classroom.name`.
- **Query:** `select(Classroom.name, Student.risk_level, fn.COUNT(Student.id))
  .join(Classroom).where(Student.is_active & <filters>)
  .group_by(Classroom.name, Student.risk_level)`.
- **Render:** vertical grouped bar, one category per class, three series —
  HIGH = `theme.ERROR` (🔴 ریسک بالا), MEDIUM = `theme.WARNING` (🟡 ریسک متوسط),
  LOW = `theme.SUCCESS` (🟢 ریسک پایین).
- **Overflow / collapse:** if `grade is None and major is None` **and** distinct class count
  `> 8`, collapse to **three school-wide bars** (total HIGH / MEDIUM / LOW) and set a
  `collapsed` flag the panel can surface in its subtitle
  (`نمای کل مدرسه — برای تفکیک کلاسی، پایه یا رشته را انتخاب کنید`). Per-class detail returns
  once a grade or major filter is active.
- **Low-N overlay:** total filtered active-student count `N < 10`.
- **Known blocker:** all real students read LOW until a predictor-persist job exists.

### Panel 2 — Trailing 8-week plan completion trend

- **Window:** eight Saturday-aligned calendar weeks ending with the current (partial) week.
  Reuse `dashboard_page.py:50` `_week_start`; week _k_ spans `[start_k, start_k + 7)`.
  Decoupled from any filter except grade/major.
- **Per-week metric:** cohort ratio
  `SUM(DailyCheckIn.completed_sessions) / SUM(DailyCheckIn.total_sessions) * 100`
  over check-ins whose `date` falls in the week, for students matching the filter. **Recompute
  from the two columns — do not use the stored `completion_rate`** (avoids drift).
- **Zero-assigned week** (`SUM(total_sessions)` is 0 or NULL) → emit `None` → gap in the line.
- **X labels:** relative — `۷ هفته پیش` … `۱ هفته پیش`, then `هفته جاری` for the last point.
- **Overlay:** total check-in rows across the 8 weeks `< 5` → `داده کافی موجود نیست`.
- **Semantics / known ceiling:** because `DailyCheckIn` rows exist only for days a student
  checked in, this reads as *"completion among students who engaged that week"* — a student who
  silently stops checking in drops out of the line rather than dragging it toward 0. Upgrade
  path: expand the `StudySession` weekly schedule to concrete dates to measure true no-show
  adherence.

### Panel 3 — Average unexcused absences by GPA band

- **GPA source (single SQL statement, no Python loop):** a per-student subquery
  `SELECT student_id, AVG(score) AS gpa, COUNT(score) AS grade_count
   FROM academicgrade GROUP BY student_id HAVING COUNT(score) > 0`
  — students with **no** grade rows are excluded entirely (a `0.0` from `calculate_gpa()` is not
  a real zero).
- **Bands (half-open):** `زیر ۱۲` = `[0, 12)`, `۱۲–۱۵` = `[12, 15)`, `۱۵–۱۸` = `[15, 18)`,
  `۱۸–۲۰` = `[18, 20]`. Assign via `CASE` on the subquery's `gpa`.
- **Absence definition:** an `AttendanceRecord` row counts as an absence when
  `status NOT IN ('present', '')`. (`reason IS NOT NULL` could later split excused/unexcused;
  not in v1.)
- **Per band:** `n` = distinct students in the band (matching the grade/major filter and
  `is_active`); value = `total absence rows in band / n`.
- **Render:** vertical bar, one per band. Bar label shows the average; category label shows
  `معدل ۱۸–۲۰ (n=۲۴)`. When a band's `n < 10`, draw a small `(نمونه کوچک)` tag under that bar.
- **Panel overlay:** total filtered active-student count `N < 10`, or the attendance table has
  zero rows → `اطلاعاتی برای نمایش وجود ندارد`.
- **Known blocker:** `AttendanceRecord` is currently unpopulated — expect the overlay.

### Panel 4 — Subject workload (planned hours)

- **Source:** `SUM(StudySession.duration_minutes) / 60.0` grouped by
  `StudySession.subject_name`, joined `StudySession → StudyPlan → Student → Classroom`, filtered
  by grade/major and `Student.is_active`.
- **Subjects:** only those with `SUM(duration_minutes) > 0` in the filtered set. **No hardcoded
  subject list, no zero-height bars.** Sort descending by hours.
- **Render:** horizontal bar, single series, `theme.PRIMARY` (teal). Bar label = hours to one
  decimal, Persian digits. Y category labels = `subject_name` verbatim as stored.
- **Overlay:** no rows → `اطلاعاتی برای نمایش وجود ندارد`.
- **Scope note:** planned only. Per-subject *actual* hours are not in the schema; a
  planned-vs-actual comparison needs new `DailyCheckIn` fields + a check-in UI change.

## 7. Performance targets (dual-core Win7 / 2 GB)

| Metric | Target | How |
| --- | --- | --- |
| First page render | < 500 ms | Lazy build on first `showEvent`. |
| Filter repaint | < 200 ms | SQL-side aggregation; four queries; reuse the four chart widgets, swap their data and `update()`. |
| Memory | no unbounded growth | Chart widgets are reused across reloads, not recreated. Zero Python iteration over student rows. |

The earlier "< 15 ms render" figure is dropped — unachievable and unmeasurable on the target.

## 8. Tests

`tests/test_analytics.py`, seeding a temp SQLite DB (follow the fixture style in
`tests/test_auth_and_login.py`):

1. **Panel 3 band bucketing** — students with grades straddling 12 / 15 / 18, plus a
   no-grade student; assert each lands in the correct half-open band, the no-grade student is
   excluded, `n` per band is right, and the average-absences maths matches a hand computation.
2. **Panel 2 week aggregation** — check-ins across several Saturday weeks including one week
   with zero assigned sessions; assert the cohort `SUM/SUM` per week, that the zero-assigned
   week yields `None` (gap), and that the window is exactly 8 weeks ending on the current one.

No framework beyond the existing `pytest` setup; no per-panel exhaustive suite.

## 9. Open decisions

None. Frontier fully explored.
