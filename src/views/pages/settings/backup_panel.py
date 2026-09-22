from pathlib import Path

import jdatetime
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.storage import backup_ops, rollover_ops
from src.storage.db import get_database_manager
from src.storage.models import SchoolProfile
from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.utils.validators import validate_academic_year
from src.views.components.ui_kit import Card, FormField, PrimaryButton, SecondaryButton


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"font-size:15px; font-weight:800; color:{Colors.TEXT_MAIN};")
    return label


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"font-size:12px; color:{Colors.TEXT_MUTED};")
    return label


class BackupPanel(QWidget):
    def __init__(self, actor, parent=None):
        super().__init__(parent)
        self.actor = actor

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        create_card = Card()
        layout.addWidget(create_card)
        create_card.body_layout.addWidget(_heading("ساخت نسخه پشتیبان"))
        create_card.body_layout.addWidget(
            _muted(
                "یک فایل رمزگذاری‌شده .fanusbak شامل کل پایگاه داده مدرسه می‌سازد؛ "
                "برای انتقال به رایانه نو، نگهداری روی حافظه جانبی یا بازیابی پس از خرابی دیسک."
            )
        )
        self.include_vault = QCheckBox("اضافه کردن گاوصندوق محرمانه مشاور")
        self.vault_hint = _muted(
            "برای اضافه کردن گاوصندوق، ابتدا آن را در بخش «امنیت و گاوصندوق» باز کنید."
        )
        create_card.body_layout.addWidget(self.include_vault)
        create_card.body_layout.addWidget(self.vault_hint)
        make = PrimaryButton("ساخت نسخه پشتیبان", icon="archive")
        make.clicked.connect(self._create)
        create_card.body_layout.addWidget(make)

        if getattr(actor, "can_manage_users", False):
            restore_card = Card()
            layout.addWidget(restore_card)
            restore_card.body_layout.addWidget(_heading("بازیابی از نسخه پشتیبان"))
            warning = _muted(
                "هشدار: بازیابی همه داده‌های فعلی را با محتوای فایل پشتیبان جایگزین می‌کند "
                "و بازگشت‌پذیر نیست. پس از پایان، برنامه بسته می‌شود."
            )
            warning.setStyleSheet(f"font-size:12px; color:{Colors.ERROR};")
            restore_card.body_layout.addWidget(warning)
            restore = SecondaryButton("انتخاب فایل و بازیابی", icon="rotate-ccw")
            restore.clicked.connect(self._restore)
            restore_card.body_layout.addWidget(restore)

            rollover_card = Card()
            layout.addWidget(rollover_card)
            rollover_card.body_layout.addWidget(_heading("شروع سال تحصیلی جدید"))
            rollover_card.body_layout.addWidget(
                _muted(
                    "ابتدا یک نسخه پشتیبان کامل گرفته می‌شود، سپس همه دانش‌آموزان، "
                    "نمرات، آزمون‌ها، حضور و غیاب و برنامه‌های مطالعاتی سال جاری پاک "
                    "می‌شوند و سال تحصیلی به مقدار تازه به‌روزرسانی می‌شود."
                )
            )
            ro_warning = _muted(
                "هشدار: این عمل بازگشت‌پذیر نیست. تنها راه بازیابی، فایل پشتیبانی است "
                "که در همین مرحله ساخته می‌شود. پس از پایان، برنامه بسته می‌شود."
            )
            ro_warning.setStyleSheet(f"font-size:12px; color:{Colors.ERROR};")
            rollover_card.body_layout.addWidget(ro_warning)
            rollover = SecondaryButton("پشتیبان‌گیری و شروع سال نو", icon="graduation-cap")
            rollover.clicked.connect(self._roll_over)
            rollover_card.body_layout.addWidget(rollover)

        layout.addStretch(1)
        self._refresh_vault_option()

    def reload(self):
        self._refresh_vault_option()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_vault_option()

    def _refresh_vault_option(self):
        is_counselor = getattr(self.actor, "role", None) == "counselor"
        try:
            unlocked = get_database_manager().vault_unlocked
        except Exception:
            unlocked = False
        self.include_vault.setVisible(is_counselor and unlocked)
        self.vault_hint.setVisible(is_counselor and not unlocked)
        if not self.include_vault.isVisible():
            self.include_vault.setChecked(False)

    def _default_name(self) -> str:
        school = SchoolProfile.get_or_none(id=1)
        slug = (school.school_name if school and school.school_name else "fanus").strip()
        slug = slug.replace(" ", "_") or "fanus"
        stamp = jdatetime.date.today().strftime("%Y_%m_%d")
        return f"{slug}_backup_{stamp}.fanusbak"

    def _create(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره نسخه پشتیبان",
            self._default_name(),
            "فایل پشتیبان فانوس (*.fanusbak)",
        )
        if not path:
            return
        if not path.endswith(".fanusbak"):
            path += ".fanusbak"
        include_vault = self.include_vault.isVisible() and self.include_vault.isChecked()
        try:
            backup_ops.create_backup(Path(path), self.actor, include_vault=include_vault)
        except backup_ops.BackupError as exc:
            QMessageBox.warning(self, "ساخت پشتیبان ناموفق بود", str(exc))
            return
        QMessageBox.information(self, "انجام شد", "نسخه پشتیبان با موفقیت ساخته شد.")

    def _restore(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل پشتیبان", "", "فایل پشتیبان فانوس (*.fanusbak)"
        )
        if not path:
            return
        try:
            info = backup_ops.inspect_backup(Path(path))
        except backup_ops.BackupError as exc:
            QMessageBox.warning(self, "فایل پشتیبان نامعتبر است", str(exc))
            return

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("تأیید بازیابی")
        dialog.setText(
            f"مدرسه: {info.school_name or '—'}\n"
            f"تاریخ ساخت: {info.created_at_fa or '—'}\n"
            f"شامل گاوصندوق: {'بله' if info.includes_vault else 'خیر'}\n\n"
            "همه داده‌های فعلی جایگزین می‌شوند. این عمل بازگشت‌پذیر نیست."
        )
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        dialog.setDefaultButton(QMessageBox.Cancel)
        dialog.button(QMessageBox.Yes).setText("بازیابی و بستن برنامه")
        dialog.button(QMessageBox.Cancel).setText("انصراف")
        if dialog.exec_() != QMessageBox.Yes:
            return

        try:
            backup_ops.restore_backup(Path(path), self.actor)
        except backup_ops.BackupError as exc:
            QMessageBox.critical(self, "بازیابی ناموفق بود", str(exc))
            return
        QMessageBox.information(
            self,
            "بازیابی کامل شد",
            "داده‌ها بازیابی شدند. برنامه بسته می‌شود؛ لطفاً دوباره آن را باز کنید.",
        )
        QApplication.quit()

    def _roll_over(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره نسخه پشتیبان پیش از شروع سال نو",
            self._default_name().replace("_backup_", "_rollover_"),
            "فایل پشتیبان فانوس (*.fanusbak)",
        )
        if not path:
            return
        if not path.endswith(".fanusbak"):
            path += ".fanusbak"

        try:
            wipe_vault = bool(get_database_manager().vault_unlocked)
        except Exception:
            wipe_vault = False

        try:
            backup_ops.create_backup(Path(path), self.actor, include_vault=wipe_vault)
        except backup_ops.BackupError as exc:
            QMessageBox.warning(self, "ساخت پشتیبان ناموفق بود", str(exc))
            return

        current = SchoolProfile.get_or_none(id=1)
        dialog = RolloverConfirmDialog(getattr(current, "academic_year", ""), wipe_vault, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        try:
            counts = rollover_ops.roll_over_year(
                dialog.new_year,
                keep_classrooms=dialog.keep_classrooms,
                wipe_vault=wipe_vault,
                actor=self.actor,
            )
        except Exception as exc:  # noqa: BLE001 - atomic() already rolled back
            QMessageBox.critical(
                self,
                "شروع سال نو ناموفق بود",
                f"هیچ داده‌ای پاک نشد.\n\n{exc}",
            )
            return

        removed = to_persian_digits(str(counts.get("Student", 0)))
        QMessageBox.information(
            self,
            "سال تحصیلی جدید آغاز شد",
            f"{removed} دانش‌آموز و داده‌های تحصیلی مرتبط پاک شدند. "
            "برنامه بسته می‌شود؛ لطفاً دوباره آن را باز کنید.",
        )
        QApplication.quit()


class RolloverConfirmDialog(QDialog):
    def __init__(self, current_year: str, wipe_vault: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("شروع سال تحصیلی جدید")
        self.new_year = ""
        self.keep_classrooms = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.year_field = FormField("سال تحصیلی جدید", "برای مثال: ۱۴۰۵-۱۴۰۶")
        self.year_field.input.setText(current_year or "")
        layout.addWidget(self.year_field)

        self.keep_box = QCheckBox("نگه داشتن کلاس‌ها (بدون دانش‌آموز)")
        self.keep_box.setChecked(True)
        layout.addWidget(self.keep_box)

        warning = _muted(
            "دانش‌آموزان، نمرات، آزمون‌ها، حضور و غیاب و برنامه‌های مطالعاتی "
            "پاک می‌شوند. این عمل بازگشت‌پذیر نیست."
        )
        warning.setStyleSheet(f"font-size:12px; color:{Colors.ERROR};")
        layout.addWidget(warning)

        if not wipe_vault:
            layout.addWidget(_muted("یادداشت‌های محرمانه پاک نمی‌شوند چون گاوصندوق قفل است."))

        buttons = QDialogButtonBox()
        self.ok_button = buttons.addButton("شروع سال نو", QDialogButtonBox.AcceptRole)
        buttons.addButton("انصراف", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.year_field.input.textChanged.connect(self._revalidate)
        self._revalidate()

    def _revalidate(self):
        self.ok_button.setEnabled(validate_academic_year(self.year_field.text()))

    def _accept(self):
        if not validate_academic_year(self.year_field.text()):
            self.year_field.set_error("سال تحصیلی نامعتبر است.")
            return
        self.new_year = self.year_field.text()
        self.keep_classrooms = self.keep_box.isChecked()
        self.accept()
