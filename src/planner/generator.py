from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from src.storage.models import Student, StudyPlan


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


@dataclass(frozen=True)
class PlanResult:
    plan: Optional[StudyPlan]
    warnings: Tuple[str, ...]
    errors: Tuple[str, ...]


def generate_plan(student: Student, params: PlanParams) -> PlanResult:
    raise NotImplementedError("Scheduling engine is not enabled yet")


def optimize_plan(plan: StudyPlan) -> PlanResult:
    raise NotImplementedError("Scheduling engine is not enabled yet")


def plan_to_pdf(plan: StudyPlan) -> bytes:
    raise NotImplementedError("PDF engine is not enabled yet")
