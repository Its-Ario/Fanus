# Spec — Student Panel (پرونده تحصیلی — Per-Student Record)

Status: agreed design, frontier fully explored. Ready to implement. Scoped as a **UI shell**:
the scheduling engine and PDF export are stubs this pass (see "Non-goals").

## Context

FANUS is an offline-first PyQt5 (`5.15.9`) desktop app, Python 3.8-compatible, Peewee `3.17.0`
+ SQLite WAL, RTL Persian UI. Today, double-clicking a row in `StudentsPage`
(`src/views/pages/students_page.py:439`) opens `StudentDetailsDialog` — a small flat-label
modal. This spec replaces that with a full page: a 3-tab student record reached by drilling
into the students list.

The data model already carries everything this page needs: `StudyPlan` (status,
confidence_score, is_approved, is_ai_generated), `StudySession` (day/time/subject/duration/
is_locked), `DailyCheckIn` (completion_rate), `Student.risk_level`, and `CounselorNote` (an
existing encrypted, vault-gated model with no UI today). No schema changes are required.

`src/planner/generator.py` exists with three stubs — `generate_plan`, `optimize_plan`,
`plan_to_pdf` — all `raise NotImplementedError`. An earlier attempt at a plans area
(`src/planner/`, `src/views/pages/plans/`, tests) was started and later deleted from disk
(only stale `.pyc` remained); this spec does not resurrect or depend on that work.

## Goals

- One reusable `StudentPanel` page, pushed onto `MainWindow`'s `QStackedWidget`, showing a
  3-tab record for a single student: summary/history, weekly study plan, confidential notes.
- Manual study-plan creation and editing work end-to-end against real `StudyPlan`/
  `StudySession` rows.
- Confidential notes tab reuses the existing vault/PIN infrastructure as-is.

## Non-goals (deferred, not this build)

- **The scheduling engine** (`generate_plan`, `optimize_plan`) — CSP/constraint design is a
  separate problem. "⚡ تولید مجدد" ships **disabled**.
- **PDF export** (`plan_to_pdf`) — "🖨️ چاپ برنامه A4 PDF" ships **disabled**. When built, prefer
  `QPrinter`/`QPainter` (already in PyQt5) over adding a PDF dependency — none is installed
  today (`reportlab`/`fpdf`/`weasyprint` all absent).
- **`is_locked` toggle** on sessions in the manual editor — meaningless until regeneration
  exists that would need to respect it. Field stays on the model, unused by this UI.
  (`ponytail:` add the lock toggle alongside the scheduling engine.)
- **Editing or deleting confidential notes** — create + list only, keeping notes an immutable
  audit trail.
- **A generic page-level dirty-navigation guard.** Today only `SettingsPage` has
  `confirm_navigation_away()`, hardcoded into `MainWindow._navigate_to`
  (`main_window.py:89-98`). This page doesn't need it: the manual plan editor is a self-
  contained Save/Cancel flow, so leaving the panel can never strand unsaved edits.
- **Subject picker / curriculum list** — no `Subject` model exists anywhere in the codebase;
  `subject_name` is free text on every model that has it (`AcademicGrade`, `StudySession`) and
  in every query that groups by it (`analytics_page.py:246`). The manual editor's subject field
  stays free text, matching that convention.

## Pre-existing conditions this spec must work around

- **Pages are static.** `MainWindow._setup_navigation` (`main_window.py:72-87`) adds four pages
  once at startup, each bound to a fixed sidebar index. There is no existing "detail page"
  pattern for a dynamically-selected record — this spec introduces one.
- **`dashboard_page.py:65` already assumes one `ACTIVE` plan per student**
  (`StudyPlan.status == PlanStatus.ACTIVE`). `PlanStatus` already defines `ARCHIVED`
  (`models.py:95-101`) for exactly this transition — this spec must preserve the invariant,
  not add a second active plan.
- **`AttendanceRecord` is unpopulated** (per `specs/analytics-area.md`) — Tab 1's attendance
  summary will show its empty state for real data today.
- **`CounselorNote.student_id` is a bare indexed `UUIDField`, not a `ForeignKeyField`** — it
  lives in the separate vault database, so it can't FK across databases. Filter by value, not
  by join.

---

## 1. Shell & integration

- New `src/views/pages/student_panel.py` — `StudentPanel(QWidget)`, one instance, reused across
  students (not recreated per open).
- `MainWindow` adds it to `self.pages` at a new index, but it is **not** a sidebar
  destination. `StudentsPage` gets a new method `open_student(student)`:
  ```python
  def _open_selected_student(self, index):
      student = index.data(Qt.UserRole)
      if student:
          self.student_opened.emit(student)   # new signal
  ```
  `MainWindow` connects `students_page.student_opened` to
  `lambda s: (self.student_panel.load(s), self._navigate_to(student_panel_index))`.
- **Back button:** a "← بازگشت" `SecondaryButton` in the panel header calls
  `self._navigate_to(students_index)`. `StudentsPage` already preserves its own `_page`/`_query`
  state across `reload()` calls, so returning to it needs no extra state-passing — its list is
  simply still there.
- **Lazy per-open load:** `load(student)` sets `self.student = student`, resets to tab 0
  (خلاصه و سوابق), and calls `self.reload()` — no `showEvent` lazy-load games needed since
  `load()` is the explicit entry point.
- Replaces `StudentDetailsDialog` and its call site entirely; `NewStudentDialog` and the
  students-list page are unaffected.

### Files

```
src/views/pages/
└── student_panel.py     # StudentPanel(QWidget), tabs: SummaryTab, PlanTab, NotesTab
tests/
└── test_student_panel.py   # plan-status invariant + manual session CRUD
```

Small enough (3 tabs, no charts) to keep as one file with three widget classes, rather than a
`student_panel/` package like `settings/`.

## 2. Header

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ← بازگشت   👤 پرونده تحصیلی: علی رضایی — پایه یازدهم تجربی (کد ملی: ...) │
├──────────────────────────────────────────────────────────────────────────┤
│  [ 📊 خلاصه و سوابق ]  [ 📅 برنامه مطالعاتی هفتگی ⭐ ]  [ 🔒 یادداشت‌ها ] │
```

- Title line: `student.full_name`, `f"پایه {ordinal} {major}"` (reuse `GRADE_ORDINALS`,
  `Classroom.compose_name()` logic), national ID via `to_persian_digits`.
- Tabs: same segmented-bar pattern as `SettingsPage` (`settings_page.py:105-134`) —
  `QButtonGroup` + `QStackedWidget`, no page-level dirty guard (see Non-goals).
- **Notes tab is hidden entirely** (not disabled — not added to the segmented bar) when
  `self.current_user.role != "counselor"`, matching `SecurityPanel`'s existing pattern
  (`security_panel.py:87`, `.setHidden(actor.role != "counselor")`).
- Default active tab: **برنامه مطالعاتی هفتگی** (starred in the mockup).

## 3. Tab 1 — خلاصه و سوابق (summary & history)

Read-only. Reload builds this from the student's row plus three queries:

- **Risk & scores:** `RiskBadge` (existing component, `ui_kit.py:126`) for `risk_level`, plus
  `burnout_score` / `disengagement_score` as labeled values.
- **GPA:** `student.calculate_gpa()` (`models.py:253-257`); show `—` when it returns `0.0` with
  no grade rows (don't claim a real zero).
- **Attendance summary:** count of `AttendanceRecord` rows for the student in the last N days;
  `EmptyState`-style inline message (not a dialog) when the table has no rows for this student,
  same tone as Analytics Panel 3's overlay (`specs/analytics-area.md` §Panel 3).
- **Plan history:** `StudyPlan.select().where(StudyPlan.student == student, StudyPlan.status !=
  PlanStatus.ACTIVE).order_by(StudyPlan.start_date.desc())` — a simple list/table: title, date
  range, `PlanStatus.PERSIAN_MAP[status]`. No click-through to view archived sessions in v1
  (`ponytail:` add a read-only session view per history row if a counselor asks for it).

## 4. Tab 2 — برنامه مطالعاتی هفتگی (weekly study plan)

### 4.1 Active-plan view

Query: `StudyPlan.get_or_none(StudyPlan.student == student, StudyPlan.status ==
PlanStatus.ACTIVE)`.

**When one exists:**

```
وضعیت فعلی: برنامه فعال (تأیید شده) | نرخ پایبندی: ۸۲٪ | ریسک: کم 🟢
[⚡ تولید مجدد]  [✏️ ویرایش دستی]  [🖨️ چاپ برنامه A4 PDF]   [🗄️ پایان برنامه]
┌────────────────────────────────────────────────────────────────────┐
│                  7-day grid: rows = sessions, columns = days        │
└────────────────────────────────────────────────────────────────────┘
```

- **Status line:** `PlanStatus.PERSIAN_MAP[plan.status]` + `"(تأیید شده)"` when
  `plan.is_approved` else `"(در انتظار تأیید)"`; adherence % from the **average of
  `DailyCheckIn.completion_rate`** for this student over the plan's date range (reuse the
  "recompute from stored columns" caution from the Analytics spec if check-ins ever get a
  richer shape — for v1, plain average is fine since this is a single-student, not cohort,
  metric); risk badge same as Tab 1.
- **"⚡ تولید مجدد" and "🖨️ چاپ برنامه A4 PDF":** rendered **disabled**, `setToolTip` explaining
  why (e.g. "موتور برنامه‌ریزی هوشمند هنوز فعال نشده است."). No click handler, no
  try/except-around-`NotImplementedError` — there's nothing to catch if the button can't be
  clicked.
- **"✏️ ویرایش دستی":** opens the grid in an editable mode (see §4.3) — inline, not a separate
  dialog, since the grid itself is the thing being edited.
- **"🗄️ پایان برنامه":** `SecondaryButton`, confirm dialog ("این برنامه آرشیو می‌شود و غیرفعال
  خواهد شد. ادامه می‌دهید؟"), then `plan.status = PlanStatus.ARCHIVED; plan.save()` and
  `reload()`. This is the only way to end an active plan in v1 — no auto-archive-on-create (see
  §4.2).
- **Grid:** 7 columns (شنبه…جمعه via `DayOfWeek.PERSIAN_NAMES`), one row per
  `plan.get_active_sessions()` sorted by `start_time`; cell shows `subject_name`,
  `start_time–end_time`, `session_type`. Read-only rendering in view mode.

### 4.2 Empty state — no active plan

```
هنوز برنامه مطالعاتی فعالی برای این دانش‌آموز ثبت نشده است.
[ + ساخت برنامه جدید ]
```

- If an `ACTIVE` plan **does** exist but the counselor tries to create another (shouldn't be
  reachable via this empty state, but guards the create flow itself): **block**, show
  "یک برنامه فعال از قبل وجود دارد؛ ابتدا آن را آرشیو کنید." and point at the "🗄️ پایان برنامه"
  control on the existing active plan's view. No silent auto-archive.
- "+ ساخت برنامه جدید" opens the manual-create flow: a small form (`FormField` × 2 for start/
  end date, reusing the digit-normalization helper pattern from `NewStudentDialog`) followed by
  an empty 7-day grid in **editable mode** (§4.3) to add sessions before saving.
- **On save:** `StudyPlan.create(student=student, start_date=..., end_date=...,
  status=PlanStatus.ACTIVE, is_approved=True, is_ai_generated=False)`, then bulk-create the
  edited `StudySession` rows against it. Immediately active+approved — no separate approval
  step for a counselor's own manual plan (the approval gate exists to vet AI output, which
  doesn't apply here).

### 4.3 Manual editing (create or edit-existing)

- Per-cell/per-row form to add a session: day (`QComboBox` over `DayOfWeek.PERSIAN_NAMES`),
  start time, end time (both `HH:MM`, validate `end > start`), subject (**free-text**
  `FormField`, per Non-goals — no picker), session_type (free-text or a small fixed combo of
  common values, e.g. `مطالعه` / `تمرین` / `مرور`, defaulting to `مطالعه` — cosmetic, not a
  modeled enum). `duration_minutes` is derived from start/end, not entered separately.
  Row-level delete (✕) button.
- Save writes/updates `StudySession` rows tied to the plan; Cancel discards in-memory edits and
  reverts the grid to the last-saved state. This Save/Cancel pair is the "self-contained editor"
  referenced in Non-goals — no page-level dirty check needed.
- No validation against overlapping sessions on the same day in v1 (`ponytail:` add an overlap
  check if counselors report double-booked cells; not requested).

## 5. Tab 3 — یادداشت‌های محرمانه (confidential notes)

Hidden entirely for non-counselor roles (§2). For a counselor:

### 5.1 Locked state

Reuses the exact unlock flow from `SecurityPanel` (`security_panel.py:79-112`):

```python
self.pin = FormField("پین گاوصندوق", password=True, revealable=True)
unlock = PrimaryButton("باز کردن گاوصندوق")
unlock.clicked.connect(self._unlock)
```
```python
def _unlock(self):
    try:
        get_database_manager().unlock_vault(DatabaseCredentials.from_vault_pin(self.pin.text()))
        self.unlocked = True
        self.reload_notes()
    except Exception as exc:
        self.pin.set_error(str(exc))
```

Shown inline in the tab, not a blocking modal — the rest of the page (other tabs) stays usable
while notes are locked.

### 5.2 Unlocked state

- **List:** `CounselorNote.select().where(CounselorNote.student_id ==
  student.id).order_by(CounselorNote.created_at.desc())` — filter by value since there's no FK
  (§Pre-existing conditions). Each row: title, tags, created date, content (or truncated with
  expand — content is already decrypted transparently by `EncryptedTextField.python_value`).
- **Create only:** a small form (title `FormField`, tags `FormField`, content multi-line) plus
  "افزودن یادداشت" button → `CounselorNote.create(student_id=student.id, title=..., content=...,
  tags=...)`, then prepend to the list. **No edit, no delete** — audit-trail semantics (§Non-
  goals).

## 6. Tests

`tests/test_student_panel.py`, following the fixture style in `tests/test_auth_and_login.py`:

1. **One-active-plan invariant** — create an `ACTIVE` plan, assert the create-new path is
   blocked while it's active; archive it; assert create-new now succeeds and exactly one
   `ACTIVE` plan exists for the student afterward.
2. **Manual session round-trip** — create a plan, add sessions via the editor's save path,
   reload, assert the grid reads back the same day/time/subject values.

No framework beyond the existing `pytest` setup.

## 7. Open decisions

None. Frontier fully explored.
