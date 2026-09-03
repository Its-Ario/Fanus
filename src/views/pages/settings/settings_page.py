from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.styles.theme import Colors
from src.views.pages.settings.classes_panel import ClassesPanel
from src.views.pages.settings.school_panel import SchoolPanel
from src.views.pages.settings.security_panel import SecurityPanel
from src.views.pages.settings.users_panel import UsersPanel

TABS = ("عمومی و اطلاعات مدرسه", "مدیریت کلاس‌ها و پایه‌ها", "مدیریت کاربران و دسترسی‌ها", "امنیت و گاوصندوق")

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
        self.security = SecurityPanel(current_user)
        for panel in (self.school, self.classes, self.users, self.security):
            self.stack.addWidget(panel)
        layout.addWidget(self.stack, 1)

        self.seg_group.buttonClicked.connect(lambda btn: self._change(self.seg_group.id(btn)))
        self.seg_group.button(0).setChecked(True)
        self._change(0)

    def _change(self, index):
        if index != 0 and self.school._dirty:
            self.school.reload()
        self.stack.setCurrentIndex(index)

    def showEvent(self, event):
        super().showEvent(event)
        self.school.reload()
        self.classes.reload()
        self.users.reload()
        self.security.reload()
