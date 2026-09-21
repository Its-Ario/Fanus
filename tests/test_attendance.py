from datetime import date
from types import SimpleNamespace

from src.storage.attendance_ops import list_attendance, save_attendance_bulk
from src.storage.db import DatabaseManager
from src.storage.models import (
    AcademicMajor,
    AttendanceRecord,
    AttendanceStatus,
    AttendanceValidationError,
    Classroom,
    Student,
)
from src.views.pages.attendance_page import STATUS_COL, AttendancePage

DAY = date(2026, 9, 1)


def _class(tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    manager.initialize_public()
    classroom = Classroom.create(name="دهم", grade_level=10, major=AcademicMajor.MATH)
    students = [
        Student.create(
            national_id=f"400000000{i}",
            first_name=f"د{i}",
            last_name=f"خ{i}",
            classroom=classroom,
        )
        for i in range(1, 4)
    ]
    return manager, students


def _entry(student, status, reason=None):
    return {"student": student, "status": status, "reason": reason}


def test_model_rejects_unknown_status(tmp_path):
    _, students = _class(tmp_path)
    try:
        AttendanceRecord.create(student=students[0], date=DAY, status="sleeping")
    except AttendanceValidationError:
        pass
    else:
        raise AssertionError("expected AttendanceValidationError for unknown status")


def test_bulk_create_then_update_in_place(tmp_path):
    _, students = _class(tmp_path)
    result = save_attendance_bulk(
        DAY,
        [
            _entry(students[0], AttendanceStatus.ABSENT),
            _entry(students[1], AttendanceStatus.LATE),
        ],
    )
    assert result == (2, 0)
    assert AttendanceRecord.select().count() == 2

    result = save_attendance_bulk(
        DAY,
        [
            _entry(students[0], AttendanceStatus.EXCUSED, "بیماری"),
            _entry(students[1], AttendanceStatus.LATE),
        ],
    )
    assert result == (0, 1)
    assert AttendanceRecord.select().count() == 2
    row = AttendanceRecord.get(AttendanceRecord.student == students[0])
    assert row.status == AttendanceStatus.EXCUSED
    assert row.reason == "بیماری"


def test_present_without_reason_writes_nothing(tmp_path):
    _, students = _class(tmp_path)
    result = save_attendance_bulk(DAY, [_entry(students[0], AttendanceStatus.PRESENT)])
    assert result == (0, 0)
    assert AttendanceRecord.select().count() == 0


def test_reason_cleared_on_return_to_present(tmp_path):
    _, students = _class(tmp_path)
    save_attendance_bulk(DAY, [_entry(students[0], AttendanceStatus.ABSENT, "سفر")])
    result = save_attendance_bulk(DAY, [_entry(students[0], AttendanceStatus.PRESENT)])
    assert result == (0, 1)
    row = AttendanceRecord.get()
    assert row.status == AttendanceStatus.PRESENT
    assert row.reason is None


def test_list_attendance_filters(tmp_path):
    _, students = _class(tmp_path)
    save_attendance_bulk(DAY, [_entry(students[0], AttendanceStatus.ABSENT)])
    save_attendance_bulk(date(2026, 9, 2), [_entry(students[0], AttendanceStatus.LATE)])
    assert len(list_attendance(students[0])) == 2
    assert len(list_attendance(students[0], since=date(2026, 9, 2))) == 1
    only_absent = list_attendance(students[0], statuses=[AttendanceStatus.ABSENT])
    assert [r.status for r in only_absent] == [AttendanceStatus.ABSENT]


def test_page_read_only_for_non_assistant(tmp_path, qtbot):
    _class(tmp_path)
    page = AttendancePage(current_user=SimpleNamespace(role="principal", full_name="م"))
    qtbot.addWidget(page)
    assert page.read_only is True
    assert not page.save_button.isVisibleTo(page)
    assert not page.table.cellWidget(0, STATUS_COL).isEnabled()


def test_page_save_writes_changed_row(tmp_path, qtbot):
    _, students = _class(tmp_path)
    page = AttendancePage(current_user=SimpleNamespace(role="assistant", full_name="ع"))
    qtbot.addWidget(page)
    assert not page.has_unsaved_changes()

    combo = page.table.cellWidget(0, STATUS_COL)
    combo.setCurrentIndex(combo.findData(AttendanceStatus.ABSENT))
    assert page.has_unsaved_changes()

    page._save()
    marked = page._rows[0]["student"]
    row = AttendanceRecord.get(AttendanceRecord.student == marked)
    assert row.status == AttendanceStatus.ABSENT
    assert not page.has_unsaved_changes()
