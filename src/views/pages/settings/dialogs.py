from PyQt5.QtWidgets import QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QVBoxLayout

from src.storage.models import AcademicMajor, SchoolProfile, Student
from src.storage.settings_ops import (
    change_own_password,
    save_classroom,
    save_user,
)
from src.utils.persian_utils import to_persian_digits
from src.utils.validators import validate_username
from src.views.components.ui_kit import FormField, PrimaryButton, SecondaryButton


class _Dialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 22, 24, 20)
        self.layout.setSpacing(11)
        self.error = QLabel()
        self.error.setStyleSheet("color: #DC2626;")
        self.error.setWordWrap(True)
        self.error.hide()

    def fail(self, message):
        self.error.setText(str(message))
        self.error.show()

    def actions(self, text, callback):
        row = QHBoxLayout()
        cancel = SecondaryButton("انصراف")
        cancel.clicked.connect(self.reject)
        save = PrimaryButton(text)
        save.clicked.connect(callback)
        row.addWidget(cancel)
        row.addStretch()
        row.addWidget(save)
        self.layout.addWidget(self.error)
        self.layout.addLayout(row)


class ClassDialog(_Dialog):
    def __init__(self, actor, instance=None, parent=None):
        super().__init__("کلاس جدید" if instance is None else "ویرایش کلاس", parent)
        self.actor, self.instance = actor, instance
        profile = SchoolProfile.get_or_none(id=1)
        from src.storage.models import grade_options

        self.grade = QComboBox()
        self.major = QComboBox()
        for value in grade_options(profile.type if profile else "high"):
            self.grade.addItem(to_persian_digits(value), value)
        for value in AcademicMajor.VALUES:
            self.major.addItem(value, value)
        self.code = FormField("عنوان/کد کلاس", "برای مثال: ۱۰۱")
        self.layout.addWidget(QLabel("پایه تحصیلی"))
        self.layout.addWidget(self.grade)
        self.layout.addWidget(QLabel("رشته تحصیلی"))
        self.layout.addWidget(self.major)
        self.layout.addWidget(self.code)
        if instance:
            self.grade.setCurrentIndex(max(0, self.grade.findData(instance.grade_level)))
            self.major.setCurrentIndex(max(0, self.major.findData(instance.major)))
            self.code.input.setText(instance.code)
            if Student.select().where((Student.classroom == instance) & Student.is_active).exists():
                self.grade.setEnabled(False)
                self.major.setEnabled(False)
                self.layout.addWidget(
                    QLabel("پایه و رشتهٔ کلاس دارای دانش آموز فعال قابل تغییر نیست.")
                )
        self.grade.currentIndexChanged.connect(self._sync_major)
        self._sync_major()
        self.actions("ذخیره", self._save)

    def _sync_major(self):
        self.major.setEnabled(self.grade.currentData() >= 10 if self.grade.currentData() else False)
        self.major.setCurrentIndex(
            self.major.findData(AcademicMajor.GENERAL)
        ) if self.grade.currentData() and self.grade.currentData() < 10 else None

    def _save(self):
        try:
            profile = SchoolProfile.get_by_id(1)
            self.instance = save_classroom(
                self.actor,
                self.instance,
                grade_level=self.grade.currentData(),
                major=self.major.currentData(),
                code=to_persian_digits(self.code.text()),
                academic_year=profile.academic_year,
            )
            self.accept()
        except Exception as exc:
            self.fail(exc)


class UserDialog(_Dialog):
    def __init__(self, actor, instance=None, parent=None):
        super().__init__("کاربر جدید" if instance is None else "ویرایش کاربر", parent)
        self.actor, self.instance = actor, instance
        self.name = FormField("نام و نام خانوادگی")
        self.username = FormField("نام کاربری")
        self.role = QComboBox()
        [
            self.role.addItem(label, value)
            for value, label in (
                ("assistant", "معاون"),
                ("counselor", "مشاور"),
                ("principal", "مدیر مدرسه"),
            )
        ]
        self.manager = QCheckBox("مدیریت کاربران و تنظیمات")
        self.password = FormField(
            "رمز موقت" if instance else "رمز عبور (اختیاری)",
            "حداقل ۸ نویسه",
            password=True,
            revealable=True,
        )
        for widget in (
            self.name,
            self.username,
            QLabel("نقش"),
            self.role,
            self.manager,
            self.password,
        ):
            self.layout.addWidget(widget)
        if instance:
            self.name.input.setText(instance.full_name)
            self.username.input.setText(instance.username)
            self.username.setEnabled(False)
            self.role.setCurrentIndex(self.role.findData(instance.role))
            self.manager.setChecked(instance.can_manage_users)
            if instance.id == actor.id:
                self.role.setEnabled(False)
                self.manager.setEnabled(False)
        self.actions("ذخیره", self._save)

    def _save(self):
        username = self.username.text().lower()
        if self.instance is None and not validate_username(username):
            self.fail("نام کاربری باید ۳ تا ۲۰ حرف یا عدد انگلیسی باشد.")
            return
        if self.password.text() and len(self.password.text()) < 8:
            self.fail("رمز عبور باید دست کم ۸ نویسه باشد.")
            return
        try:
            self.instance = save_user(
                self.actor,
                self.instance,
                full_name=self.name.text(),
                username=username,
                role=self.role.currentData(),
                can_manage_users=self.manager.isChecked(),
                password=self.password.text() or None,
            )
            self.accept()
        except Exception as exc:
            self.fail(exc)


class PasswordChangeDialog(_Dialog):
    def __init__(self, actor, parent=None):
        super().__init__("تغییر رمز عبور", parent)
        self.actor = actor
        self.current = FormField("رمز فعلی", password=True, revealable=True)
        self.new = FormField("رمز جدید", "حداقل ۸ نویسه", password=True, revealable=True)
        self.confirm = FormField("تکرار رمز جدید", password=True, revealable=True)
        if actor.password_hash:
            self.layout.addWidget(self.current)
        self.layout.addWidget(self.new)
        self.layout.addWidget(self.confirm)
        self.actions("تغییر رمز", self._save)

    def _save(self):
        if self.new.text() != self.confirm.text():
            self.fail("دو رمز یکسان نیستند.")
            return
        try:
            change_own_password(self.actor, self.current.text(), self.new.text())
            self.accept()
        except Exception as exc:
            self.fail(exc)


class VaultPinDialog(_Dialog):
    def __init__(self, actor, parent=None):
        super().__init__("تغییر پین گاوصندوق", parent)
        self.actor = actor
        self.old = FormField("پین فعلی", password=True, revealable=True)
        self.new = FormField("پین جدید", "حداقل ۱۲ نویسه", password=True, revealable=True)
        self.ack = QCheckBox("می دانم پین فراموش شده قابل بازیابی نیست.")
        self.layout.addWidget(self.old)
        self.layout.addWidget(self.new)
        self.layout.addWidget(self.ack)
        self.layout.addWidget(
            QLabel("در صورت قطع ناگهانی برق هنگام عملیات، از نسخهٔ پشتیبان معتبر بازیابی کنید.")
        )
        self.actions("تغییر پین", self._save)

    def _save(self):
        if len(self.new.text()) < 12 or not self.ack.isChecked():
            self.fail("پین باید حداقل ۱۲ نویسه باشد و تأیید بازیابی ناپذیری لازم است.")
            return
        from src.core.auth import verify_password

        if self.actor.password_hash and verify_password(self.new.text(), self.actor.password_hash):
            self.fail("پین باید با رمز ورود متفاوت باشد.")
            return
        try:
            from src.storage.settings_ops import rotate_vault_pin

            rotate_vault_pin(self.actor, self.old.text(), self.new.text())
            self.accept()
        except Exception as exc:
            self.fail("عملیات ناتمام ماند؛ از نسخه پشتیبان معتبر بازیابی کنید. " + str(exc))
