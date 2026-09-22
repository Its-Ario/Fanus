from src.storage.db import DatabaseManager
from src.storage.models import Classroom, Student
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
                first_name="سارا" if number == 0 else "دانش آموز",
                last_name=f"نام{number:02d}",
                classroom=classroom,
            )
        Student.create(
            national_id="9999999999",
            first_name="غیرفعال",
            last_name="دانش آموز",
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


def test_load_students_page_filters_by_major_and_classroom_and_sorts_columns(tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    try:
        manager.initialize_public()
        math_room = Classroom.create(name="دهم ریاضی", grade_level=10, major="ریاضی فیزیک")
        exp_room = Classroom.create(name="یازدهم تجربی", grade_level=11, major="علوم تجربی")

        Student.create(
            national_id="1000000001",
            first_name="آرش",
            last_name="الف",
            classroom=math_room,
            major="ریاضی فیزیک",
        )
        Student.create(
            national_id="1000000002",
            first_name="بابک",
            last_name="ب",
            classroom=math_room,
            major="ریاضی فیزیک",
        )
        Student.create(
            national_id="1000000003",
            first_name="پری",
            last_name="پ",
            classroom=exp_room,
            major="علوم تجربی",
        )

        by_major = load_students_page(major="ریاضی فیزیک")
        by_grade = load_students_page(grade_level=11)
        by_class = load_students_page(classroom_id=exp_room.id)
        by_id_desc = load_students_page(sort_key=1, sort_desc=True)

        assert by_major.total == 2
        assert {s.national_id for s in by_major.students} == {"1000000001", "1000000002"}
        assert [s.national_id for s in by_grade.students] == ["1000000003"]
        assert [s.national_id for s in by_class.students] == ["1000000003"]
        assert [s.national_id for s in by_id_desc.students] == [
            "1000000003",
            "1000000002",
            "1000000001",
        ]
    finally:
        manager.close()


def test_major_selection_narrows_the_class_filter(qtbot, tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    try:
        manager.initialize_public()
        Classroom.create(grade_level=10, major="ریاضی فیزیک", code="۱")
        Classroom.create(grade_level=10, major="علوم تجربی", code="۲")

        page = students_page.StudentsPage()
        qtbot.addWidget(page)
        page.reload()
        assert page.class_filter.count() == 3

        page.major_filter.setCurrentIndex(page.major_filter.findData("ریاضی فیزیک"))
        rooms = [page.class_filter.itemText(i) for i in range(1, page.class_filter.count())]
        assert page.class_filter.count() == 2
        assert all("ریاضی" in name for name in rooms)
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
        assert model.index(0, 0).data(256) is student
    finally:
        manager.close()


def test_students_page_debounces_search_and_surfaces_a_retryable_error(qtbot, monkeypatch):
    calls = []

    def fake_loader(query, page, **kwargs):
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
        lambda *_, **__: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    page.reload()
    assert not page.error_state.isHidden()
