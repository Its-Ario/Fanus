from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.views.components.ui_kit import (
    AIInsightCard,
    Card,
    Divider,
    PrimaryButton,
    ProgressBar,
    SecondaryButton,
    SectionHeader,
    StatCard,
    StudentRow,
)


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(20)

        header_row = QHBoxLayout()

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        page_title = QLabel("داشبورد")
        page_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")

        page_subtitle = QLabel("خلاصه‌ای از وضعیت دانش‌آموزان و برنامه‌های مطالعاتی")
        page_subtitle.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")

        title_box.addWidget(page_title)
        title_box.addWidget(page_subtitle)

        header_row.addLayout(title_box)
        header_row.addStretch()
        header_row.addWidget(PrimaryButton("دانش‌آموز جدید", icon="➕"))

        layout.addLayout(header_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)

        stats_row.addWidget(StatCard("کل دانش‌آموزان", 312, "👥"))
        stats_row.addWidget(StatCard("ریسک بالا", 8, "⚠️", accent_color=Colors.ERROR))
        stats_row.addWidget(StatCard("برنامه‌های فعال", 289, "📚"))
        stats_row.addWidget(StatCard("نرخ تکمیل هفتگی", "۷۸٪", "✅", accent_color=Colors.SUCCESS))

        layout.addLayout(stats_row)

        layout.addWidget(AIInsightCard(
            "۳ دانش‌آموز بر اساس چک-این‌های این هفته نشانه‌های اولیه فرسودگی تحصیلی دارند.",
            on_review=lambda: print("Navigate to risk page")
        ))

        columns = QHBoxLayout()
        columns.setSpacing(18)

        attention_card = Card(padding=0)
        attention_card.body_layout.setSpacing(0)
        attention_card.body_layout.setContentsMargins(18, 14, 18, 8)

        attention_card.body_layout.addWidget(
            SectionHeader("نیازمند توجه", "مشاهده همه", lambda: print("view all"))
        )

        students = [
            ("سارا احمدی", "پایه دهم - ریاضی", "High"),
            ("رضا کریمی", "پایه یازدهم - فیزیک", "Medium"),
            ("نگین محمدی", "پایه نهم - شیمی", "Medium"),
            ("امیر حسینی", "پایه دوازدهم - زیست", "High"),
        ]
        for name, subtitle, risk in students:
            attention_card.body_layout.addWidget(
                StudentRow(name, subtitle, risk, on_click=lambda n=name: print(f"Open profile: {n}"))
            )

        columns.addWidget(attention_card, stretch=6)

        side_column = QVBoxLayout()
        side_column.setSpacing(18)

        progress_card = Card()
        progress_title = QLabel("پیشرفت هفتگی کلاس‌ها")
        progress_title.setAlignment(Qt.AlignRight)
        progress_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {Colors.TEXT_MAIN};")
        progress_card.body_layout.addWidget(progress_title)
        progress_card.body_layout.addWidget(Divider())

        subjects = [
            ("ریاضی", 82, Colors.PRIMARY),
            ("فیزیک", 64, Colors.WARNING),
            ("شیمی", 91, Colors.SUCCESS),
            ("زیست‌شناسی", 47, Colors.ERROR),
        ]
        for subject_name, percent, color in subjects:
            row = QVBoxLayout()
            row.setSpacing(4)

            label_row = QHBoxLayout()
            name_label = QLabel(subject_name)
            name_label.setAlignment(Qt.AlignRight)
            name_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};")

            percent_label = QLabel(to_persian_digits(f"{percent}٪"))
            percent_label.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {color};")

            label_row.addWidget(name_label)
            label_row.addStretch()
            label_row.addWidget(percent_label)

            row.addLayout(label_row)
            row.addWidget(ProgressBar(value=percent, color=color))

            progress_card.body_layout.addLayout(row)

        side_column.addWidget(progress_card)

        actions_card = Card()
        actions_title = QLabel("اقدامات سریع")
        actions_title.setAlignment(Qt.AlignRight)
        actions_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {Colors.TEXT_MAIN};")
        actions_card.body_layout.addWidget(actions_title)
        actions_card.body_layout.addWidget(Divider())

        actions_card.body_layout.addWidget(SecondaryButton("ساخت برنامه مطالعاتی", icon="📅"))
        actions_card.body_layout.addWidget(SecondaryButton("افزودن دانش‌آموز", icon="👤"))
        actions_card.body_layout.addWidget(SecondaryButton("خروجی گزارش هفتگی", icon="📄"))

        side_column.addWidget(actions_card)
        side_column.addStretch()

        columns.addLayout(side_column, stretch=4)

        layout.addLayout(columns)
        layout.addStretch()