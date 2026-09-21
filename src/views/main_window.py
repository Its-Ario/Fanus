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
from src.views.pages.attendance_page import AttendancePage
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
        self.attendance_page = AttendancePage(current_user=self.current_user)
        self.pages.addWidget(self.attendance_page)

        students_page.student_opened.connect(self._open_student_panel)
        self.student_panel.back_requested.connect(lambda: self._navigate_to(1))
        self.grade_entry_page.back_requested.connect(lambda: self._navigate_to(0))
        self.attendance_page.back_requested.connect(lambda: self._navigate_to(0))

        self.dashboard_nav_item = self.sidebar.add_nav_item("🏠", "داشبورد", lambda: self._navigate_to(0))
        self.students_nav_item = self.sidebar.add_nav_item("👥", "دانش آموزان", lambda: self._navigate_to(1))
        self.grades_nav_item = self.sidebar.add_nav_item(
            "📝", "آزمون‌ها و نمرات", lambda: self._navigate_to(self.pages.indexOf(self.grade_entry_page))
        )
        self.attendance_nav_item = self.sidebar.add_nav_item(
            "🗓", "حضور و غیاب", lambda: self._navigate_to(self.pages.indexOf(self.attendance_page))
        )
        self.analytics_nav_item = self.sidebar.add_nav_item("📊", "آمار", lambda: self._navigate_to(2))
        self.settings_nav_item = self.sidebar.add_nav_item("⚙️", "تنظیمات", lambda: self._navigate_to(3))
        self._nav_by_page = {
            dashboard_page: self.dashboard_nav_item,
            students_page: self.students_nav_item,
            self.student_panel: self.students_nav_item,
            self.grade_entry_page: self.grades_nav_item,
            self.attendance_page: self.attendance_nav_item,
            analytics_page: self.analytics_nav_item,
            self.settings_page: self.settings_nav_item,
        }

        self.sidebar.finalize()

    def _open_student_panel(self, student) -> None:
        self.student_panel.load(student)
        self._navigate_to(self.pages.indexOf(self.student_panel))

    def _navigate_to(self, index: int) -> None:
        settings_index = self.pages.indexOf(self.settings_page)
        if (
            self.pages.currentWidget() is self.settings_page
            and index != settings_index
            and not self.settings_page.confirm_navigation_away()
        ):
            self._restore_current_nav_item()
            return
        for page in (self.grade_entry_page, self.attendance_page):
            if (
                self.pages.currentWidget() is page
                and index != self.pages.indexOf(page)
                and not page.confirm_navigation_away()
            ):
                self._restore_current_nav_item()
                return
        if self.pages.currentWidget() is self.student_panel and index != self.pages.indexOf(self.student_panel):
            if self.student_panel.notes.unlocked:
                self.student_panel.notes.lock()
        self.pages.setCurrentIndex(index)

    def _restore_current_nav_item(self) -> None:
        item = self._nav_by_page.get(self.pages.currentWidget())
        if item:
            item.setChecked(True)

    def closeEvent(self, event) -> None:
        current = self.pages.currentWidget()
        if self.settings_page.confirm_navigation_away() and (
            current not in (self.grade_entry_page, self.attendance_page)
            or current.confirm_navigation_away()
        ):
            if self.student_panel.notes.unlocked:
                self.student_panel.notes.lock()
            event.accept()
        else:
            event.ignore()
