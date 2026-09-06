"""Validated write operations for daily student attendance.

Kept UI-free so every entry surface shares one validation boundary (mirrors
``grade_ops``).
"""

from collections import namedtuple
from datetime import date as _date

from src.storage.db import db
from src.storage.models import AttendanceRecord, AttendanceStatus

SaveResult = namedtuple("SaveResult", ("created", "updated"))


def save_attendance_bulk(record_date: _date, entries, *, actor=None) -> SaveResult:
    """Write one day's changed attendance rows in a single transaction.

    ``entries`` is an iterable of ``{student, status, reason}``. The row key is
    ``(student, record_date)`` — the unique index the model already carries.

    A ``present`` status with no reason and no existing row writes nothing (that is
    the default state). Any model ``AttendanceValidationError`` rolls the whole
    batch back. ``actor`` is accepted for symmetry; auditing is the caller's job.
    """
    created = updated = 0
    students = [e["student"] for e in list(entries) if e.get("student") is not None]
    existing = {
        row.student_id: row
        for row in AttendanceRecord.select().where(
            AttendanceRecord.date == record_date,
            AttendanceRecord.student << [s.id for s in students],
        )
    } if students else {}

    with db.atomic():
        for entry in entries:
            student = entry["student"]
            status = entry["status"]
            reason = (entry.get("reason") or "").strip() or None
            row = existing.get(student.id)
            if row is None:
                if status == AttendanceStatus.PRESENT and reason is None:
                    continue
                row = AttendanceRecord(
                    student=student, date=record_date, status=status, reason=reason
                )
                row.save(force_insert=True)
                existing[student.id] = row
                created += 1
            elif row.status != status or row.reason != reason:
                row.status = status
                row.reason = reason
                row.save()
                updated += 1
    return SaveResult(created=created, updated=updated)


def list_attendance(student, *, since=None, statuses=None, limit=None) -> list:
    query = AttendanceRecord.select().where(AttendanceRecord.student == student)
    if since is not None:
        query = query.where(AttendanceRecord.date >= since)
    if statuses is not None:
        query = query.where(AttendanceRecord.status << tuple(statuses))
    query = query.order_by(AttendanceRecord.date.desc())
    if limit is not None:
        query = query.limit(limit)
    return list(query)
