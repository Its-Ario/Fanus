"""First-run setup dialog for establishing the first Fanus workspace."""

import base64
import hashlib
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config import ConfigManager
from src.storage.db import DatabaseCredentials, configure_database_manager
from src.storage.models import SchoolProfile, User
from src.styles.app_style import APP_STYLE
from src.styles.theme import Colors
from src.views.components.title_bar import TitleBar
from src.views.components.ui_kit import (
    Card,
    FormField,
    PrimaryButton,
    ProgressBar,
    SecondaryButton,
)


class FirstRunWizard(QDialog):
    """Three focused steps that create the initial school and administrator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(760, 590)
        self.setMinimumSize(680, 540)
        self.setStyleSheet(APP_STYLE)
        self._step = 0

        self._build_ui()
        self._update_step()

    def _build_ui(self):
        wrapper = QWidget()
        wrapper.setObjectName("CentralWrapper")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(wrapper)

        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self, title="راه‌اندازی فانوس"))

        body = QWidget()
        body.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(84, 38, 84, 28)
        body_layout.setSpacing(16)

        self.step_label = QLabel()
        self.step_label.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {Colors.PRIMARY};"
        )
        body_layout.addWidget(self.step_label)

        self.progress = ProgressBar()
        body_layout.addWidget(self.progress)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("QStackedWidget { background: transparent; }")
        self.pages.addWidget(self._school_page())
        self.pages.addWidget(self._user_page())
        self.pages.addWidget(self._security_page())
        body_layout.addWidget(self.pages, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.cancel_button = SecondaryButton("انصراف")
        self.cancel_button.clicked.connect(self.reject)
        self.back_button = SecondaryButton("مرحله قبل")
        self.back_button.clicked.connect(self._back)
        self.next_button = PrimaryButton("ادامه")
        self.next_button.clicked.connect(self._next)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.back_button)
        actions.addWidget(self.next_button)
        body_layout.addLayout(actions)

        outer.addWidget(body, stretch=1)

        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setFixedHeight(30)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 0, 10, 0)
        footer_label = QLabel("تنظیم اولیه فقط یک‌بار انجام می‌شود")
        footer_label.setObjectName("FooterText")
        footer_layout.addWidget(footer_label)
        footer_layout.addStretch()
        footer_layout.addWidget(QSizeGrip(footer))
        outer.addWidget(footer)

    def _page_shell(self, title, subtitle):
        card = Card(padding=26)
        card.body_layout.setSpacing(14)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};"
        )
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        card.body_layout.addWidget(title_label)
        card.body_layout.addWidget(subtitle_label)
        card.body_layout.addSpacing(4)
        return card

    def _school_page(self):
        card = self._page_shell("مدرسه‌تان را معرفی کنید", "این اطلاعات در سربرگ‌ها و گزارش‌ها استفاده می‌شود.")
        self.school_name = FormField("نام مدرسه", "برای مثال: دبیرستان فرهنگ")
        self.academic_year = FormField("سال تحصیلی", "برای مثال: ۱۴۰۵–۱۴۰۶")
        card.body_layout.addWidget(self.school_name)
        card.body_layout.addWidget(self.academic_year)
        card.body_layout.addStretch()
        return self._centered_page(card)

    def _user_page(self):
        card = self._page_shell("اولین کاربر را بسازید", "این حساب به همهٔ بخش‌های مدیریتی فانوس دسترسی خواهد داشت.")
        self.full_name = FormField("نام و نام خانوادگی", "برای مثال: نرگس احمدی")
        self.username = FormField("نام کاربری", "برای ورود به برنامه")
        card.body_layout.addWidget(self.full_name)
        card.body_layout.addWidget(self.username)

        role_label = QLabel("نقش کاربر")
        role_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};")
        card.body_layout.addWidget(role_label)
        roles = QHBoxLayout()
        roles.setSpacing(8)
        self.role_group = QButtonGroup(self)
        self.role_group.setExclusive(True)
        self.role_buttons = {}
        for key, text in (("counselor", "مشاور"), ("assistant", "معاون"), ("principal", "مدیر مدرسه")):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(38)
            button.setStyleSheet(f"""
                QPushButton {{ background: {Colors.SURFACE}; color: {Colors.TEXT_MUTED}; border: 1px solid {Colors.BORDER}; border-radius: 8px; font-size: 12px; font-weight: 600; }}
                QPushButton:hover {{ background: {Colors.SURFACE_HOVER}; color: {Colors.TEXT_MAIN}; }}
                QPushButton:checked {{ background: {Colors.PRIMARY}18; color: {Colors.PRIMARY}; border: 1px solid {Colors.PRIMARY}; }}
            """)
            self.role_group.addButton(button)
            self.role_buttons[key] = button
            roles.addWidget(button)
        self.role_buttons["counselor"].setChecked(True)
        self.role_group.buttonClicked.connect(self._refresh_security_page)
        card.body_layout.addLayout(roles)
        card.body_layout.addStretch()
        return self._centered_page(card)

    def _security_page(self):
        card = self._page_shell("امنیت حساب", "برای ورود، می‌توانید از رمز عبور استفاده کنید یا آن را فعلاً خالی بگذارید.")
        self.password_enabled = QCheckBox("برای این حساب رمز ورود تعیین می‌کنم")
        self.password_enabled.setCursor(Qt.PointingHandCursor)
        self.password_enabled.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Colors.TEXT_MAIN};")
        self.password_enabled.toggled.connect(self._toggle_password_fields)
        card.body_layout.addWidget(self.password_enabled)

        self.password = FormField("رمز عبور", "حداقل ۸ نویسه", password=True)
        self.password_confirmation = FormField("تکرار رمز عبور", "رمز عبور را دوباره وارد کنید", password=True)
        card.body_layout.addWidget(self.password)
        card.body_layout.addWidget(self.password_confirmation)

        self.vault_note = QLabel()
        self.vault_note.setWordWrap(True)
        self.vault_note.setStyleSheet(
            f"background-color: {Colors.AI_BG}; color: {Colors.AI_ACCENT}; border: 1px solid {Colors.AI_BORDER}; border-radius: 8px; padding: 10px; font-size: 12px; font-weight: 600;"
        )
        self.vault_pin = FormField("پین گاوصندوق", "یک پین جداگانه برای یادداشت‌های محرمانه", password=True)
        card.body_layout.addWidget(self.vault_note)
        card.body_layout.addWidget(self.vault_pin)
        card.body_layout.addStretch()
        self._toggle_password_fields(False)
        return self._centered_page(card)

    @staticmethod
    def _centered_page(card):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _selected_role(self):
        return next(key for key, button in self.role_buttons.items() if button.isChecked())

    def _refresh_security_page(self, *_):
        is_counselor = self._selected_role() == "counselor"
        self.vault_note.setVisible(is_counselor)
        self.vault_pin.setVisible(is_counselor)
        if is_counselor:
            self.vault_note.setText("پین گاوصندوق برای مشاور الزامی است و با رمز ورود متفاوت است. آن را در جای امن نگه دارید.")

    def _toggle_password_fields(self, enabled):
        self.password.setVisible(enabled)
        self.password_confirmation.setVisible(enabled)

    def _update_step(self):
        self.pages.setCurrentIndex(self._step)
        self.step_label.setText(f"مرحله {self._step + 1} از ۳")
        self.progress.set_value((self._step + 1) * 100 // 3)
        self.back_button.setVisible(self._step > 0)
        self.next_button.setText("اتمام راه‌اندازی" if self._step == 2 else "ادامه")
        if self._step == 2:
            self._refresh_security_page()

    def _next(self):
        if not self._validate_current_step():
            return
        if self._step < 2:
            self._step += 1
            self._update_step()
            return
        self._complete_setup()

    def _back(self):
        if self._step:
            self._step -= 1
            self._update_step()

    def _validate_current_step(self):
        fields = []
        if self._step == 0:
            fields = ((self.school_name, "نام مدرسه را وارد کنید."), (self.academic_year, "سال تحصیلی را وارد کنید."))
        elif self._step == 1:
            fields = ((self.full_name, "نام و نام خانوادگی را وارد کنید."), (self.username, "نام کاربری را وارد کنید."))
        else:
            if self.password_enabled.isChecked():
                fields = ((self.password, "رمز عبور را وارد کنید."), (self.password_confirmation, "تکرار رمز عبور را وارد کنید."))
            if self._selected_role() == "counselor":
                fields += ((self.vault_pin, "پین گاوصندوق برای مشاور الزامی است."),)

        valid = True
        for field, error in fields:
            field.clear_error()
            if not field.text():
                field.set_error(error)
                valid = False
        if not valid:
            return False
        if self._step == 2 and self.password_enabled.isChecked():
            if len(self.password.text()) < 8:
                self.password.set_error("رمز عبور باید دست‌کم ۸ نویسه باشد.")
                return False
            if self.password.text() != self.password_confirmation.text():
                self.password_confirmation.set_error("دو رمز عبور یکسان نیستند.")
                return False
        return True

    def _complete_setup(self):
        role = self._selected_role()
        # The vault database always needs a key. Non-counselor accounts never use it,
        # so their first-run key is random and only lives for this application session.
        vault_pin = self.vault_pin.text() if role == "counselor" else base64.b64encode(os.urandom(32)).decode("ascii")
        try:
            credentials = DatabaseCredentials.from_vault_pin(vault_pin)
            manager = configure_database_manager(credentials)
            manager.initialize()
            with manager.transaction():
                SchoolProfile.insert(
                    id=1,
                    school_name=self.school_name.text(),
                    academic_year=self.academic_year.text(),
                ).on_conflict(
                    conflict_target=[SchoolProfile.id],
                    update={
                        SchoolProfile.school_name: self.school_name.text(),
                        SchoolProfile.academic_year: self.academic_year.text(),
                    },
                ).execute()
                User.create(
                    username=self.username.text(),
                    password_hash=self._password_hash(self.password.text()) if self.password_enabled.isChecked() else None,
                    full_name=self.full_name.text(),
                    role=role,
                    can_manage_users=True,
                )
            if not ConfigManager.mark_configured():
                raise RuntimeError("پیکربندی برنامه ذخیره نشد.")
        except Exception as exc:
            self._show_error(self._friendly_error(exc))
            return
        self.accept()

    @staticmethod
    def _password_hash(password):
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
        return "pbkdf2_sha256$600000${}${}".format(
            base64.b64encode(salt).decode("ascii"), base64.b64encode(digest).decode("ascii")
        )

    def _show_error(self, message):
        self.vault_note.setText(message)
        self.vault_note.setStyleSheet(
            f"background-color: {Colors.ERROR_BG}; color: {Colors.ERROR}; border: 1px solid {Colors.ERROR}; border-radius: 8px; padding: 10px; font-size: 12px; font-weight: 600;"
        )
        self.vault_note.setVisible(True)

    @staticmethod
    def _friendly_error(exc):
        if "UNIQUE constraint failed: user.username" in str(exc):
            return "این نام کاربری قبلاً استفاده شده است. نام دیگری انتخاب کنید."
        return "راه‌اندازی کامل نشد. لطفاً دوباره تلاش کنید."
