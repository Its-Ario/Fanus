from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.storage.db import DatabaseCredentials, get_database_manager
from src.storage.models import AuditLog, CounselorNote
from src.views.components.ui_kit import DataTable, FormField, PrimaryButton
from src.views.pages.settings.dialogs import PasswordChangeDialog, VaultPinDialog

ACTION_LABELS = {
    "school.update": "ویرایش مدرسه",
    "class.create": "ایجاد کلاس",
    "class.update": "ویرایش کلاس",
    "class.delete": "حذف کلاس",
    "user.create": "ایجاد کاربر",
    "user.update": "ویرایش کاربر",
    "user.role_change": "تغییر نقش",
    "user.activate": "فعال سازی",
    "user.deactivate": "غیرفعال سازی",
    "user.password_reset": "بازنشانی رمز",
    "vault.pin_change": "تغییر پین گاوصندوق",
    "password.self_change": "تغییر رمز شخصی",
    "exam.create": "ایجاد آزمون",
    "grade.bulk_save": "ثبت گروهی نمرات",
    "attendance.bulk_save": "ثبت گروهی حضور و غیاب",
}


class _AuditModel(QAbstractTableModel):
    HEADERS = ("تاریخ", "کاربر", "عملیات", "جزئیات")

    def __init__(self):
        super().__init__()
        self.rows = ()

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = tuple(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            return self.HEADERS[section]
        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        values = (
            str(row.created_at),
            row.actor_name,
            ACTION_LABELS.get(row.action, row.action),
            row.details or "—",
        )
        if role == Qt.DisplayRole:
            return values[index.column()]
        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter
        return None


class SecurityPanel(QWidget):
    def __init__(self, actor, parent=None):
        super().__init__(parent)
        self.actor = actor
        self.page = 0
        self.unlocked = False
        layout = QVBoxLayout(self)
        password = PrimaryButton("تغییر رمز عبور")
        password.clicked.connect(lambda: PasswordChangeDialog(actor, self).exec_())
        layout.addWidget(password)
        self.vault = QWidget()
        vault_layout = QVBoxLayout(self.vault)
        self.pin = FormField("پین فعلی گاوصندوق", password=True, revealable=True)
        unlock = PrimaryButton("باز کردن گاوصندوق")
        unlock.clicked.connect(self._unlock)
        vault_layout.addWidget(QLabel("گاوصندوق محرمانه"))
        vault_layout.addWidget(self.pin)
        vault_layout.addWidget(unlock)
        self.vault.setHidden(actor.role != "counselor")
        layout.addWidget(self.vault)
        self.audit = QWidget()
        audit_layout = QVBoxLayout(self.audit)
        audit_layout.addWidget(QLabel("گزارش تغییرات"))
        self.table = DataTable()
        self.model = _AuditModel()
        self.table.setModel(self.model)
        audit_layout.addWidget(self.table)
        self.audit.setHidden(not actor.can_manage_users)
        layout.addWidget(self.audit, 1)
        self.reload()

    def _unlock(self):
        try:
            get_database_manager().unlock_vault(DatabaseCredentials.from_vault_pin(self.pin.text()))
            self.unlocked = True
            self.pin.hide()
            self.vault.layout().itemAt(2).widget().hide()
            count = CounselorNote.select().count()
            button = PrimaryButton("تغییر پین گاوصندوق")
            button.clicked.connect(lambda: VaultPinDialog(self.actor, self).exec_())
            self.vault.layout().addWidget(QLabel(f"یادداشت های فعال: {count}"))
            self.vault.layout().addWidget(button)
        except Exception as exc:
            self.pin.set_error(str(exc))

    def reload(self):
        if self.actor.can_manage_users:
            self.model.set_rows(
                AuditLog.select()
                .where(~AuditLog.action.startswith("note."))
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .paginate(self.page + 1, 25)
            )
