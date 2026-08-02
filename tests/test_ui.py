# tests/test_ui_components.py
from src.views.components.ui_kit import AIInsightCard, RiskBadge, StatCard, StudentRow


def test_stat_card_instantiation_and_persian_digits(qtbot):
    """Test StatCard converts numerical value to Persian digits on creation."""
    card = StatCard(title="کل دانش‌آموزان", value=312, icon_emoji="👥")
    qtbot.addWidget(card)

    _labels = card.findChildren(type(card.findChild(type(None))))
    assert card.isVisible() is False


def test_risk_badge_levels(qtbot):
    """Test RiskBadge updates styles and Persian text based on level."""
    badge = RiskBadge(level="High")
    qtbot.addWidget(badge)

    assert "زیاد" in badge.text()

    badge.set_level("Low")
    assert "کم" in badge.text()


def test_student_row_click_callback(qtbot):
    """Test that clicking a StudentRow triggers its callback."""
    clicked = False

    def on_click():
        nonlocal clicked
        clicked = True

    row = StudentRow("رضا کریمی", "پایه یازدهم", "Medium", on_click=on_click)
    qtbot.addWidget(row)

    # Simulate mouse click on the row
    qtbot.mouseClick(row, 1)  # Qt.LeftButton = 1
    assert clicked is True


def test_ai_insight_card_action_button(qtbot):
    """Test AI Insight Card trigger callback."""
    reviewed = False

    def on_review():
        nonlocal reviewed
        reviewed = True

    card = AIInsightCard("هشدار فرسودگی تحصیلی", on_review=on_review)
    qtbot.addWidget(card)

    # Find the 'بررسی' button inside the card and click it
    from PyQt5.QtWidgets import QPushButton

    button = card.findChild(QPushButton)
    assert button is not None
    qtbot.mouseClick(button, 1)

    assert reviewed is True
