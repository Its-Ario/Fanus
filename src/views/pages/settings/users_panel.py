from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.storage.models import User
from src.storage.settings_ops import set_user_active
from src.views.components.ui_kit import DataTable, PrimaryButton, SecondaryButton
from src.views.pages.settings.dialogs import UserDialog


class _UsersModel(QAbstractTableModel):
    HEADERS = ("نام", "نام کاربری", "نقش", "دسترسی", "وضعیت")
    def __init__(self): super().__init__(); self.rows = ()
    def set_rows(self, rows): self.beginResetModel(); self.rows = tuple(rows); self.endResetModel()
    def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.rows)
    def columnCount(self, parent=QModelIndex()): return len(self.HEADERS)
    def headerData(self, section, orientation, role=Qt.DisplayRole): return self.HEADERS[section] if role == Qt.DisplayRole and orientation == Qt.Horizontal else None
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        user = self.rows[index.row()]; values=(user.full_name,user.username,{"assistant":"معاون","counselor":"مشاور","principal":"مدیر"}.get(user.role,user.role),"مدیر تنظیمات" if user.can_manage_users else "—","فعال" if user.is_active else "غیرفعال")
        return values[index.column()] if role == Qt.DisplayRole else (user if role == Qt.UserRole else None)


class UsersPanel(QWidget):
    def __init__(self, actor, editable, parent=None):
        super().__init__(parent); self.actor, self.editable = actor, editable
        layout=QVBoxLayout(self); header=QHBoxLayout(); header.addWidget(QLabel("مدیریت کاربران و دسترسی‌ها")); header.addStretch(); self.edit=SecondaryButton("ویرایش"); self.edit.clicked.connect(lambda: self._edit(self.table.currentIndex())); self.edit.setHidden(not editable); header.addWidget(self.edit); self.toggle=SecondaryButton("فعال/غیرفعال"); self.toggle.clicked.connect(self.toggle_selected); self.toggle.setHidden(not editable); header.addWidget(self.toggle); self.add=PrimaryButton("کاربر جدید"); self.add.clicked.connect(self._add); self.add.setHidden(not editable); header.addWidget(self.add); layout.addLayout(header)
        self.inactive=QCheckBox("نمایش کاربران غیرفعال"); self.inactive.toggled.connect(self.reload); layout.addWidget(self.inactive); self.notice=QLabel("برای ویرایش تنظیمات به دسترسی «مدیریت کاربران» نیاز دارید."); self.notice.setHidden(editable); layout.addWidget(self.notice)
        self.table=DataTable(); self.model=_UsersModel(); self.table.setModel(self.model); self.table.doubleClicked.connect(self._edit); layout.addWidget(self.table,1); self.reload()
    def reload(self):
        query=User.select().order_by(User.is_active.desc(), User.full_name)
        if not self.inactive.isChecked(): query=query.where(User.is_active)
        self.model.set_rows(query)
    def _add(self):
        if UserDialog(self.actor,parent=self).exec_(): self.reload()
    def _edit(self,index):
        if self.editable and index.isValid() and UserDialog(self.actor,index.data(Qt.UserRole),self).exec_(): self.reload()
    def toggle_selected(self):
        user=self.table.currentIndex().data(Qt.UserRole)
        if user:
            try: set_user_active(self.actor,user,not user.is_active); self.reload()
            except Exception: pass
