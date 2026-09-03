from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.utils.profile_color import generate_profile_color


def apply_soft_shadow(widget, blur=18, y_offset=3, alpha=25):
    """Adds a subtle drop shadow. Safe to use on cards (not the main frameless window)."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(shadow)


class PrimaryButton(QPushButton):
    def __init__(self, text: str, icon: str | None = None):
        label = f"{icon}  {text}" if icon else text
        super().__init__(label)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY};
                color: white;
                font-weight: 600;
                font-size: 13px;
                border: none;
                border-radius: 8px;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: {Colors.PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: {Colors.PRIMARY_ACTIVE}; }}
            QPushButton:focus {{ border: 2px solid {Colors.TEXT_MAIN}; }}
        """)


class SecondaryButton(QPushButton):
    def __init__(self, text: str, icon: str | None = None):
        label = f"{icon}  {text}" if icon else text
        super().__init__(label)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SURFACE};
                color: {Colors.TEXT_MAIN};
                font-weight: 600;
                font-size: 13px;
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: {Colors.SURFACE_HOVER}; }}
            QPushButton:focus {{ border: 2px solid {Colors.PRIMARY}; }}
        """)


class StatCard(QFrame):
    def __init__(self, title: str, value, icon_emoji: str = "📊", accent_color: str | None = None):
        super().__init__()
        accent = accent_color or Colors.PRIMARY
        self.setFixedHeight(100)
        self.setObjectName("Card")
        self.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
            }}
        """)
        apply_soft_shadow(self, blur=16, y_offset=2, alpha=18)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)

        icon_bubble = QLabel(icon_emoji)
        icon_bubble.setFixedSize(44, 44)
        icon_bubble.setAlignment(Qt.AlignCenter)
        icon_bubble.setStyleSheet(f"""
            background-color: {accent}20;
            border-radius: 22px;
            font-size: 18px;
        """)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        value_label = QLabel(to_persian_digits(value))
        value_label.setAlignment(Qt.AlignRight)
        value_label.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {Colors.TEXT_MAIN};")

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignRight)
        title_label.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED}; font-weight: 500;")

        text_box.addWidget(value_label)
        text_box.addWidget(title_label)

        layout.addWidget(icon_bubble)
        layout.addSpacing(12)
        layout.addLayout(text_box)
        layout.addStretch()


class RiskBadge(QLabel):
    def __init__(self, level: str = "Low"):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.set_level(level)

    def set_level(self, level: str):
        level = level.capitalize()
        config = {
            "Low": (Colors.SUCCESS_BG, Colors.SUCCESS, "🟢 کم"),
            "Medium": (Colors.WARNING_BG, Colors.WARNING, "🟡 متوسط"),
            "High": (Colors.ERROR_BG, Colors.ERROR, "🔴 زیاد"),
        }
        bg, text_color, label = config.get(level, config["Low"])

        self.setText(label)
        self.setStyleSheet(f"""
            background-color: {bg};
            color: {text_color};
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 10px;
        """)
        self.setFixedHeight(24)


class AIInsightCard(QFrame):
    def __init__(self, message: str, on_review=None):
        super().__init__()
        self.setObjectName("AICard")
        self.setStyleSheet(f"""
            QFrame#AICard {{
                background-color: {Colors.AI_BG};
                border: 1px solid {Colors.AI_BORDER};
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        icon = QLabel("✨")
        icon.setStyleSheet("font-size: 18px;")

        text = QLabel(message)
        text.setWordWrap(True)
        text.setStyleSheet(f"color: {Colors.AI_ACCENT}; font-size: 13px; font-weight: 600;")

        layout.addWidget(icon)
        layout.addWidget(text, stretch=1)

        if on_review:
            review_btn = QPushButton("بررسی")
            review_btn.setCursor(Qt.PointingHandCursor)
            review_btn.setFixedHeight(32)
            review_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.AI_ACCENT};
                    color: white;
                    border-radius: 6px;
                    padding: 0 14px;
                    font-weight: 600;
                    font-size: 12px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: {Colors.AI_HOVER}; }}
            """)
            review_btn.clicked.connect(on_review)
            layout.addWidget(review_btn)


class Avatar(QLabel):
    def __init__(self, full_name: str, size: int = 40, color: str | None = None):
        super().__init__()
        self.setFixedSize(size, size)
        parts = full_name.split()
        initials = "".join([p[0] for p in parts[:2]]) if len(parts) > 1 else full_name[:2]

        color = color or generate_profile_color(full_name)

        self.setText(initials)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            background-color: {color};
            color: white;
            font-weight: 700;
            font-size: {int(size * 0.35)}px;
            border-radius: {size // 2}px;
        """)


class StudentRow(QFrame):
    def __init__(self, name: str, subtitle: str, risk_level: str, on_click=None):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("StudentRow")
        self.setStyleSheet(f"""
            QFrame#StudentRow {{
                background-color: {Colors.SURFACE};
                border-bottom: 1px solid {Colors.BORDER};
            }}
            QFrame#StudentRow:hover {{
                background-color: {Colors.SURFACE_HOVER};
            }}
        """)
        self.setFixedHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        avatar = Avatar(name, size=38)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Colors.TEXT_MAIN};")
        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        text_box.addWidget(name_label)
        text_box.addWidget(sub_label)

        badge = RiskBadge(risk_level)

        layout.addWidget(avatar)
        layout.addLayout(text_box, stretch=1)
        layout.addWidget(badge)

        self._on_click = on_click

    def mousePressEvent(self, event):
        if self._on_click:
            self._on_click()
        super().mousePressEvent(event)


class EmptyState(QWidget):
    def __init__(
        self,
        icon_emoji: str,
        title: str,
        subtitle: str,
        cta_text: str | None = None,
        on_cta=None,
    ):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        icon = QLabel(icon_emoji)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 40px;")

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_MAIN};")

        sub_label = QLabel(subtitle)
        sub_label.setAlignment(Qt.AlignCenter)
        sub_label.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")

        layout.addWidget(icon)
        layout.addWidget(title_label)
        layout.addWidget(sub_label)

        if cta_text:
            btn = PrimaryButton(cta_text)
            btn.setFixedWidth(170)
            if on_cta:
                btn.clicked.connect(on_cta)
            layout.addSpacing(6)
            layout.addWidget(btn, alignment=Qt.AlignCenter)


class SearchInput(QLineEdit):
    def __init__(self, placeholder="جستجوی دانش‌آموزان..."):
        super().__init__()
        self.setPlaceholderText(f"🔍  {placeholder}")
        self.setFixedHeight(38)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 13px;
                color: {Colors.TEXT_MAIN};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {Colors.PRIMARY};
            }}
        """)


class FormField(QWidget):
    """A labelled text field shared by focused forms such as setup and settings."""

    def __init__(
        self,
        label: str,
        placeholder: str = "",
        hint: str | None = None,
        password: bool = False,
        revealable: bool = False,
    ):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.setSizeConstraint(QLayout.SetMinimumSize)

        self.label = QLabel(label)
        self.label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};")

        self.input = QLineEdit()
        self.label.setBuddy(self.input)
        self.input.textEdited.connect(self.clear_error)
        self.input.setPlaceholderText(placeholder)
        self.input.setFixedHeight(38)
        if password:
            self.input.setEchoMode(QLineEdit.Password)
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                color: {Colors.TEXT_MAIN};
            }}
            QLineEdit:focus {{ border: 1.5px solid {Colors.PRIMARY}; }}
        """)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        # Placeholders provide the default guidance. This area is reserved for
        # validation feedback, keeping compact forms from growing at rest.
        self.message.setVisible(False)

        layout.addWidget(self.label)
        if password and revealable:
            input_row = QHBoxLayout()
            input_row.setContentsMargins(0, 0, 0, 0)
            input_row.setSpacing(6)
            self.reveal_button = QPushButton("نمایش")
            self.reveal_button.setCheckable(True)
            self.reveal_button.setCursor(Qt.PointingHandCursor)
            self.reveal_button.setFixedHeight(38)
            self.reveal_button.setStyleSheet(f"""
                QPushButton {{ background-color: {Colors.SURFACE}; color: {Colors.TEXT_MUTED}; border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 0 10px; font-size: 11px; font-weight: 600; }}
                QPushButton:hover, QPushButton:checked {{ background-color: {Colors.SURFACE_HOVER}; color: {Colors.TEXT_MAIN}; }}
                QPushButton:focus {{ border: 2px solid {Colors.PRIMARY}; }}
            """)
            self.reveal_button.toggled.connect(self._toggle_password_visibility)
            input_row.addWidget(self.input, stretch=1)
            input_row.addWidget(self.reveal_button)
            layout.addLayout(input_row)
        else:
            self.reveal_button = None
            layout.addWidget(self.input)
        layout.addWidget(self.message)

    def _toggle_password_visibility(self, visible: bool):
        self.input.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self.reveal_button.setText("پنهان" if visible else "نمایش")

    def text(self) -> str:
        return self.input.text().strip()

    def set_error(self, message: str):
        self.message.setText(message)
        self.message.setStyleSheet(f"font-size: 11px; color: {Colors.ERROR};")
        self.message.setVisible(True)
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.SURFACE};
                border: 1.5px solid {Colors.ERROR};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                color: {Colors.TEXT_MAIN};
            }}
        """)
        self._refresh_geometry()

    def clear_error(self, *_):
        self.message.setText("")
        self.message.setVisible(False)
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                color: {Colors.TEXT_MAIN};
            }}
            QLineEdit:focus {{ border: 1.5px solid {Colors.PRIMARY}; }}
        """)
        self._refresh_geometry()

    def _refresh_geometry(self):
        """Propagate changed helper text size through parent layouts immediately."""
        self.layout().invalidate()
        self.updateGeometry()

        parent = self.parentWidget()
        while parent:
            if parent.layout():
                parent.layout().invalidate()
            parent.updateGeometry()
            parent = parent.parentWidget()


class ProgressBar(QWidget):
    """Custom-painted RTL progress bar. Fills from RIGHT to LEFT."""

    def __init__(self, value: int = 0, color: str | None = None):
        super().__init__()
        self.value = max(0, min(100, value))
        self.color = color or Colors.PRIMARY
        self.setFixedHeight(8)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setBrush(QColor(Colors.BORDER))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 4, 4)

        fill_width = int(self.width() * (self.value / 100))
        x_start = self.width() - fill_width  # Manual RTL fill direction

        painter.setBrush(QColor(self.color))
        painter.drawRoundedRect(x_start, 0, fill_width, self.height(), 4, 4)

    def set_value(self, value: int):
        self.value = max(0, min(100, value))
        self.update()


class SectionHeader(QWidget):
    def __init__(self, title: str, action_text: str | None = None, on_action=None):
        super().__init__()
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_label.setFixedHeight(22)
        title_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {Colors.TEXT_MAIN};")
        layout.addWidget(title_label)
        layout.addStretch()

        if action_text:
            btn = QPushButton(action_text)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Colors.PRIMARY};
                    font-weight: 600;
                    font-size: 12px;
                    border: none;
                }}
                QPushButton:hover {{ text-decoration: underline; }}
            """)
            if on_action:
                btn.clicked.connect(on_action)
            layout.addWidget(btn)


class Divider(QFrame):
    def __init__(self, margin_v: int = 8):
        super().__init__()
        self.setFixedHeight(1)
        self.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")
        self.setContentsMargins(0, margin_v, 0, margin_v)


class DataTable(QTableView):
    """QTableView with the app's card styling: rounded border, quiet header,
    row separators, teal row selection, slim scrollbars."""

    def __init__(self):
        super().__init__()
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.setFrameShape(QFrame.NoFrame)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(42)
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.setStyleSheet(f"""
            QTableView {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                outline: none;
                gridline-color: transparent;
                selection-background-color: {Colors.PRIMARY}22;
                selection-color: {Colors.PRIMARY};
            }}
            QTableView::item {{
                padding: 0 12px;
                border-bottom: 1px solid {Colors.BORDER};
                color: {Colors.TEXT_MAIN};
                font-size: 13px;
            }}
            QTableView::item:hover {{
                background-color: {Colors.SURFACE_HOVER};
            }}
            QTableView::item:selected {{
                background-color: {Colors.PRIMARY}22;
                color: {Colors.PRIMARY};
            }}
            QHeaderView {{ background-color: transparent; }}
            QHeaderView::section {{
                background-color: {Colors.BACKGROUND};
                color: {Colors.TEXT_MUTED};
                font-size: 12px;
                font-weight: 700;
                padding: 9px 12px;
                border: none;
                border-bottom: 1px solid {Colors.BORDER};
            }}
            QHeaderView::section:first {{ border-top-right-radius: 10px; }}
            QHeaderView::section:last {{ border-top-left-radius: 10px; }}
            QTableCornerButton::section {{
                background-color: {Colors.BACKGROUND};
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 10px; margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER}; border-radius: 5px; min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {Colors.TEXT_DISABLED}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QScrollBar:horizontal {{
                background: transparent; height: 10px; margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {Colors.BORDER}; border-radius: 5px; min-width: 28px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: {Colors.TEXT_DISABLED}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
        """)


class Card(QFrame):
    """Generic white card container with border + soft shadow. Use as a wrapper for custom sections."""

    def __init__(self, padding: int = 18):
        super().__init__()
        self.setObjectName("GenericCard")
        self.setStyleSheet(f"""
            QFrame#GenericCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
            }}
        """)
        apply_soft_shadow(self, blur=16, y_offset=2, alpha=16)

        self.body_layout = QVBoxLayout(self)
        self.body_layout.setContentsMargins(padding, padding, padding, padding)
        self.body_layout.setSpacing(10)
