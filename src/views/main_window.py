from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.styles.app_style import APP_STYLE
from src.utils.get_version import get_version
from src.utils.persian_utils import to_persian_digits
from src.views.components.sidebar import Sidebar
from src.views.components.title_bar import TitleBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1200, 750)
        self.setStyleSheet(APP_STYLE)

        wrapper = QWidget()
        wrapper.setObjectName("CentralWrapper")
        self.setCentralWidget(wrapper)

        outer_layout = QVBoxLayout(wrapper)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.title_bar = TitleBar(self, title="فانوس")
        outer_layout.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = Sidebar()
        self.pages = QStackedWidget()
        self.pages.setObjectName("Pages")

        body.addWidget(self.sidebar)
        body.addWidget(self.pages, stretch=1)
        outer_layout.addLayout(body, stretch=1)

        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setFixedHeight(30)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 0, 10, 0)

        footer_label = QLabel(f"فانوس - نسخه {to_persian_digits(get_version())}")
        footer_label.setObjectName("FooterText")
        footer_layout.addWidget(footer_label)
        footer_layout.addStretch()

        grip = QSizeGrip(footer)
        footer_layout.addWidget(grip)

        outer_layout.addWidget(footer)

        self._setup_navigation()

    def _setup_navigation(self):

        self.sidebar.add_nav_item(
            "🏠", "داشبورد", lambda: self.pages.setCurrentIndex(0)
        )
        self.sidebar.add_nav_item("👥", "دانش‌آموزان", lambda: print("TODO"))
        self.sidebar.add_nav_item("📅", "برنامه‌ها", lambda: print("TODO"))
        self.sidebar.add_nav_item("📊", "آمار", lambda: print("TODO"))
        self.sidebar.add_nav_item("⚙️", "تنظیمات", lambda: print("TODO"))

        self.sidebar.finalize()
