from PyQt5.QtCore import QSignalBlocker, Qt
from PyQt5.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.styles.theme import Colors
from src.views.components.ui_kit import PrimaryButton, SecondaryButton
from src.views.pages.settings.classes_panel import ClassesPanel
from src.views.pages.settings.planner_panel import PlannerPanel
from src.views.pages.settings.school_panel import SchoolPanel
from src.views.pages.settings.security_panel import SecurityPanel
from src.views.pages.settings.users_panel import UsersPanel

TABS = (
    "عمومی و اطلاعات مدرسه",
    "مدیریت کلاس ها و پایه ها",
    "مدیریت کاربران و دسترسی ها",
    "موتور برنامه‌ریزی",
    "امنیت و گاوصندوق",
)

SEGMENTED_STYLE = f"""
QFrame#SegmentedBar {{
    background-color: {Colors.SURFACE_HOVER};
    border: 1px solid {Colors.BORDER};
    border-radius: 10px;
}}
QPushButton#SegItem {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 0 18px;
    font-size: 13px;
    font-weight: 600;
    color: {Colors.TEXT_MUTED};
}}
QPushButton#SegItem:hover {{
    color: {Colors.TEXT_MAIN};
}}
QPushButton#SegItem:checked {{
    background-color: {Colors.SURFACE};
    border: 1px solid {Colors.BORDER};
    color: {Colors.PRIMARY};
}}
"""


class UnsavedChangesDialog(QDialog):
    """Ask for an explicit discard decision without platform-default actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تغییرات ذخیره نشده")
        self.setMinimumWidth(390)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)

        title = QLabel("تغییرات ذخیره نشده دارید")
        title.setAlignment(Qt.AlignRight)
        title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        layout.addWidget(title)

        detail = QLabel("آیا می خواهید بدون ذخیره از این صفحه خارج شوید؟")
        detail.setAlignment(Qt.AlignRight)
        detail.setWordWrap(True)
        detail.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        layout.addWidget(detail)

        layout.addSpacing(6)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        cancel = SecondaryButton("بازگشت")
        discard = PrimaryButton("دور ریختن تغییرات")
        cancel.clicked.connect(self.reject)
        discard.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addStretch()
        actions.addWidget(discard)
        layout.addLayout(actions)


class SettingsPage(QWidget):
    def __init__(self, current_user, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        editable = bool(current_user and current_user.can_manage_users)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("تنظیمات")
        title.setStyleSheet("font-size:20px; font-weight:800;")
        layout.addWidget(title)

        self.seg_bar = QFrame()
        self.seg_bar.setObjectName("SegmentedBar")
        self.seg_bar.setStyleSheet(SEGMENTED_STYLE)
        self.seg_bar.setFixedHeight(44)
        seg_layout = QHBoxLayout(self.seg_bar)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(4)

        self.seg_group = QButtonGroup(self)
        self.seg_group.setExclusive(True)
        for index, text in enumerate(TABS):
            button = QPushButton(text)
            button.setObjectName("SegItem")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(32)
            self.seg_group.addButton(button, index)
            seg_layout.addWidget(button)

        bar_row = QHBoxLayout()
        bar_row.addWidget(self.seg_bar)
        bar_row.addStretch()
        layout.addLayout(bar_row)

        self.stack = QStackedWidget()
        self.school = SchoolPanel(current_user, editable)
        self.classes = ClassesPanel(current_user, editable)
        self.users = UsersPanel(current_user, editable)
        self.planner = PlannerPanel(current_user, editable)
        self.security = SecurityPanel(current_user)
        for panel in (self.school, self.classes, self.users, self.planner, self.security):
            self.stack.addWidget(panel)
        layout.addWidget(self.stack, 1)

        self.seg_group.buttonClicked.connect(lambda btn: self._change(self.seg_group.id(btn)))
        self.seg_group.button(0).setChecked(True)
        self._change(0)

    def _change(self, index):
        if self.stack.currentIndex() == 0 and index != 0 and self.school._dirty:
            if not self.confirm_navigation_away():
                with QSignalBlocker(self.seg_group):
                    self.seg_group.button(0).setChecked(True)
                return
        self.stack.setCurrentIndex(index)

    def confirm_navigation_away(self) -> bool:
        """Confirm discarding Tab 1 edits before any page-level navigation."""
        if not self.school._dirty:
            return True
        if UnsavedChangesDialog(self).exec_() != QDialog.Accepted:
            return False
        self.school.reload()
        return True

    def showEvent(self, event):
        super().showEvent(event)
        self.school.reload()
        self.classes.reload()
        self.users.reload()
        self.planner.reload()
        self.security.reload()
