# Graph Report - Fanus  (2026-09-22)

## Corpus Check
- 86 files · ~74,091 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1104 nodes · 3600 edges · 45 communities (42 shown, 3 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 698 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c0de6ae4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Colors
- models.py
- FirstRunWizard
- GradeEntryPage
- .__init__
- ConfigManager
- set_vault_cipher_key
- db.py
- DatabaseManager
- .from_vault_pin
- generator.py
- student_panel.py
- WindowsDpapiAnchor
- Build Windows Executable job (PyInstaller onefile)
- to_persian_digits
- Fanus Logo
- StudentsPage
- AttendancePage
- Fanus Exam Model & Grade Entry UI — Design
- backup_ops.py
- fanus
- settings_ops.py
- Spec — Settings Area (Administrative & Structural Setup)
- Spec — Analytics Page (آمار — School Overview)
- Spec — `.fanusbak` Full Backup & Restore
- settings_page.py
- _ScoreGrid
- backup_panel.py
- Spec — Student Panel (پرونده تحصیلی — Per-Student Record)
- Fanus Grade System — Design
- DataTable
- PrimaryButton
- ClassesPanel
- test_grades.py
- FormField
- Student Import / Export — Design
- _AuditModel
- Daily Attendance — Design
- 003_reshape_academicgrade.py
- 001_add_audit_note_metadata.py
- 004_attendance_record.py

## God Nodes (most connected - your core abstractions)
1. `Colors` - 80 edges
2. `PrimaryButton` - 80 edges
3. `Student` - 74 edges
4. `SecondaryButton` - 71 edges
5. `FormField` - 65 edges
6. `Exam` - 60 edges
7. `DatabaseManager` - 58 edges
8. `Dropdown` - 58 edges
9. `to_persian_digits()` - 56 edges
10. `Classroom` - 53 edges

## Surprising Connections (you probably didn't know these)
- `FakeUser` --uses--> `DatabaseConfigurationError`  [INFERRED]
  tests/test_auth_and_login.py → src/storage/db.py
- `FakeUser` --uses--> `DatabaseManager`  [INFERRED]
  tests/test_auth_and_login.py → src/storage/db.py
- `FakeUser` --uses--> `User`  [INFERRED]
  tests/test_auth_and_login.py → src/storage/models.py
- `FakeUser` --uses--> `Classroom`  [INFERRED]
  tests/test_auth_and_login.py → src/storage/models.py
- `FakeUser` --uses--> `Student`  [INFERRED]
  tests/test_auth_and_login.py → src/storage/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Dual-database migration regime linked by student_id UUID** — src_storage_migrations_fanus_readme_migration_policy, src_storage_migrations_vault_readme_migration_policy, src_storage_migrations_vault_readme_cross_db_student_id [EXTRACTED 0.75]

## Communities (45 total, 3 thin omitted)

### Community 0 - "Colors"
Cohesion: 0.05
Nodes (55): BarGroup, QComboBox, QTableView, QValidator, AcademicMajor, Classroom, GradeValidationError, Student (+47 more)

### Community 1 - "models.py"
Cohesion: 0.05
Nodes (67): Model, QToolButton, encrypt_vault_value(), create_grade(), list_grades(), _number(), SaveResult, save_grades_bulk() (+59 more)

### Community 2 - "FirstRunWizard"
Cohesion: 0.08
Nodes (8): QFrame, TitleBar, FirstRunWizard, QDialog, AccountChoice, LoginDialog, QDialog, QFrame

### Community 3 - "GradeEntryPage"
Cohesion: 0.15
Nodes (5): QMainWindow, MainWindow, GradeEntryPage, _labelled(), QWidget

### Community 4 - ".__init__"
Cohesion: 0.07
Nodes (17): QIcon, NavItem, QFrame, QPushButton, Sidebar, UserFooter, _ActionPopup, AIInsightCard (+9 more)

### Community 5 - "ConfigManager"
Cohesion: 0.36
Nodes (4): Any, AppConfig, ConfigManager, Path

### Community 6 - "set_vault_cipher_key"
Cohesion: 0.21
Nodes (6): SqliteDatabase, DatabaseConnectionError, _derive_subkey(), set_vault_cipher_key(), in_memory_db(), fixture

### Community 7 - "db.py"
Cohesion: 0.21
Nodes (12): _app_asset_path(), main(), Path, _set_windows_app_identity(), setup_logging(), heal_interrupted_restore(), configure_database_manager(), DatabaseCredentials (+4 more)

### Community 8 - "DatabaseManager"
Cohesion: 0.15
Nodes (11): DatabaseConfigurationError, DatabaseError, DatabaseManager, DatabaseMigrationError, RuntimeError, load_students_page(), test_load_students_page_filters_by_major_and_classroom_and_sorts_columns(), test_major_selection_narrows_the_class_filter() (+3 more)

### Community 9 - ".from_vault_pin"
Cohesion: 0.18
Nodes (12): decrypt_vault_value(), _default_vault_anchor_path(), _derive_key(), _load_or_create_salts(), Path, env(), fixture, test_different_vault_pin_derives_a_different_key() (+4 more)

### Community 10 - "generator.py"
Cohesion: 0.09
Nodes (52): NamedTuple, setter, block_requests(), low_priority_subjects(), priority_weights(), weekly_blocks(), coefficient_for(), subject_family() (+44 more)

### Community 11 - "student_panel.py"
Cohesion: 0.08
Nodes (27): QTableWidget, CounselorNote, _actor(), create_note(), list_note_audit(), list_notes(), NotePermissionError, NoteValidationError (+19 more)

### Community 13 - "Build Windows Executable job (PyInstaller onefile)"
Cohesion: 0.32
Nodes (8): Build Windows Executable job (PyInstaller onefile), CI Build Pipeline (GitHub Actions), Lint & Test job (Ruff + pytest, Python 3.8, uv), Fanus - offline-first study manager & planner for old hardware, App runtime dependencies (PyQt5, PyInstaller), Fanus DB migration policy (numbered peewee-migrate, restore-path test), Cross-database student_id UUID relationship (vault <-> fanus.db), Counselor vault migration policy (peewee-migrate, preserve cross-db student_id UUID)

### Community 14 - "to_persian_digits"
Cohesion: 0.10
Nodes (39): QFont, QPrinter, QRectF, attendance_summary(), AttendanceSummary, _ensure_font(), export_academic_summary_pdf(), export_weekly_plan_pdf() (+31 more)

### Community 15 - "Fanus Logo"
Cohesion: 0.47
Nodes (6): Navy and Amber Brand Palette, Circuit Board Traces and Nodes, Fanus Logo, Fanus Project, Glowing Four-Pointed Star / Sparkle, Circuit-Style Lantern Motif

### Community 16 - "StudentsPage"
Cohesion: 0.11
Nodes (11): ImportResult, ImportRow, bulk_create_students(), Path, read_roster(), _rows_from_csv(), _rows_from_xlsx(), _valid_national_id() (+3 more)

### Community 17 - "AttendancePage"
Cohesion: 0.14
Nodes (16): list_attendance(), _date, SaveResult, save_attendance_bulk(), AttendancePage, _labelled(), QWidget, _class() (+8 more)

### Community 18 - "Fanus Exam Model & Grade Entry UI — Design"
Cohesion: 0.07
Nodes (28): 10. Files touched, 11. `ponytail:` markers to leave in code, 1.1 `Exam` — new (`src/storage/models.py`), 1.2 `ExamClassroom` — new link table, 1.3 `AcademicGrade` — reshaped (`src/storage/models.py`), 1.4 `PUBLIC_MODELS`, 1. Data model, 2. Migration `006_exam_model.py` (`src/storage/migrations/fanus/`) (+20 more)

### Community 19 - "backup_ops.py"
Cohesion: 0.13
Nodes (41): _apply_restore(), BackupError, BackupInfo, _build_manifest(), _close_databases(), create_backup(), _derive(), _info() (+33 more)

### Community 22 - "settings_ops.py"
Cohesion: 0.16
Nodes (21): hash_password(), verify_password(), record_audit(), _active_actor(), _actor(), change_own_password(), delete_classroom(), PermissionError (+13 more)

### Community 25 - "Spec — Settings Area (Administrative & Structural Setup)"
Cohesion: 0.07
Nodes (26): 10. Codex review — disposition, 1. Shell & integration, 2. Access & authorization, 3. Save semantics, 4. Audit, 5. Tab 1 — عمومی و اطلاعات مدرسه, 6.1 Schema change — model layer **and** one migration file, 6.2 Classes list (+18 more)

### Community 26 - "Spec — Analytics Page (آمار — School Overview)"
Cohesion: 0.09
Nodes (22): 1. Shell & integration, 2. Data layer, 3. Layout, 4. Filter bar, 5. Chart widgets, 6. Panels, 7. Performance targets (dual-core Win7 / 2 GB), 8. Tests (+14 more)

### Community 27 - "Spec — `.fanusbak` Full Backup & Restore"
Cohesion: 0.09
Nodes (22): 10. Test plan — `tests/test_backup.py`, 1.1 `manifest.json`, 1. File format, 2. Module & API — new `src/storage/backup_ops.py`, 3. Create flow (`create_backup`), 4. Restore flow (`restore_backup`), 5.1 The marker, 5.2 `db.py` change — the only edit to existing storage code (+14 more)

### Community 28 - "settings_page.py"
Cohesion: 0.15
Nodes (9): parse_levels(), PlannerPanel, QWidget, QWidget, SchoolPanel, QDialog, QWidget, SettingsPage (+1 more)

### Community 29 - "_ScoreGrid"
Cohesion: 0.18
Nodes (3): to_ascii_digits(), ExamGridView, _ScoreGrid

### Community 30 - "backup_panel.py"
Cohesion: 0.17
Nodes (8): validate_academic_year(), BackupPanel, _heading(), _muted(), QDialog, QLabel, QWidget, RolloverConfirmDialog

### Community 31 - "Spec — Student Panel (پرونده تحصیلی — Per-Student Record)"
Cohesion: 0.11
Nodes (18): 1. Shell & integration, 2. Header, 3. Tab 1 — خلاصه و سوابق (summary & history), 4.1 Active-plan view, 4.2 Empty state — no active plan, 4.3 Manual editing (create or edit-existing), 4. Tab 2 — برنامه مطالعاتی هفتگی (weekly study plan), 5.1 Locked state (+10 more)

### Community 32 - "Fanus Grade System — Design"
Cohesion: 0.11
Nodes (17): 10. Seed — `src/storage/seed.py`, 11. Tests, 12. `ponytail:` markers to leave in code, 13. Not in scope, 1. Purpose & scope, 2. Data model — `AcademicGrade` (`src/storage/models.py:513`), 3. Term taxonomy, 4. معدل (GPA) — `Student.calculate_gpa()` (`src/storage/models.py:495`) (+9 more)

### Community 33 - "DataTable"
Cohesion: 0.22
Nodes (6): DataTable, UserDialog, QAbstractTableModel, QWidget, _UsersModel, UsersPanel

### Community 34 - "PrimaryButton"
Cohesion: 0.33
Nodes (8): SchoolProfile, PrimaryButton, SecondaryButton, ClassDialog, _Dialog, PasswordChangeDialog, QDialog, VaultPinDialog

### Community 35 - "ClassesPanel"
Cohesion: 0.20
Nodes (4): _ClassesModel, ClassesPanel, QAbstractTableModel, QWidget

### Community 36 - "test_grades.py"
Cohesion: 0.39
Nodes (14): _weakness_map(), _round2(), _add_peers(), _exam(), _student(), test_exam_validation(), test_gpa_empty_when_no_moadel_grades(), test_gpa_uses_latest_highest_term_and_weights() (+6 more)

### Community 38 - "Student Import / Export — Design"
Cohesion: 0.14
Nodes (13): 1. Scope, 2. Template / file format, 3. `src/storage/student_ops.py` — UI-free module, 4. UI — `src/views/pages/students_page.py`, 5. Wiring, audit, deps, 6. Tests — `tests/test_student_import.py`, 7. File touch list, commit — `bulk_create_students(rows, *, commit=True, actor=None) -> ImportResult` (+5 more)

### Community 39 - "_AuditModel"
Cohesion: 0.23
Nodes (4): _AuditModel, QAbstractTableModel, QWidget, SecurityPanel

### Community 40 - "Daily Attendance — Design"
Cohesion: 0.25
Nodes (7): Daily Attendance — Design, Data, Not in scope, `src/storage/attendance_ops.py` (UI-free, mirrors `grade_ops`), `src/views/pages/attendance_page.py` — `AttendancePage(QWidget)`, Tests — `tests/test_attendance.py` (asserts + `qtbot`, no framework), Wiring

### Community 41 - "003_reshape_academicgrade.py"
Cohesion: 0.60
Nodes (3): _columns(), migrate(), _tables()

### Community 42 - "001_add_audit_note_metadata.py"
Cohesion: 0.83
Nodes (3): migrate(), rollback(), _tables()

### Community 43 - "004_attendance_record.py"
Cohesion: 0.83
Nodes (3): migrate(), rollback(), _tables()

## Knowledge Gaps
- **130 isolated node(s):** `fanus`, `Context`, `Goals`, `Non-goals (deferred, not this build)`, `Pre-existing conditions this spec must work around` (+125 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Colors` connect `Colors` to `DataTable`, `FirstRunWizard`, `models.py`, `.__init__`, `FormField`, `PrimaryButton`, `db.py`, `GradeEntryPage`, `student_panel.py`, `StudentsPage`, `AttendancePage`, `settings_page.py`, `_ScoreGrid`, `backup_panel.py`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `Student` connect `Colors` to `models.py`, `PrimaryButton`, `GradeEntryPage`, `test_grades.py`, `ClassesPanel`, `DataTable`, `DatabaseManager`, `generator.py`, `StudentsPage`, `AttendancePage`, `backup_ops.py`, `settings_ops.py`, `settings_page.py`, `_ScoreGrid`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `to_persian_digits()` connect `to_persian_digits` to `Colors`, `models.py`, `PrimaryButton`, `GradeEntryPage`, `.__init__`, `FormField`, `student_panel.py`, `StudentsPage`, `AttendancePage`, `backup_ops.py`, `settings_ops.py`, `_ScoreGrid`, `backup_panel.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 60 inferred relationships involving `Colors` (e.g. with `BarChartWidget` and `LineChartWidget`) actually correct?**
  _`Colors` has 60 INFERRED edges - model-reasoned connections that need verification._
- **Are the 41 inferred relationships involving `PrimaryButton` (e.g. with `Colors` and `AttendancePage`) actually correct?**
  _`PrimaryButton` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `Student` (e.g. with `PlanParams` and `PlanResult`) actually correct?**
  _`Student` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `SecondaryButton` (e.g. with `Colors` and `AttendancePage`) actually correct?**
  _`SecondaryButton` has 37 INFERRED edges - model-reasoned connections that need verification._