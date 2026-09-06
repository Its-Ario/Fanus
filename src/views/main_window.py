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
from src.views.components.sidebar import Sidebar
from src.views.components.title_bar import TitleBar
from src.views.pages.analytics_page import AnalyticsPage
from src.views.pages.dashboard_page import DashboardPage
from src.views.pages.grade_entry_page import GradeEntryPage
from src.views.pages.settings import SettingsPage
from src.views.pages.student_panel import StudentPanel
from src.views.pages.students_page import StudentsPage


class MainWindow(QMainWindow):
    def __init__(self, current_user=None):
        super().__init__()
        self.current_user = current_user
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

        self.sidebar = Sidebar(user=current_user)
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

        footer_label = QLabel("فانوس - نسخه ۱.۰.۰")
        footer_label.setObjectName("FooterText")
        footer_layout.addWidget(footer_label)
        footer_layout.addStretch()

        grip = QSizeGrip(footer)
        footer_layout.addWidget(grip)

        outer_layout.addWidget(footer)

        self._setup_navigation()

    def _setup_navigation(self):
        dashboard_page = DashboardPage()
        students_page = StudentsPage(current_user=self.current_user)
        analytics_page = AnalyticsPage()
        self.settings_page = SettingsPage(current_user=self.current_user)
        self.pages.addWidget(dashboard_page)
        self.pages.addWidget(students_page)
        self.pages.addWidget(analytics_page)
        self.pages.addWidget(self.settings_page)
        self.student_panel = StudentPanel(current_user=self.current_user)
        self.pages.addWidget(self.student_panel)
        self.grade_entry_page = GradeEntryPage(current_user=self.current_user)
        self.pages.addWidget(self.grade_entry_page)

        students_page.student_opened.connect(self._open_student_panel)
        students_page.open_grade_entry.connect(self._open_grade_entry)
        self.student_panel.back_requested.connect(lambda: self._navigate_to(1))
        self.grade_entry_page.back_requested.connect(lambda: self._navigate_to(1))

        self.sidebar.add_nav_item("🏠", "داشبورد", lambda: self._navigate_to(0))
        self.sidebar.add_nav_item("👥", "دانش آموزان", lambda: self._navigate_to(1))
        self.sidebar.add_nav_item("📊", "آمار", lambda: self._navigate_to(2))
        self.sidebar.add_nav_item("⚙️", "تنظیمات", lambda: self._navigate_to(3))

        self.sidebar.finalize()

    def _open_student_panel(self, student) -> None:
        self.student_panel.load(student)
        self._navigate_to(self.pages.indexOf(self.student_panel))

    def _open_grade_entry(self) -> None:
        self._navigate_to(self.pages.indexOf(self.grade_entry_page))

    def _navigate_to(self, index: int) -> None:
        settings_index = self.pages.indexOf(self.settings_page)
        if (
            self.pages.currentWidget() is self.settings_page
            and index != settings_index
            and not self.settings_page.confirm_navigation_away()
        ):
            self.sidebar.nav_items[settings_index].setChecked(True)
            return
        grade_index = self.pages.indexOf(self.grade_entry_page)
        if (
            self.pages.currentWidget() is self.grade_entry_page
            and index != grade_index
            and not self.grade_entry_page.confirm_navigation_away()
        ):
            return
        if self.pages.currentWidget() is self.student_panel and index != self.pages.indexOf(self.student_panel):
            if self.student_panel.notes.unlocked:
                self.student_panel.notes.lock()
        self.pages.setCurrentIndex(index)

    def closeEvent(self, event) -> None:
        if self.settings_page.confirm_navigation_away() and (
            self.pages.currentWidget() is not self.grade_entry_page
            or self.grade_entry_page.confirm_navigation_away()
        ):
            if self.student_panel.notes.unlocked:
                self.student_panel.notes.lock()
            event.accept()
        else:
            event.ignore()
