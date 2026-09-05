from __future__ import annotations

from typing import Dict, Iterable, Sequence

from src.planner import catalog


def priority_weights(
    subjects: Sequence[str],
    coeffs: Dict[str, int],
    weaknesses: Dict[str, float],
) -> Dict[str, float]:
    return {s: max(coeffs.get(s, 0), 0) * max(weaknesses.get(s, 1.0), 0.0) for s in subjects}


def weekly_blocks(
    subjects: Sequence[str],
    coeffs: Dict[str, int],
    weaknesses: Dict[str, float],
    capacity: int,
) -> Dict[str, int]:
    subjects = list(subjects)
    weights = priority_weights(subjects, coeffs, weaknesses)
    total_w = sum(weights.values())
    capacity = max(int(capacity), 0)

    blocks = {sub: 0 for sub in subjects}
    # larget remainder
    if total_w > 0 and capacity > 0:
        raw = {s: capacity * (weights[s] / total_w) for s in subjects}
        blocks = {s: int(v) for s, v in raw.items()}
        used = sum(blocks.values())
        sorted_sub = sorted(
            subjects, key=lambda s: (raw[s] - blocks[s], weights[s], s), reverse=True
        )
        for s in sorted_sub:
            if used >= capacity:
                break
            blocks[s] += 1
            used += 1

    for s in subjects:
        if coeffs.get(s, 0) > 0 and blocks[s] == 0:
            blocks[s] = 1

    used = sum(blocks.values())
    if used > capacity:
        sub_priority = sorted(subjects, key=lambda s: (weights[s], s))
        idx = 0
        while used > capacity and idx < len(sub_priority):
            s = sub_priority[idx]
            if blocks[s] > 1:
                blocks[s] -= 1
                used -= 1
            else:
                idx += 1

    return blocks


def low_priority_subjects(subjects: Sequence[str], coeffs: Dict[str, int]) -> "set[str]":
    values = sorted(coeffs.get(s, 0) for s in subjects)
    if not values:
        return set()
    median = values[len(values) // 2]
    return {
        s for s in subjects if coeffs.get(s, 0) <= median and catalog.type_for(s) != "calc"
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
        weak = weaknesses.get(subject, 1.0) >= catalog.S4_LIMIT
        type = catalog.type_for(subject)
        if subject in half_subjects:
            requests.append(
                dict(
                    subject=subject,
                    minutes=catalog.HALF_BLOCK_MINUTES,
                    type=type,
                    weak=weak,
                )
            )
            continue
        for _ in range(count):
            requests.append(
                dict(
                    subject=subject,
                    minutes=block_minutes,
                    type=type,
                    weak=weak,
                )
            )
    requests.sort(key=lambda r: (r["weak"] is False, r["subject"]))
    return requests
