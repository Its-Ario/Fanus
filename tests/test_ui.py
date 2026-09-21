from types import SimpleNamespace

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPushButton

from src.views.components.ui_kit import AIInsightCard, Dropdown, StatCard
from src.views.pages.student_panel import StudentPanel


def _tab_labels(panel):
    return {b.text() for b in panel.findChildren(QPushButton) if b.objectName() == "SegItem"}


def test_assistant_cannot_see_study_plan_tab(qtbot):
    panel = StudentPanel(current_user=SimpleNamespace(role="assistant"))
    qtbot.addWidget(panel)

    assert "برنامه مطالعاتی هفتگی" not in _tab_labels(panel)
    assert panel.plan not in panel._tab_viewports


def test_counselor_keeps_study_plan_tab(qtbot):
    panel = StudentPanel(current_user=SimpleNamespace(role="counselor"))
    qtbot.addWidget(panel)

    assert "برنامه مطالعاتی هفتگی" in _tab_labels(panel)
    assert panel.plan in panel._tab_viewports


def test_dropdown_supports_selection_and_keyboard_navigation(qtbot):
    dropdown = Dropdown()
    dropdown.addItem("اول", 1)
    dropdown.addItem("دوم", 2)
    qtbot.addWidget(dropdown)
    dropdown.show()

    qtbot.keyClick(dropdown, Qt.Key_Down)

    assert dropdown.currentData() == 2
    assert "QAbstractItemView" in dropdown.styleSheet()


def test_stat_card_instantiation_and_persian_digits(qtbot):
    card = StatCard(title="کل دانش آموزان", value=312, icon_name="users")
    qtbot.addWidget(card)

    _labels = card.findChildren(type(card.findChild(type(None))))
    assert card.isVisible() is False


def test_ai_insight_card_action_button(qtbot):
    reviewed = False

    def on_review():
        nonlocal reviewed
        reviewed = True

    card = AIInsightCard("هشدار فرسودگی تحصیلی", on_review=on_review)
    qtbot.addWidget(card)

    from PyQt5.QtWidgets import QPushButton

    button = card.findChild(QPushButton)
    assert button is not None
    qtbot.mouseClick(button, 1)

    assert reviewed is True
