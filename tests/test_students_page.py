from src.storage.db import DatabaseManager
from src.storage.models import Classroom, RiskLevel, Student
from src.views.pages import students_page
from src.views.pages.students_page import (
    PAGE_SIZE,
    StudentPage,
    StudentTableModel,
    load_students_page,
)


def test_student_page_searches_active_students_and_paginates(tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    try:
        manager.initialize_public()
        classroom = Classroom.create(name="دهم الف", major="ریاضی فیزیک")
        for number in range(PAGE_SIZE + 2):
            Student.create(
                national_id=f"1000000{number:03d}",
                first_name="سارا" if number == 0 else "دانش‌آموز",
                last_name=f"نام{number:02d}",
                classroom=classroom,
                risk_level=RiskLevel.MEDIUM,
            )
        Student.create(
            national_id="9999999999",
            first_name="غیرفعال",
            last_name="دانش‌آموز",
            classroom=classroom,
            is_active=False,
        )

        first_page = load_students_page(page=0)
        second_page = load_students_page(page=1)
        by_name = load_students_page("سارا")
        by_id = load_students_page("1000000000")

        assert first_page.total == PAGE_SIZE + 2
        assert len(first_page.students) == PAGE_SIZE
        assert len(second_page.students) == 2
        assert [student.first_name for student in by_name.students] == ["سارا"]
        assert [student.national_id for student in by_id.students] == ["1000000000"]
    finally:
        manager.close()


def test_student_table_model_exposes_student_for_row_actions(qtbot, tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    try:
        manager.initialize_public()
        classroom = Classroom.create(name="یازدهم ب")
        student = Student.create(
            national_id="1000000001",
            first_name="رضا",
            last_name="کریمی",
            classroom=classroom,
        )
        model = StudentTableModel()
        model.set_students((student,))

        assert model.rowCount() == 1
        assert model.index(0, 0).data() == "رضا کریمی"
        assert model.index(0, 0).data(256) is student  # Qt.UserRole
    finally:
        manager.close()


def test_students_page_debounces_search_and_surfaces_a_retryable_error(qtbot, monkeypatch):
    calls = []

    def fake_loader(query, page):
        calls.append((query, page))
        return StudentPage(students=(), total=0)

    monkeypatch.setattr(students_page, "load_students_page", fake_loader)
    page = students_page.StudentsPage()
    qtbot.addWidget(page)
    page.search_input.setText("سارا")
    qtbot.wait(249)
    assert calls == []
    qtbot.wait(2)
    assert calls == [("سارا", 0)]

    monkeypatch.setattr(
        students_page,
        "load_students_page",
        lambda *_: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    page.reload()
    assert not page.error_state.isHidden()
