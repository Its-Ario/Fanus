from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtProperty
from PyQt5.QtWidgets import QButtonGroup, QFrame, QPushButton, QVBoxLayout


class NavItem(QPushButton):
    """A sidebar button that collapses cleanly to icon-only mode."""

    def __init__(self, icon_emoji: str, label: str):
        super().__init__()
        self.icon_emoji = icon_emoji
        self.label_text = label
        self.setProperty("class", "NavItem")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.set_expanded(True)

    def set_expanded(self, expanded: bool):
        if expanded:
            self.setText(f"{self.icon_emoji}   {self.label_text}")
            self.setProperty("collapsed", "false")
        else:
            self.setText(self.icon_emoji)
            self.setProperty("collapsed", "true")

        self.style().unpolish(self)
        self.style().polish(self)


class Sidebar(QFrame):
    COLLAPSED_WIDTH = 64
    EXPANDED_WIDTH = 220

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self._expanded = True
        self._width = self.EXPANDED_WIDTH
        self.setFixedWidth(self._width)

        self.animation = QPropertyAnimation(self, b"sidebar_width")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(6)

        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setObjectName("ToggleBtn")
        self.toggle_btn.setFixedHeight(36)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_btn)
        layout.addSpacing(6)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_items = []
        self.layout_ref = layout

    def add_nav_item(self, icon: str, label: str, on_click=None) -> NavItem:
        item = NavItem(icon, label)
        self.nav_group.addButton(item)
        self.nav_items.append(item)
        self.layout_ref.addWidget(item)
        if on_click:
            item.clicked.connect(on_click)
        return item

    def finalize(self):
        self.layout_ref.addStretch()
        if self.nav_items:
            self.nav_items[0].setChecked(True)

    def toggle(self):
        self._expanded = not self._expanded
        target = self.EXPANDED_WIDTH if self._expanded else self.COLLAPSED_WIDTH

        for item in self.nav_items:
            item.set_expanded(self._expanded)

        self.animation.stop()
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(target)
        self.animation.start()

    def get_sidebar_width(self):
        return self._width

    def set_sidebar_width(self, value):
        self._width = value
        self.setFixedWidth(value)

    sidebar_width = pyqtProperty(int, get_sidebar_width, set_sidebar_width)
