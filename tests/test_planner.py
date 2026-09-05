from src.planner import budget, catalog, grid, solver, validate
from src.planner.generator import generate_plan, params_for_student
from src.storage.db import DatabaseManager
from src.storage.models import (
    AcademicGrade,
    AcademicMajor,
    Classroom,
    PlanStatus,
    SchoolProfile,
    Student,
    StudySession,
)

SCHOOL_DAYS = catalog.DEFAULT_SCHOOL_DAYS
SCHOOL_HOURS = ("07:30", "13:30")


# --- pure units --------------------------------------------------------------


def test_budget_fits_capacity_and_never_starves_a_graded_subject():
    subjects = ["ریاضی", "فیزیک", "شیمی", "زیست‌شناسی", "عربی", "دین و زندگی"]
    coeffs = {s: catalog.coefficient_for(s, AcademicMajor.EXPERIMENTAL) for s in subjects}
    weaknesses = {s: 1.5 for s in subjects}
    weaknesses["ریاضی"] = 2.0
    capacity = 23
    n_required = sum(1 for s in subjects if coeffs[s] > 0)

    blocks = budget.weekly_blocks(subjects, coeffs, weaknesses, capacity)

    assert sum(blocks.values()) <= max(capacity, n_required)
    assert all(blocks[s] >= 1 for s in subjects)  # H5
    assert blocks["ریاضی"] >= blocks["عربی"]  # priority ordering holds


def test_budget_never_exceeds_grid_capacity():
    subjects = ["ریاضی", "فیزیک", "شیمی", "زیست‌شناسی", "عربی", "دین و زندگی", "انگلیسی"]
    coeffs = {s: catalog.coefficient_for(s, AcademicMajor.EXPERIMENTAL) for s in subjects}
    weaknesses = {s: 1.5 for s in subjects}
    windows = grid.free_windows(SCHOOL_DAYS, SCHOOL_HOURS)
    slots = grid.candidate_slots(windows, 90, SCHOOL_DAYS, daily_hours=[5.0] * 7)
    n_required = sum(1 for s in subjects if coeffs[s] > 0)

    blocks = budget.weekly_blocks(subjects, coeffs, weaknesses, len(slots))

    assert sum(blocks.values()) <= max(len(slots), n_required)


def test_grid_removes_sleep_school_and_meal_windows():
    windows = grid.free_windows(SCHOOL_DAYS, SCHOOL_HOURS)
    school_start, school_end = 7 * 60 + 30, 13 * 60 + 30
    lunch = (13 * 60 + 30, 14 * 60 + 30)

    for start, end in windows[0]:  # Saturday = school day
        assert not (start < school_end and school_start < end)
        assert not (start < lunch[1] and lunch[0] < end)
        assert start >= 6 * 60 + 30 and end <= 23 * 60 + 30


def test_solver_output_passes_the_hard_constraint_checker():
    subjects = ["ریاضی", "فیزیک", "فارسی و نگارش", "عربی", "دین و زندگی"]
    coeffs = {s: catalog.coefficient_for(s, AcademicMajor.MATH) for s in subjects}
    weaknesses = {s: 1.5 for s in subjects}
    blocks = budget.weekly_blocks(subjects, coeffs, weaknesses, 20)
    requests = budget.block_requests(blocks, 90, weaknesses)

    windows = grid.free_windows(SCHOOL_DAYS, SCHOOL_HOURS)
    slots = grid.candidate_slots(windows, 90, SCHOOL_DAYS)
    placements, _, unplaced = solver.solve(
        requests, slots, SCHOOL_DAYS, catalog.DEFAULT_SOFT_WEIGHTS
    )

    assert not unplaced
    errors = validate.check_hard(
        placements,
        school_days=SCHOOL_DAYS,
        school_hours=SCHOOL_HOURS,
        required_subjects=subjects,
    )
    assert errors == []


def test_solver_is_deterministic():
    subjects = ["ریاضی", "فیزیک", "فارسی و نگارش", "عربی"]
    coeffs = {s: catalog.coefficient_for(s, AcademicMajor.MATH) for s in subjects}
    weaknesses = {s: 1.5 for s in subjects}
    blocks = budget.weekly_blocks(subjects, coeffs, weaknesses, 16)
    windows = grid.free_windows(SCHOOL_DAYS, SCHOOL_HOURS)
    slots = grid.candidate_slots(windows, 90, SCHOOL_DAYS)

    runs = [
        solver.solve(
            budget.block_requests(blocks, 90, weaknesses),
            slots,
            SCHOOL_DAYS,
            catalog.DEFAULT_SOFT_WEIGHTS,
        )[0]
        for _ in range(3)
    ]
    assert runs[0] == runs[1] == runs[2]


def test_improvement_sweep_never_worsens_greedy(monkeypatch):
    """Filling every slot exactly disables the relocate-to-empty move, so any
    penalty drop here comes from the pairwise swap. It must never regress."""
    subjects = ["ریاضی", "فیزیک", "شیمی", "زیست‌شناسی", "فارسی و نگارش", "عربی", "دین و زندگی"]
    coeffs = {s: catalog.coefficient_for(s, AcademicMajor.EXPERIMENTAL) for s in subjects}
    weaknesses = {s: 2.0 for s in subjects}  # all weak -> dense s4 interplay
    windows = grid.free_windows(SCHOOL_DAYS, SCHOOL_HOURS)
    slots = grid.candidate_slots(windows, 90, SCHOOL_DAYS, daily_hours=[5.0] * 7)
    blocks = budget.weekly_blocks(subjects, coeffs, weaknesses, len(slots))

    def make_requests():
        return budget.block_requests(blocks, 90, weaknesses)

    _, swept_penalty, _ = solver.solve(
        make_requests(), slots, SCHOOL_DAYS, catalog.DEFAULT_SOFT_WEIGHTS
    )

    monkeypatch.setattr(solver, "_TIME_BUDGET_S", -1.0)  # skip the improvement sweep
    _, greedy_penalty, _ = solver.solve(
        make_requests(), slots, SCHOOL_DAYS, catalog.DEFAULT_SOFT_WEIGHTS
    )

    assert swept_penalty <= greedy_penalty


# --- end to end (real DB) --------------------------------------------------


def _seed(tmp_path, *, daily_hours=5.0):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    manager.initialize_public()
    SchoolProfile.create(id=1, school_name="دبیرستان نمونه", academic_year="1404-1405", type="high")
    classroom = Classroom.create(
        name="یازدهم تجربی", grade_level=11, major=AcademicMajor.EXPERIMENTAL
    )
    student = Student.create(
        national_id="2000000001",
        first_name="نگار",
        last_name="کاظمی",
        classroom=classroom,
        major=AcademicMajor.EXPERIMENTAL,
        daily_active_hours=daily_hours,
    )
    for subject, score in (("زیست‌شناسی ۲", 9.0), ("شیمی ۲", 11.0), ("ریاضی ۲", 8.0)):
        AcademicGrade.create(student=student, subject_name=subject, score=score, max_score=20.0)
    return manager, student


def test_generate_plan_end_to_end_is_valid(tmp_path):
    manager, student = _seed(tmp_path)
    try:
        result = generate_plan(student, params_for_student(student))
        plan = result.plan

        assert plan is not None and plan.status == PlanStatus.DRAFT
        assert plan.is_ai_generated and not plan.is_approved

        study = [
            dict(
                day=s.day_of_week,
                start=grid.to_minutes(s.start_time),
                end=grid.to_minutes(s.end_time),
                subject=s.subject_name,
            )
            for s in plan.sessions.where(StudySession.session_type == "مطالعه")
        ]
        assert study, "expected study sessions"
        errors = validate.check_hard(
            study,
            school_days=catalog.DEFAULT_SCHOOL_DAYS,
            school_hours=tuple(SchoolProfile.get_instance().school_hours),
            required_subjects=[p["subject"] for p in study],
        )
        assert errors == []

        # S5 fixtures present
        types = {s.session_type for s in plan.sessions}
        assert "آزمون" in types and "مرور" in types
    finally:
        manager.close()


def test_generate_plan_generous_time_has_no_deficit(tmp_path):
    manager, student = _seed(tmp_path, daily_hours=7.0)
    try:
        result = generate_plan(student, params_for_student(student))
        assert result.plan is not None
        assert not any("کمبود" in w for w in result.warnings)
        study_subjects = {
            s.subject_name
            for s in result.plan.sessions.where(StudySession.session_type == "مطالعه")
        }
        assert len(study_subjects) >= 5
    finally:
        manager.close()


def test_generate_plan_low_time_emits_deficit_warning(tmp_path):
    manager, student = _seed(tmp_path, daily_hours=1.0)
    try:
        result = generate_plan(student, params_for_student(student))
        assert result.plan is not None
        assert any("کمبود" in w for w in result.warnings)
    finally:
        manager.close()
