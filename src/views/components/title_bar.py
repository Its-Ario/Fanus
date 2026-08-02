from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class TitleBar(QFrame):
    """Custom title bar replacing the native OS bar. Fully draggable."""

    def __init__(self, parent_window, title="فانوس"):
        super().__init__()
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)
        self.setLayoutDirection(Qt.LeftToRight)
        self.parent_window = parent_window
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 10, 0)
        layout.setSpacing(8)

        title_label = QLabel(f"{title}  🏮")
        title_label.setObjectName("AppTitle")

        layout.addWidget(title_label)
        layout.addStretch()

        self.btn_min = self._make_btn("─", "MinBtn")
        self.btn_max = self._make_btn("□", "MaxBtn")
        self.btn_close = self._make_btn("✕", "CloseBtn")

        self.btn_min.clicked.connect(self.parent_window.showMinimized)
        self.btn_max.clicked.connect(self.toggle_maximize)
        self.btn_close.clicked.connect(self.parent_window.close)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def _make_btn(self, text, obj_name):
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        btn.setProperty("class", "WindowBtn")
        btn.setFixedSize(32, 28)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
        else:
            self.parent_window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            self.parent_window.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        self.toggle_maximize()
