from __future__ import annotations

from typing import Dict, List, NamedTuple, Sequence, Tuple

from src.planner import catalog

Span = Tuple[int, int]


class Slot(NamedTuple):
    index: int
    day: int
    start: int
    end: int
    label: str
    is_off_day: bool


def to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _subtract(base: Span, cuts: Sequence[Span]) -> List[Span]:
    free = [base]
    for cut_start, cut_end in cuts:
        nxt: List[Span] = []
        for start, end in free:
            if cut_end <= start or cut_start >= end:
                nxt.append((start, end))
                continue
            if cut_start > start:
                nxt.append((start, cut_start))
            if cut_end < end:
                nxt.append((cut_end, end))
        free = nxt
    return [span for span in free if span[1] > span[0]]


def free_windows(
    school_days: Sequence[int],
    school_hours: Tuple[str, str],
    sleep_window: Tuple[str, str] = catalog.DEFAULT_SLEEP_WINDOW,
    blocked_spans: Dict[int, Sequence[Span]] = None,
) -> Dict[int, List[Span]]:
    blocked_spans = blocked_spans or {}
    waking: Span = (to_minutes(sleep_window[1]), to_minutes(sleep_window[0]))
    meals = [(to_minutes(a), to_minutes(b)) for a, b in catalog.MEAL_WINDOWS]
    school = (to_minutes(school_hours[0]), to_minutes(school_hours[1]))

    windows: Dict[int, List[Span]] = {}
    for day in range(7):
        cuts = list(meals)
        if day in school_days:
            cuts.append(school)
        cuts.extend(tuple(span) for span in blocked_spans.get(day, ()))
        if day == catalog.DAY_FRIDAY:
            cuts.append(
                (
                    to_minutes(catalog.FRIDAY_MOCK_WINDOW[0]),
                    to_minutes(catalog.FRIDAY_MOCK_WINDOW[1]),
                )
            )
            cuts.append(
                (
                    to_minutes(catalog.FRIDAY_BUFFER_WINDOW[0]),
                    to_minutes(catalog.FRIDAY_BUFFER_WINDOW[1]),
                )
            )
        windows[day] = _subtract(waking, cuts)
    return windows


def candidate_slots(
    windows: Dict[int, List[Span]],
    block_minutes: int,
    school_days: Sequence[int],
    break_minutes: int = catalog.MIN_BREAK_MINUTES,
    daily_hours: Sequence[float] = None,
) -> List[Slot]:
    slots: List[Slot] = []
    index = 0
    for day in range(7):
        raw: List[Span] = []
        for start, end in sorted(windows.get(day, [])):
            cursor = start
            while cursor + block_minutes <= end:
                raw.append((cursor, cursor + block_minutes))
                cursor += block_minutes + break_minutes
        raw.sort()
        if daily_hours is not None:
            budget_min = float(daily_hours[day]) * 60.0
            cap = round(budget_min / block_minutes) if budget_min > 0 else 0
            if budget_min > 0:
                cap = max(cap, 1)
            raw = raw[:cap]
        for ordinal, (start, end) in enumerate(raw):
            label = catalog.ABSTRACT_SLOTS[min(ordinal, len(catalog.ABSTRACT_SLOTS) - 1)]
            slots.append(Slot(index, day, start, end, label, day not in school_days))
            index += 1
    return slots
