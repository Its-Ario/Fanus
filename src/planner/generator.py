from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from src.planner import budget, catalog, grid, solver, validate
from src.storage.models import (
    PlanStatus,
    SchoolProfile,
    Student,
    StudyPlan,
    StudySession,
    subject_options,
)


@dataclass(frozen=True)
class PlanParams:
    start_date: date
    end_date: date
    daily_hours: Tuple[float, float, float, float, float, float, float]
    earliest_start: str
    latest_end: str
    default_session_minutes: int
    max_sessions_per_day: int
    subjects: Tuple[Tuple[str, str], ...]
    keep_locked: bool
    grade_level: int = 10
    major: str = ""
    weakness_overrides: Tuple[Tuple[str, float], ...] = ()
    school_days: Tuple[int, ...] = catalog.DEFAULT_SCHOOL_DAYS
    school_hours: Tuple[str, str] = ("07:30", "13:30")
    sleep_window: Tuple[str, str] = catalog.DEFAULT_SLEEP_WINDOW
    block_minutes: int = catalog.DEFAULT_BLOCK_MINUTES
    weights: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanResult:
    plan: Optional[StudyPlan]
    warnings: Tuple[str, ...]
    errors: Tuple[str, ...]


@dataclass
class _Schedule:
    placements: List[dict]
    penalty: int
    notes: List[str]
    block_minutes: int
    unplaced: int = 0


def planner_weights() -> Dict[str, int]:
    weights = dict(catalog.DEFAULT_SOFT_WEIGHTS)
    try:
        from src.storage.models import PlannerSettings

        stored = PlannerSettings.get_instance().weights
        weights.update({k: int(v) for k, v in (stored or {}).items() if k in weights})
    except Exception:
        pass
    return weights


def planner_block_minutes() -> int:
    try:
        from src.storage.models import PlannerSettings

        return int(PlannerSettings.get_instance().block_minutes)
    except Exception:
        return catalog.DEFAULT_BLOCK_MINUTES


def _weakness_map(
    student: Student,
    subjects: Sequence[str],
    overrides: Sequence[Tuple[str, float]],
) -> Dict[str, float]:
    override = {name: float(w) for name, w in overrides}
    ratios: Dict[str, List[float]] = {}
    for row in student.grades:
        if not row.max_score:
            continue
        ratios.setdefault(catalog.subject_family(row.subject_name), []).append(
            row.score / row.max_score
        )
    out: Dict[str, float] = {}
    for subject in subjects:
        if subject in override:
            out[subject] = override[subject]
            continue
        values = ratios.get(catalog.subject_family(subject))
        if not values:
            out[subject] = 1.5
        else:
            avg = sum(values) / len(values)
            out[subject] = 1.0 if avg >= 0.85 else (1.5 if avg >= 0.6 else 2.0)
    return out


def _locked_spans(student: Student) -> Dict[int, List[Tuple[int, int]]]:
    active = StudyPlan.get_or_none(
        StudyPlan.student == student, StudyPlan.status == PlanStatus.ACTIVE
    )
    spans: Dict[int, List[Tuple[int, int]]] = {}
    if not active:
        return spans
    for session in active.sessions.where(StudySession.is_locked == True):  # noqa: E712
        spans.setdefault(session.day_of_week, []).append(
            (grid.to_minutes(session.start_time), grid.to_minutes(session.end_time))
        )
    return spans


def _prune_general(
    blocks: Dict[str, int], subjects: Sequence[str], coeffs: Dict[str, int]
) -> Dict[str, int]:
    values = sorted(coeffs.get(s, 0) for s in subjects)
    median = values[len(values) // 2] if values else 0
    for subject in subjects:
        if (
            catalog.archetype_for(subject) != "calc"
            and coeffs.get(subject, 0) <= median
            and blocks.get(subject, 0) > 1
        ):
            blocks[subject] = max(1, int(blocks[subject] * 0.8))
    return blocks


_RELAX_NOTE = {
    "half": "برای جا شدن همهٔ دروس، درس‌های کم‌ضریب به بلوک‌های ۴۵ دقیقه‌ای کوتاه شدند.",
    "compress": "طول بلوک‌ها به ۷۵ دقیقه کاهش یافت تا برنامه کامل شود.",
}


def _build_schedule(
    subjects: Sequence[str],
    coeffs: Dict[str, int],
    weaknesses: Dict[str, float],
    params: PlanParams,
    locked: Dict[int, List[Tuple[int, int]]],
) -> _Schedule:
    weights = planner_weights()
    weights.update({k: int(v) for k, v in (params.weights or {}).items() if k in weights})

    low = budget.low_priority_subjects(subjects, coeffs)
    base_bm = params.block_minutes

    attempts = [
        ("full", base_bm, set()),
        ("half", base_bm, low),
        ("compress", catalog.COMPRESSED_BLOCK_MINUTES, low),
    ]

    windows = grid.free_windows(
        params.school_days, params.school_hours, params.sleep_window, locked
    )

    best: Optional[_Schedule] = None
    for label, block_minutes, half in attempts:
        slots = grid.candidate_slots(
            windows, block_minutes, params.school_days, daily_hours=params.daily_hours
        )
        blocks = budget.weekly_blocks(subjects, coeffs, weaknesses, len(slots))
        if label == "compress":
            blocks = _prune_general(blocks, subjects, coeffs)

        requests = budget.block_requests(blocks, block_minutes, weaknesses, half)
        placements, penalty, unplaced = solver.solve(requests, slots, params.school_days, weights)

        notes = [] if label == "full" else [_RELAX_NOTE[label]]
        if not unplaced:
            return _Schedule(placements, penalty, notes, block_minutes)
        if best is None or len(unplaced) < best.unplaced:
            best = _Schedule(placements, penalty, notes, block_minutes, len(unplaced))

    deficit = best.unplaced * (best.block_minutes / 60.0)
    best.notes = [
        f"کمبود حدود {deficit:.1f} ساعت زمان جهت پوشش کامل ضرایب درسی. برنامهٔ ناقص تولید شد."
    ]
    return best


def _confidence(schedule: _Schedule) -> float:
    placed = len(schedule.placements)
    total = placed + schedule.unplaced
    coverage = placed / total if total else 1.0
    avg_penalty = schedule.penalty / max(placed, 1)
    return round(max(20.0, 100.0 * coverage - min(avg_penalty / 4.0, 35.0)), 1)


def _persist(
    student: Student,
    params: PlanParams,
    schedule: _Schedule,
    locked: Dict[int, List[Tuple[int, int]]],
) -> StudyPlan:
    plan = StudyPlan.create(
        student=student,
        start_date=params.start_date,
        end_date=params.end_date,
        status=PlanStatus.DRAFT,
        is_ai_generated=True,
        is_approved=False,
        confidence_score=_confidence(schedule),
    )

    rows = [
        dict(
            plan=plan,
            day_of_week=p["day"],
            start_time=grid.to_hhmm(p["start"]),
            end_time=grid.to_hhmm(p["end"]),
            subject_name=p["subject"],
            session_type="مطالعه",
            duration_minutes=p["minutes"],
            is_locked=False,
        )
        for p in schedule.placements
    ]

    rows.append(
        dict(
            plan=plan,
            day_of_week=catalog.DAY_FRIDAY,
            start_time=catalog.FRIDAY_MOCK_WINDOW[0],
            end_time=catalog.FRIDAY_MOCK_WINDOW[1],
            subject_name="آزمون جامع هفتگی",
            session_type="آزمون",
            duration_minutes=240,
            is_locked=True,
        )
    )
    rows.append(
        dict(
            plan=plan,
            day_of_week=catalog.DAY_FRIDAY,
            start_time=catalog.FRIDAY_BUFFER_WINDOW[0],
            end_time=catalog.FRIDAY_BUFFER_WINDOW[1],
            subject_name="مرور و جبرانی",
            session_type="مرور",
            duration_minutes=180,
            is_locked=False,
        )
    )

    if params.keep_locked:
        for day, spans in locked.items():
            for start, end in spans:
                rows.append(
                    dict(
                        plan=plan,
                        day_of_week=day,
                        start_time=grid.to_hhmm(start),
                        end_time=grid.to_hhmm(end),
                        subject_name="تعهد ثابت",
                        session_type="قفل‌شده",
                        duration_minutes=end - start,
                        is_locked=True,
                    )
                )

    StudySession.insert_many(rows).execute()
    return plan


def get_student_params(student: Student, *, keep_locked: bool = False) -> PlanParams:
    profile = SchoolProfile.get_instance()
    classroom = student.classroom
    grade = getattr(classroom, "grade_level", 11)
    major = student.major

    block_minutes = planner_block_minutes()
    today = date.today()

    subjects = tuple((name, "مطالعه") for name in subject_options(grade, major))

    return PlanParams(
        start_date=today,
        end_date=today + timedelta(days=6),
        daily_hours=tuple([float(student.daily_active_hours)] * 7),
        earliest_start=profile.school_hours[1],
        latest_end=catalog.DEFAULT_SLEEP_WINDOW[0],
        default_session_minutes=block_minutes,
        max_sessions_per_day=catalog.MAX_BLOCKS_OFF,
        subjects=subjects,
        keep_locked=keep_locked,
        grade_level=grade,
        major=major,
        school_days=catalog.DEFAULT_SCHOOL_DAYS,
        school_hours=tuple(profile.school_hours),
        block_minutes=block_minutes,
        weights=planner_weights(),
    )


def generate_plan(student: Student, params: PlanParams) -> PlanResult:
    subjects = list(
        dict.fromkeys(
            [sub[0] for sub in params.subjects]
            or list(subject_options(params.grade_level, params.major))
        )
    )
    major = student.major

    coeff = {s: catalog.coefficient_for(s, major) for s in subjects}
    weakness = _weakness_map(student, subjects, params.weakness_overrides)
    locked = _locked_spans(student) if params.keep_locked else {}
    schedule = _build_schedule(subjects, coeff, weakness, params, locked)

    violations = validate.check_hard(
        schedule.placements,
        school_days=params.school_days,
        school_hours=params.school_hours,
        required_subjects=[sub for sub in subjects if coeff[sub] > 0],
        sleep_window=params.sleep_window,
        blocked_spans=locked,
        max_block_minutes=params.block_minutes,
    )

    warnings = list(schedule.notes)
    if violations:
        warnings.append("هشدار: ", ";".join(violations))

    plan = _persist(student, params, schedule, locked)
    return PlanResult(plan=plan, warnings=tuple(warnings), errors=())


def optimize_plan(plan: StudyPlan) -> PlanResult:
    return generate_plan(plan.student, get_student_params(plan.student, keep_locked=True))
