from pathlib import Path

import jdatetime
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QLabel,
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.storage import backup_ops
from src.storage.db import get_database_manager
from src.storage.models import SchoolProfile
from src.styles.theme import Colors
from src.views.components.ui_kit import Card, PrimaryButton, SecondaryButton


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
    """Create a portable .fanusbak, or restore one (admins only) and quit."""

    def __init__(self, actor, parent=None):
        super().__init__(parent)
        self.actor = actor

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        create_card = Card()
        layout.addWidget(create_card)
        create_card.body_layout.addWidget(_heading("ساخت نسخهٔ پشتیبان"))
        create_card.body_layout.addWidget(
            _muted(
                "یک فایل رمزگذاری‌شدهٔ .fanusbak شامل کل پایگاه دادهٔ مدرسه می‌سازد؛ "
                "برای انتقال به رایانهٔ نو، نگهداری روی حافظهٔ جانبی یا بازیابی پس از خرابی دیسک."
            )
        )
        self.include_vault = QCheckBox("گنجاندن گاوصندوق محرمانهٔ مشاور")
        self.vault_hint = _muted(
            "برای گنجاندن گاوصندوق، ابتدا آن را در بخش «امنیت و گاوصندوق» باز کنید."
        )
        create_card.body_layout.addWidget(self.include_vault)
        create_card.body_layout.addWidget(self.vault_hint)
        make = PrimaryButton("ساخت نسخهٔ پشتیبان", icon="💾")
        make.clicked.connect(self._create)
        create_card.body_layout.addWidget(make)

        if getattr(actor, "can_manage_users", False):
            restore_card = Card()
            layout.addWidget(restore_card)
            restore_card.body_layout.addWidget(_heading("بازیابی از نسخهٔ پشتیبان"))
            warning = _muted(
                "هشدار: بازیابی همهٔ داده‌های فعلی را با محتوای فایل پشتیبان جایگزین می‌کند "
                "و بازگشت‌پذیر نیست. پس از پایان، برنامه بسته می‌شود."
            )
            warning.setStyleSheet(f"font-size:12px; color:{Colors.ERROR};")
            restore_card.body_layout.addWidget(warning)
            restore = SecondaryButton("انتخاب فایل و بازیابی", icon="↩")
            restore.clicked.connect(self._restore)
            restore_card.body_layout.addWidget(restore)

        layout.addStretch(1)
        self._refresh_vault_option()

    # -- lifecycle ------------------------------------------------------------
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

    # -- actions ------------------------------------------------------------
    def _default_name(self) -> str:
        school = SchoolProfile.get_or_none(id=1)
        slug = (school.school_name if school and school.school_name else "fanus").strip()
        slug = slug.replace(" ", "_") or "fanus"
        stamp = jdatetime.date.today().strftime("%Y_%m_%d")
        return f"{slug}_backup_{stamp}.fanusbak"

    def _create(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیرهٔ نسخهٔ پشتیبان", self._default_name(),
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
        QMessageBox.information(self, "انجام شد", "نسخهٔ پشتیبان با موفقیت ساخته شد.")

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
            "همهٔ داده‌های فعلی جایگزین می‌شوند. این عمل بازگشت‌پذیر نیست."
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
            self, "بازیابی کامل شد",
            "داده‌ها بازیابی شدند. برنامه بسته می‌شود؛ لطفاً دوباره آن را باز کنید.",
        )
        QApplication.quit()
