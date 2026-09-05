from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.planner import catalog
from src.storage.models import PlannerSettings
from src.storage.settings_ops import update_planner_settings
from src.styles.theme import Colors
from src.views.components.ui_kit import Card, PrimaryButton, SecondaryButton

_WEIGHT_FIELDS = (
    ("s1", "هم‌راستایی با ساعات اوج تمرکز"),
    ("s2", "تنوع نوع دروس در طول روز"),
    ("s3", "کنترل تعداد دروس متمایز روزانه"),
    ("s4", "تکرار با فاصله برای دروس ضعیف"),
    ("s5", "ساختار آزمون و جبرانی روز جمعه"),
)


class PlannerPanel(QWidget):
    """Tuning knobs for the study-plan engine: block length + soft-rule weights."""

    def __init__(self, actor, editable, parent=None):
        super().__init__(parent)
        self.actor, self.editable = actor, editable
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.notice = QLabel("برای ویرایش تنظیمات به دسترسی «مدیریت کاربران» نیاز دارید.")
        self.notice.setStyleSheet(
            f"background:{Colors.SURFACE_HOVER}; padding:8px; border-radius:6px;"
        )
        self.notice.setHidden(editable)
        layout.addWidget(self.notice)

        card = Card()
        layout.addWidget(card)
        form = QFormLayout()
        form.setSpacing(10)

        self.block = QComboBox()
        for minutes in (90, 75):
            self.block.addItem(f"{minutes} دقیقه", minutes)
        form.addRow("طول هر بلوک مطالعه", self.block)

        self.weights = {}
        for key, label in _WEIGHT_FIELDS:
            spin = QSpinBox()
            spin.setRange(0, 500)
            spin.setSingleStep(5)
            self.weights[key] = spin
            form.addRow(f"جریمهٔ نقض «{label}»", spin)

        card.body_layout.addLayout(form)

        hint = QLabel("عدد بزرگ‌تر یعنی موتور برنامه‌ریزی سخت‌گیرتر روی آن قاعده.")
        hint.setStyleSheet(f"font-size:12px; color:{Colors.TEXT_MUTED};")
        card.body_layout.addWidget(hint)

        row = QHBoxLayout()
        self.cancel = SecondaryButton("انصراف")
        self.save = PrimaryButton("ذخیره")
        row.addWidget(self.cancel)
        row.addStretch()
        row.addWidget(self.save)
        card.body_layout.addLayout(row)
        layout.addStretch()

        self.cancel.clicked.connect(self.reload)
        self.save.clicked.connect(self._save)
        for widget in (self.block, self.save, self.cancel, *self.weights.values()):
            widget.setEnabled(editable)

        self.reload()

    def reload(self):
        settings = PlannerSettings.get_instance()
        stored = {**catalog.DEFAULT_SOFT_WEIGHTS, **settings.weights}
        index = self.block.findData(settings.block_minutes)
        self.block.setCurrentIndex(index if index >= 0 else 0)
        for key, spin in self.weights.items():
            spin.setValue(int(stored.get(key, catalog.DEFAULT_SOFT_WEIGHTS[key])))

    def _save(self):
        try:
            update_planner_settings(
                self.actor,
                block_minutes=self.block.currentData(),
                weights={key: spin.value() for key, spin in self.weights.items()},
            )
            self.reload()
        except Exception as exc:
            self.notice.setText(str(exc))
            self.notice.setHidden(False)
