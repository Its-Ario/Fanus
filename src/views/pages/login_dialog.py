from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.auth import verify_password
from src.styles.app_style import APP_STYLE
from src.styles.theme import Colors
from src.views.components.title_bar import TitleBar
from src.views.components.ui_kit import Avatar, Card, FormField, PrimaryButton

ROLE_LABELS = {
    "counselor": "مشاور",
    "assistant": "معاون",
    "principal": "مدیر مدرسه",
}


class AccountChoice(QFrame):

    def __init__(self, user, on_choose):
        super().__init__()
        self.user = user
        self._on_choose = on_choose
        self.setObjectName("AccountChoice")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedHeight(68)
        self.setStyleSheet(f"""
            QFrame#AccountChoice {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
            QFrame#AccountChoice:hover, QFrame#AccountChoice:focus {{
                background-color: {Colors.SURFACE_HOVER};
                border: 1.5px solid {Colors.PRIMARY};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        layout.addWidget(Avatar(user.full_name, size=42, color=user.avatar_color))

        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(user.full_name)
        name.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {Colors.TEXT_MAIN};")
        role = QLabel(ROLE_LABELS.get(user.role, user.role))
        role.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        text.addWidget(name)
        text.addWidget(role)
        layout.addLayout(text, stretch=1)

        indicator = QLabel("‹")
        indicator.setStyleSheet(f"font-size: 24px; color: {Colors.TEXT_DISABLED};")
        layout.addWidget(indicator)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_choose(self.user)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._on_choose(self.user)
            event.accept()
            return
        super().keyPressEvent(event)


class LoginDialog(QDialog):

    def __init__(self, users, parent=None):
        super().__init__(parent)
        self._users = list(users)
        self._authenticated_user = None
        self._selected_user = None

        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(560, 510)
        self.setMinimumSize(500, 430)
        self.setStyleSheet(APP_STYLE)
        self._build_ui()

    @property
    def authenticated_user(self):
        return self._authenticated_user

    def _build_ui(self):
        wrapper = QWidget()
        wrapper.setObjectName("CentralWrapper")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(wrapper)

        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self, title="ورود به فانوس"))

        body = QWidget()
        body.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(48, 34, 48, 28)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("QStackedWidget { background: transparent; }")
        self.pages.addWidget(self._account_page())
        self.pages.addWidget(self._password_page())
        body_layout.addWidget(self.pages)
        outer.addWidget(body, stretch=1)

        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setFixedHeight(30)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 0, 10, 0)
        footer_label = QLabel("حساب خود را برای ورود انتخاب کنید")
        footer_label.setObjectName("FooterText")
        footer_layout.addWidget(footer_label)
        footer_layout.addStretch()
        footer_layout.addWidget(QSizeGrip(footer))
        outer.addWidget(footer)

    def _page_shell(self, title, subtitle):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        card = Card(padding=24)
        card.body_layout.setSpacing(14)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        heading = QLabel(title)
        heading.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        description = QLabel(subtitle)
        description.setWordWrap(True)
        description.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
        card.body_layout.addWidget(heading)
        card.body_layout.addWidget(description)
        layout.addWidget(card)
        return page, card

    def _account_page(self):
        page, card = self._page_shell(
            "انتخاب حساب", "برای ادامه، یکی از حساب های فعال را انتخاب کنید."
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        for user in self._users:
            list_layout.addWidget(AccountChoice(user, self._choose_account))
        list_layout.addStretch()
        scroll.setWidget(list_widget)
        card.body_layout.addWidget(scroll)
        return page

    def _password_page(self):
        page, self.password_card = self._page_shell("رمز عبور", "")
        self.selected_account = QLabel()
        self.selected_account.setStyleSheet(
            f"background-color: {Colors.SURFACE_HOVER}; color: {Colors.TEXT_MAIN}; "
            "border-radius: 8px; padding: 9px 11px; font-size: 12px; font-weight: 700;"
        )
        self.password_field = FormField(
            "رمز عبور", "رمز عبور را وارد کنید", password=True, revealable=True
        )
        self.password_field.input.returnPressed.connect(self._submit_password)
        self.password_button = PrimaryButton("ورود")
        self.password_button.clicked.connect(self._submit_password)
        self.password_card.body_layout.addWidget(self.selected_account)
        self.password_card.body_layout.addWidget(self.password_field)
        self.password_card.body_layout.addWidget(self.password_button, alignment=Qt.AlignLeft)
        self.password_card.body_layout.addStretch()
        return page

    def _choose_account(self, user):
        self._selected_user = user
        if not user.password_hash:
            self._authenticate(user)
            return

        self.selected_account.setText(f"{user.full_name} · {ROLE_LABELS.get(user.role, user.role)}")
        self.password_field.input.clear()
        self.password_field.clear_error()
        self.pages.setCurrentIndex(1)
        self.password_field.input.setFocus()

    def _submit_password(self):
        if self._selected_user is None:
            return
        if not verify_password(self.password_field.text(), self._selected_user.password_hash):
            self.password_field.set_error("رمز عبور صحیح نیست. دوباره تلاش کنید.")
            self.password_field.input.setFocus()
            self.password_field.input.selectAll()
            return
        self._authenticate(self._selected_user)

    def _authenticate(self, user):
        user.last_login = datetime.now()
        user.save()
        self._authenticated_user = user
        self.accept()
