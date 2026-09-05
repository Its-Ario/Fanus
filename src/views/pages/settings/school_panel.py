from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.storage.models import Classroom, SchoolProfile, Student, User, parse_levels
from src.storage.settings_ops import update_school
from src.styles.theme import Colors
from src.views.components.ui_kit import Card, FormField, PrimaryButton, SecondaryButton


class SchoolPanel(QWidget):
    def __init__(self, actor, editable, parent=None):
        super().__init__(parent)
        self.actor, self.editable, self._dirty = actor, editable, False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        self.notice = QLabel("برای ویرایش تنظیمات به دسترسی «مدیریت کاربران» نیاز دارید.")
        self.notice.setStyleSheet(
            f"background:{Colors.SURFACE_HOVER}; padding:8px; border-radius:6px;"
        )
        self.notice.setHidden(editable)
        layout.addWidget(self.notice)
        self.card = Card()
        layout.addWidget(self.card)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.card.body_layout.addWidget(self.summary)
        self.name = FormField("نام مدرسه")
        self.card.body_layout.addWidget(self.name)
        row = QHBoxLayout()
        self.cancel = SecondaryButton("انصراف")
        self.save = PrimaryButton("ذخیره")
        row.addWidget(self.cancel)
        row.addStretch()
        row.addWidget(self.save)
        self.card.body_layout.addLayout(row)
        layout.addStretch()
        self.name.input.textEdited.connect(lambda: setattr(self, "_dirty", True))
        self.cancel.clicked.connect(self.reload)
        self.save.clicked.connect(self._save)
        self.name.setEnabled(editable)
        self.cancel.setEnabled(editable)
        self.save.setEnabled(editable)
        self.reload()

    def reload(self):
        profile = SchoolProfile.get_or_none(id=1)
        if not profile:
            return
        labels = {"elementry": "دبستان", "middle": "دوره اول", "high": "دوره دوم"}
        levels = "، ".join(labels[value] for value in parse_levels(profile.type))
        self.summary.setText(
            f"نام مدرسه: {profile.school_name}\nسال تحصیلی: {profile.academic_year}\nمقاطع: {levels}\nکلاس ها: {Classroom.select().count()} · دانش آموزان: {Student.select().where(Student.is_active).count()} · کاربران: {User.select().where(User.is_active).count()}"
        )
        self.name.input.setText(profile.school_name)
        self._dirty = False

    def _save(self):
        try:
            update_school(self.actor, self.name.text())
            self.reload()
        except Exception as exc:
            self.name.set_error(str(exc))
