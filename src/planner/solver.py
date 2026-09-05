from __future__ import annotations

import time
from typing import Dict, List, Sequence, Tuple

from src.planner import catalog
from src.planner.grid import Slot

_TIME_BUDGET_S = 1.5


def _day_ceiling(day: int, school_days: Sequence[int]) -> int:
    if day == catalog.DAY_THURSDAY:
        return catalog.MAX_BLOCKS_THURSDAY
    if day in school_days:
        return catalog.MAX_BLOCKS_SCHOOL
    return catalog.MAX_BLOCKS_OFF


def _adjacent(a: Slot, b: Slot) -> bool:
    if a.day != b.day:
        return False
    lo, hi = (a, b) if a.start <= b.start else (b, a)
    return hi.start - lo.end <= catalog.MIN_BREAK_MINUTES


def _feasible(req: dict, slot: Slot, assigned: Dict[int, dict], slots_by_day) -> bool:
    if slot.index in assigned:
        return False
    if req["minutes"] > slot.end - slot.start:
        return False
    same_day = [s for s in slots_by_day.get(slot.day, ()) if s.index in assigned]
    if len(same_day) >= _day_ceiling(slot.day, req["_school_days"]):
        return False
    for other in same_day:
        if _adjacent(slot, other) and assigned[other.index]["subject"] == req["subject"]:
            return False
    return True


def _pair_gap_hours(day_a, start_a, day_b, start_b) -> float:
    return abs((day_a * 24 * 60 + start_a) - (day_b * 24 * 60 + start_b)) / 60.0


def score(assigned: Dict[int, dict], slots: Sequence[Slot], weights: Dict[str, int]) -> int:
    slot_by_index = {s.index: s for s in slots}
    placed = [(slot_by_index[i], req) for i, req in assigned.items()]
    total = 0

    by_day: Dict[int, list] = {}
    for slot, req in placed:
        by_day.setdefault(slot.day, []).append((slot, req))

    for slot, req in placed:
        if slot.label not in catalog.PREFERRED_SLOTS.get(req["archetype"], ()):
            total += weights["s1"]

    for day, items in by_day.items():
        items.sort(key=lambda sr: sr[0].start)
        for (sa, ra), (sb, rb) in zip(items, items[1:]):
            if _adjacent(sa, sb) and ra["archetype"] == rb["archetype"]:
                total += weights["s2"]
        is_off = items[0][0].is_off_day
        lo, hi = catalog.DISTINCT_BAND_OFF if is_off else catalog.DISTINCT_BAND_SCHOOL
        distinct = len({r["subject"] for _, r in items})
        if distinct < lo or distinct > hi:
            total += weights["s3"]

    weak_positions: Dict[str, list] = {}
    for slot, req in placed:
        if req["weak"]:
            weak_positions.setdefault(req["subject"], []).append((slot.day, slot.start))
    for positions in weak_positions.values():
        if len(positions) < 2:
            continue
        positions.sort()
        for (da, sa), (db, sb) in zip(positions, positions[1:]):
            gap = _pair_gap_hours(da, sa, db, sb)
            if gap < catalog.S4_MIN_GAP_HOURS or gap > catalog.S4_MAX_GAP_HOURS:
                total += weights["s4"]

    return total


def solve(
    requests: Sequence[dict],
    slots: Sequence[Slot],
    school_days: Sequence[int],
    weights: Dict[str, int],
) -> Tuple[List[dict], int, List[dict]]:
    deadline = time.monotonic() + _TIME_BUDGET_S
    slots = list(slots)
    slots_by_day: Dict[int, list] = {}
    for s in slots:
        slots_by_day.setdefault(s.day, []).append(s)

    for r in requests:
        r["_school_days"] = tuple(school_days)

    assigned: Dict[int, dict] = {}
    unplaced: List[dict] = []

    # greedy fill
    for req in requests:
        best = None
        for slot in slots:
            if not _feasible(req, slot, assigned, slots_by_day):
                continue
            trial = dict(assigned)
            trial[slot.index] = req
            key = (score(trial, slots, weights), slot.day, slot.start)
            if best is None or key < best[0]:
                best = (key, slot.index)
        if best is None:
            unplaced.append(req)
        else:
            assigned[best[1]] = req

    improved = True
    while improved and time.monotonic() < deadline:
        improved = False
        current = score(assigned, slots, weights)
        for slot_index in list(assigned):
            req = assigned[slot_index]
            for slot in slots:
                if slot.index == slot_index or slot.index in assigned:
                    continue
                moved = {i: r for i, r in assigned.items() if i != slot_index}
                if not _feasible(req, slot, moved, slots_by_day):
                    continue
                moved[slot.index] = req
                if score(moved, slots, weights) < current:
                    assigned = moved
                    improved = True
                    break
            if improved:
                break

    slot_by_index = {s.index: s for s in slots}
    placements = []
    for i, req in sorted(assigned.items(), key=lambda kv: (slot_by_index[kv[0]].day, slot_by_index[kv[0]].start)):
        slot = slot_by_index[i]
        placements.append(
            dict(
                day=slot.day,
                start=slot.start,
                end=slot.start + req["minutes"],
                subject=req["subject"],
                minutes=req["minutes"],
                archetype=req["archetype"],
            )
        )
    return placements, score(assigned, slots, weights), unplaced
