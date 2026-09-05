""" P_i = C_i * W_i
    R_i = P_i / sum(P)
    H_i = T_avail * R_i
    B_i = round(H_i / block_hours)
"""

from __future__ import annotations

from typing import Dict, Iterable, Sequence

from src.planner import catalog


def priority_weights(
    subjects: Sequence[str],
    coeffs: Dict[str, int],
    weaknesses: Dict[str, float],
) -> Dict[str, float]:
    return {
        s: max(coeffs.get(s, 0), 0) * max(weaknesses.get(s, 1.0), 0.0) for s in subjects
    }


def weekly_blocks(
    subjects: Sequence[str],
    coeffs: Dict[str, int],
    weaknesses: Dict[str, float],
    t_avail_hours: float,
    block_hours: float,
) -> Dict[str, int]:
    """Return {subject: whole block count}. May exceed the time budget only when
    H5 (every C_i>0 subject gets >=1 block) forces it -- caller then relaxes."""
    subjects = list(subjects)
    weights = priority_weights(subjects, coeffs, weaknesses)
    total_w = sum(weights.values())
    capacity = int(t_avail_hours // block_hours) if block_hours > 0 else 0

    blocks = {s: 0 for s in subjects}
    if total_w > 0 and capacity > 0:
        raw = {s: capacity * (weights[s] / total_w) for s in subjects}
        blocks = {s: int(v) for s, v in raw.items()}
        used = sum(blocks.values())
        by_remainder = sorted(
            subjects, key=lambda s: (raw[s] - blocks[s], weights[s], s), reverse=True
        )
        for s in by_remainder:
            if used >= capacity:
                break
            blocks[s] += 1
            used += 1

    for s in subjects:
        if coeffs.get(s, 0) > 0 and blocks[s] == 0:
            blocks[s] = 1

    used = sum(blocks.values())
    if used > capacity:
        by_priority = sorted(subjects, key=lambda s: (weights[s], s))
        idx = 0
        while used > capacity and idx < len(by_priority):
            s = by_priority[idx]
            if blocks[s] > 1:
                blocks[s] -= 1
                used -= 1
            else:
                idx += 1

    return blocks


def low_priority_subjects(
    subjects: Sequence[str], coeffs: Dict[str, int]
) -> "set[str]":
    values = sorted(coeffs.get(s, 0) for s in subjects)
    if not values:
        return set()
    median = values[len(values) // 2]
    return {
        s
        for s in subjects
        if coeffs.get(s, 0) <= median and catalog.archetype_for(s) != "calc"
    }


def block_requests(
    blocks: Dict[str, int],
    block_minutes: int,
    weaknesses: Dict[str, float],
    half_subjects: Iterable[str] = (),
) -> "list[dict]":
    half_subjects = set(half_subjects)
    requests = []
    for subject, count in blocks.items():
        if count <= 0:
            continue
        weak = weaknesses.get(subject, 1.0) >= catalog.S4_WEAKNESS_TRIGGER
        archetype = catalog.archetype_for(subject)
        if subject in half_subjects:
            requests.append(
                dict(
                    subject=subject,
                    minutes=catalog.HALF_BLOCK_MINUTES,
                    archetype=archetype,
                    weak=weak,
                )
            )
            continue
        for _ in range(count):
            requests.append(
                dict(
                    subject=subject,
                    minutes=block_minutes,
                    archetype=archetype,
                    weak=weak,
                )
            )
    requests.sort(key=lambda r: (r["weak"] is False, r["subject"]))
    return requests
