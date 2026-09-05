from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from src.planner import catalog
from src.planner.grid import Span, to_minutes


def _day_ceiling(day: int, school_days: Sequence[int]) -> int:
    if day == catalog.DAY_THURSDAY:
        return catalog.MAX_BLOCKS_THURSDAY
    if day in school_days:
        return catalog.MAX_BLOCKS_SCHOOL
    return catalog.MAX_BLOCKS_OFF


def check_hard(
    placements: Sequence[dict],
    *,
    school_days: Sequence[int],
    school_hours: Tuple[str, str],
    required_subjects: Sequence[str],
    sleep_window=catalog.DEFAULT_SLEEP_WINDOW,
    blocked_spans: Dict[int, Sequence[Span]] = None,
    max_block_minutes: int = catalog.DEFAULT_BLOCK_MINUTES,
) -> List[str]:
    blocked_spans = blocked_spans or {}
    errors: List[str] = []

    wake_start = to_minutes(sleep_window[1])
    wake_end = to_minutes(sleep_window[0])
    school = (to_minutes(school_hours[0]), to_minutes(school_hours[1]))
    meals = [(to_minutes(a), to_minutes(b)) for a, b in catalog.MEAL_WINDOWS]

    by_day: Dict[int, List[dict]] = {}
    for p in placements:
        by_day.setdefault(p["day"], []).append(p)

    def overlaps(a_start, a_end, b_start, b_end) -> bool:
        return a_start < b_end and b_start < a_end

    for day, items in by_day.items():
        items = sorted(items, key=lambda p: p["start"])

        ceiling = _day_ceiling(day, school_days)
        if len(items) > ceiling:
            errors.append(f"H3: روز {day} دارای {len(items)} بلوک است (سقف مجاز {ceiling}).")

        for i, p in enumerate(items):
            start, end = p["start"], p["end"]

            if end - start > max_block_minutes:
                errors.append(
                    f"H4: بلوک روز {day} ساعت {p.get('subject', '')} بیش از حد پیوسته است."
                )

            if start < wake_start or end > wake_end:
                errors.append(f"H2: بلوک روز {day} داخل بازه خواب قرار دارد.")
            if day in school_days and overlaps(start, end, *school):
                errors.append(f"H2: بلوک روز {day} با ساعات مدرسه هم پوشانی دارد.")
            if any(overlaps(start, end, *meal) for meal in meals):
                errors.append(f"H2: بلوک روز {day} با وعده غذایی هم پوشانی دارد.")
            if any(overlaps(start, end, bs, be) for bs, be in blocked_spans.get(day, ())):
                errors.append(f"H2: بلوک روز {day} با یک تعهد ثابت هم پوشانی دارد.")

            if i + 1 < len(items):
                nxt = items[i + 1]
                if nxt["start"] < end:
                    errors.append(f"H1: دو بلوک روز {day} هم پوشانی دارند.")
                elif nxt["start"] - end < catalog.MIN_BREAK_MINUTES:
                    errors.append(
                        f"H4: فاصله استراحت بین دو بلوک روز {day} کمتر از "
                        f"{catalog.MIN_BREAK_MINUTES} دقیقه است."
                    )

    placed = {p.get("subject") for p in placements}
    missing = [s for s in required_subjects if s not in placed]
    if missing:
        errors.append("H5: درس های بدون سهمیه: " + "، ".join(sorted(missing)))

    return errors
