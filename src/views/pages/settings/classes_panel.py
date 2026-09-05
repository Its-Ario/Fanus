from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from src.storage.models import Classroom, Student
from src.storage.settings_ops import delete_classroom
from src.views.components.ui_kit import DataTable, PrimaryButton, SecondaryButton
from src.views.pages.settings.dialogs import ClassDialog


class _ClassesModel(QAbstractTableModel):
    HEADERS = ("نام کلاس", "پایه", "رشته", "تعداد دانش آموز")

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
        return len(self.HEADERS)

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
        room = self.rows[index.row()]
        values = (
            room.name,
            room.grade_level,
            room.major,
            Student.select().where((Student.classroom == room) & Student.is_active).count(),
        )
        if role == Qt.DisplayRole:
            return values[index.column()]
        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter
        return room if role == Qt.UserRole else None


class ClassesPanel(QWidget):
    def __init__(self, actor, editable, parent=None):
        super().__init__(parent)
        self.actor, self.editable = actor, editable
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("مدیریت کلاس ها و پایه ها"))
        header.addStretch()
        self.edit = SecondaryButton("ویرایش")
        self.edit.clicked.connect(self._edit_selected)
        self.edit.setHidden(not editable)
        header.addWidget(self.edit)
        self.delete = SecondaryButton("حذف")
        self.delete.clicked.connect(self.delete_selected)
        self.delete.setHidden(not editable)
        header.addWidget(self.delete)
        self.add = PrimaryButton("کلاس جدید")
        self.add.clicked.connect(self._add)
        self.add.setHidden(not editable)
        header.addWidget(self.add)
        layout.addLayout(header)
        self.notice = QLabel("برای ویرایش تنظیمات به دسترسی «مدیریت کاربران» نیاز دارید.")
        self.notice.setHidden(editable)
        layout.addWidget(self.notice)
        self.table = DataTable()
        self.model = _ClassesModel()
        self.table.setModel(self.model)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table, 1)
        self.reload()

    def reload(self):
        self.model.set_rows(Classroom.select().order_by(Classroom.grade_level, Classroom.name))

    def _add(self):
        if ClassDialog(self.actor, parent=self).exec_():
            self.reload()

    def _edit(self, index):
        if not self.editable or not index.isValid():
            return
        if ClassDialog(self.actor, index.data(Qt.UserRole), self).exec_():
            self.reload()

    def _edit_selected(self):
        self._edit(self.table.currentIndex())

    def delete_selected(self):
        index = self.table.currentIndex()
        room = index.data(Qt.UserRole)
        if room and QMessageBox.question(self, "حذف کلاس", "کلاس حذف شود؟") == QMessageBox.Yes:
            try:
                delete_classroom(self.actor, room)
                self.reload()
            except Exception as exc:
                QMessageBox.warning(self, "حذف کلاس", str(exc))
