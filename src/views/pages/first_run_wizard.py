import base64
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.auth import hash_password
from src.core.config import ConfigManager
from src.storage.db import DatabaseCredentials, configure_database_manager
from src.storage.models import SchoolProfile, User
from src.styles.app_style import APP_STYLE
from src.styles.theme import Colors
from src.utils.profile_color import generate_profile_color
from src.utils.validators import validate_academic_year, validate_username
from src.views.components.title_bar import TitleBar
from src.views.components.ui_kit import (
    Card,
    FormField,
    PrimaryButton,
    ProgressBar,
    SecondaryButton,
)


class FirstRunWizard(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(800, 700)
        self.setMinimumSize(760, 650)
        self.setStyleSheet(APP_STYLE)
        self._step = 0
        self.created_user = None

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
        outer.addWidget(TitleBar(self, title="راه اندازی فانوس"))

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

        self.setup_alert = QLabel()
        self.setup_alert.setObjectName("SetupAlert")
        self.setup_alert.setWordWrap(True)
        self.setup_alert.setStyleSheet(
            f"background-color: {Colors.ERROR_BG}; color: {Colors.ERROR}; border: 1px solid {Colors.ERROR}; border-radius: 8px; padding: 10px; font-size: 12px; font-weight: 600;"
        )
        self.setup_alert.setVisible(False)
        body_layout.addWidget(self.setup_alert)

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
        footer_label = QLabel("تنظیم اولیه فقط یک بار انجام می شود")
        footer_label.setObjectName("FooterText")
        footer_layout.addWidget(footer_label)
        footer_layout.addStretch()
        footer_layout.addWidget(QSizeGrip(footer))
        outer.addWidget(footer)

    def _page_shell(self, title, subtitle):
        card = Card(padding=26)
        card.body_layout.setSpacing(14)
        card.body_layout.setSizeConstraint(QLayout.SetMinimumSize)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        card.body_layout.addWidget(title_label)
        card.body_layout.addWidget(subtitle_label)
        card.body_layout.addSpacing(4)
        return card

    def _school_page(self):
        card = self._page_shell(
            "مدرسه تان را معرفی کنید", "این اطلاعات در سربرگ ها و گزارش ها استفاده می شود."
        )
        self.school_name = FormField("نام مدرسه", "برای مثال: علامه حلی ۳")
        self.academic_year = FormField("سال تحصیلی", "برای مثال: ۱۴۰۵–۱۴۰۶")
        card.body_layout.addWidget(self.school_name)
        card.body_layout.addWidget(self.academic_year)

        type_label = QLabel("مقطع های تحصیلی مدرسه")
        type_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};")
        card.body_layout.addWidget(type_label)

        type_hint = QLabel("یک یا چند مورد را انتخاب کنید")
        type_hint.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        card.body_layout.addWidget(type_hint)

        type_buttons_layout = QHBoxLayout()
        type_buttons_layout.setSpacing(8)
        self.school_type_buttons = {}
        for key, text in (
            ("elementry", "دبستان"),
            ("middle", "دوره اول دبیرستان (راهنمایی)"),
            ("high", "دوره دوم دبیرستان"),
        ):
            button = QCheckBox(text)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(38)
            button.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
            button.setStyleSheet(f"""
                QCheckBox {{ background: {Colors.SURFACE}; color: {Colors.TEXT_MUTED}; border: 1px solid {Colors.BORDER}; border-radius: 8px; font-size: 12px; font-weight: 600; padding: 0 10px; }}
                QCheckBox:hover {{ background: {Colors.SURFACE_HOVER}; color: {Colors.TEXT_MAIN}; }}
                QCheckBox:checked {{ background: {Colors.PRIMARY}18; color: {Colors.PRIMARY}; border: 1px solid {Colors.PRIMARY}; }}
                QCheckBox:focus {{ border: 2px solid {Colors.PRIMARY}; }}
                QCheckBox::indicator {{ width: 14px; height: 14px; }}
            """)
            button.toggled.connect(self._clear_school_type_error)
            self.school_type_buttons[key] = button
            type_buttons_layout.addWidget(button)
        card.body_layout.addLayout(type_buttons_layout)

        self.school_type_error = QLabel()
        self.school_type_error.setWordWrap(True)
        self.school_type_error.setStyleSheet(f"font-size: 11px; color: {Colors.ERROR};")
        self.school_type_error.setVisible(False)
        card.body_layout.addWidget(self.school_type_error)
        card.body_layout.addStretch()
        return self._centered_page(card)

    def _user_page(self):
        card = self._page_shell(
            "اولین کاربر را بسازید", "بعدا قادر به ساخت کاربر های دیگر خواهید بود"
        )
        self.full_name = FormField("نام و نام خانوادگی", "برای مثال: علی احمدی")
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
        for key, text in (
            ("counselor", "مشاور"),
            ("assistant", "معاون"),
            ("principal", "مدیر مدرسه"),
        ):
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

        self.role_description = QLabel()
        self.role_description.setWordWrap(True)
        self.role_description.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        card.body_layout.addWidget(self.role_description)
        self._refresh_role_description()
        card.body_layout.addStretch()
        return self._centered_page(card)

    def _security_page(self):
        card = self._page_shell(
            "امنیت حساب",
            "برای ورود، می توانید از رمز عبور استفاده کنید یا آن را فعلاً خالی بگذارید.",
        )
        self.review_summary = QLabel()
        self.review_summary.setWordWrap(True)
        self.review_summary.setStyleSheet(
            f"background-color: {Colors.SURFACE_HOVER}; color: {Colors.TEXT_MUTED}; border-radius: 8px; padding: 8px 10px; font-size: 11px; font-weight: 600;"
        )
        card.body_layout.addWidget(self.review_summary)
        self.password_enabled = QCheckBox("برای این حساب رمز ورود تعیین می کنم")
        self.password_enabled.setCursor(Qt.PointingHandCursor)
        self.password_enabled.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {Colors.TEXT_MAIN};"
        )
        self.password_enabled.toggled.connect(self._toggle_password_fields)
        card.body_layout.addWidget(self.password_enabled)

        password_help = QLabel("رمز ورود اختیاری است و از پین یادداشت های محرمانه جداست.")
        password_help.setWordWrap(True)
        password_help.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        card.body_layout.addWidget(password_help)

        self.password = FormField("رمز عبور", "حداقل ۸ نویسه", password=True, revealable=True)
        self.password_confirmation = FormField(
            "تکرار رمز عبور", "رمز عبور را دوباره وارد کنید", password=True, revealable=True
        )
        card.body_layout.addWidget(self.password)
        card.body_layout.addWidget(self.password_confirmation)

        self.vault_note = QLabel()
        self.vault_note.setWordWrap(True)
        self.vault_note.setStyleSheet(
            f"background-color: {Colors.AI_BG}; color: {Colors.AI_ACCENT}; border: 1px solid {Colors.AI_BORDER}; border-radius: 8px; padding: 10px; font-size: 12px; font-weight: 600;"
        )
        self.vault_pin = FormField(
            "عبارت عبور یادداشت های محرمانه",
            "حداقل ۱۲ کاراکتر و متفاوت از رمز ورود",
            password=True,
            revealable=True,
        )
        self.vault_acknowledgement = QCheckBox("می دانم پین فراموش شده قابل بازیابی نیست.")
        self.vault_acknowledgement.setCursor(Qt.PointingHandCursor)
        self.vault_acknowledgement.setStyleSheet(
            f"font-size: 11px; color: {Colors.TEXT_MAIN}; font-weight: 600;"
        )
        card.body_layout.addWidget(self.vault_note)
        card.body_layout.addWidget(self.vault_pin)
        card.body_layout.addWidget(self.vault_acknowledgement)
        card.body_layout.addStretch()
        self._toggle_password_fields(False)
        return self._centered_page(card)

    @staticmethod
    def _centered_page(card):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        layout.addWidget(card, alignment=Qt.AlignTop)
        return page

    def _selected_role(self):
        return next(key for key, button in self.role_buttons.items() if button.isChecked())

    def _refresh_role_description(self):
        descriptions = {
            "counselor": "مشاور: برای کار با یادداشت های محرمانه از یک پین اختصاصی استفاده می کند.",
            "assistant": "معاون: نقش اجرایی برای پیگیری امور مدرسه.",
            "principal": "مدیر مدرسه: نقش مدیریتی برای اداره مدرسه.",
        }
        self.role_description.setText(descriptions[self._selected_role()])

    def _refresh_review_summary(self):
        type_labels = {
            "elementry": "دبستان",
            "middle": "دوره اول",
            "high": "دوره دوم",
        }
        selected_types = "، ".join(type_labels[key] for key in self._selected_school_types())
        self.review_summary.setText(
            f"مرور اطلاعات: {self.school_name.text()} · {selected_types} · "
            f"{self.full_name.text()} ({self.role_buttons[self._selected_role()].text()})"
        )

    def _selected_school_types(self):
        return [key for key, button in self.school_type_buttons.items() if button.isChecked()]

    def _clear_school_type_error(self, *_):
        if self._selected_school_types():
            self.school_type_error.setVisible(False)
            self._refresh_layout()

    def _refresh_security_page(self, *_):
        self._refresh_role_description()
        is_counselor = self._selected_role() == "counselor"
        self.vault_note.setVisible(is_counselor)
        self.vault_pin.setVisible(is_counselor)
        self.vault_acknowledgement.setVisible(is_counselor)
        if is_counselor:
            self.vault_note.setText(
                "پین یادداشت های محرمانه برای مشاور الزامی است و با رمز ورود متفاوت است. آن را در جای امن نگه دارید."
            )
        self._refresh_layout()

    def _toggle_password_fields(self, enabled):
        self.password.setVisible(enabled)
        self.password_confirmation.setVisible(enabled)
        self._refresh_layout()

    def _refresh_layout(self):
        for index in range(self.pages.count()):
            page = self.pages.widget(index)
            if page.layout():
                page.layout().invalidate()
                page.layout().activate()
            page.updateGeometry()
        self.pages.updateGeometry()

    def _update_step(self):
        self.pages.setCurrentIndex(self._step)
        self.step_label.setText(f"مرحله {self._step + 1} از ۳")
        self.progress.set_value((self._step + 1) * 100 // 3)
        self.back_button.setVisible(self._step > 0)
        self.next_button.setText("اتمام راه اندازی" if self._step == 2 else "ادامه")
        if self._step == 2:
            self._refresh_review_summary()
            self._refresh_security_page()

    def _next(self):
        self.setup_alert.setVisible(False)
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
            fields = (
                (self.school_name, "نام مدرسه را وارد کنید."),
                (self.academic_year, "سال تحصیلی را وارد کنید."),
            )
        elif self._step == 1:
            fields = (
                (self.full_name, "نام و نام خانوادگی را وارد کنید."),
                (self.username, "نام کاربری را وارد کنید."),
            )
        else:
            if self.password_enabled.isChecked():
                fields = (
                    (self.password, "رمز عبور را وارد کنید."),
                    (self.password_confirmation, "تکرار رمز عبور را وارد کنید."),
                )
            if self._selected_role() == "counselor":
                fields += (
                    (self.vault_pin, "عبارت عبور یادداشت های محرمانه برای مشاور الزامی است."),
                )

        valid = True
        first_invalid = None
        for field, error in fields:
            field.clear_error()
            if not field.text():
                field.set_error(error)
                valid = False
                first_invalid = first_invalid or field
        if not valid:
            first_invalid.input.setFocus()
            return False
        if self._step == 0:
            if not (2 < len(self.school_name.text()) < 50):
                self.school_name.set_error("نام مدرسه باید بین ۲ تا ۵۰ حرف باشد")
                return False
            if not validate_academic_year(self.academic_year.text()):
                self.academic_year.set_error(
                    "سال تحصیلی را به شکل «۱۴۰۵-۱۴۰۶» وارد کنید؛ سال دوم باید دقیقاً یک سال بعد باشد."
                )
                self.academic_year.input.setFocus()
                return False
            if not self._selected_school_types():
                self.school_type_error.setText("حداقل یک مقطع تحصیلی را انتخاب کنید.")
                self.school_type_error.setVisible(True)
                self._refresh_layout()
                return False
        elif self._step == 1:
            if not (3 < len(self.username.text()) < 20):
                self.username.set_error("طول نام کاربری باید بین ۳ تا ۲۰ حرف باشد")
                return False
            if not validate_username(self.username.text()):
                self.username.set_error(
                    "نام کاربری معتبر نیست، لطفا از حروف و اعداد انگلیسی استفاده کنید."
                )
                self.username.input.setFocus()
                return False
        elif self._step == 2 and self.password_enabled.isChecked():
            if len(self.password.text()) < 8:
                self.password.set_error("رمز عبور باید دست کم ۸ نویسه باشد.")
                self.password.input.setFocus()
                return False
            if self.password.text() != self.password_confirmation.text():
                self.password_confirmation.set_error("دو رمز عبور یکسان نیستند.")
                self.password_confirmation.input.setFocus()
                return False
        if (
            self._step == 2
            and self._selected_role() == "counselor"
            and len(self.vault_pin.text()) < 12
        ):
            self.vault_pin.set_error("عبارت عبور یادداشت های محرمانه باید دست کم ۱۲ نویسه باشد.")
            self.vault_pin.input.setFocus()
            return False
        if (
            self._step == 2
            and self._selected_role() == "counselor"
            and not self.vault_acknowledgement.isChecked()
        ):
            self.vault_acknowledgement.setFocus()
            self.setup_alert.setText(
                "پیش از اتمام راه اندازی، پیام مربوط به بازیابی ناپذیری پین را تأیید کنید."
            )
            self.setup_alert.setVisible(True)
            return False
        return True

    def _complete_setup(self):
        role = self._selected_role()
        vault_pin = (
            self.vault_pin.text()
            if role == "counselor"
            else base64.b64encode(os.urandom(32)).decode("ascii")
        )
        try:
            credentials = DatabaseCredentials.from_vault_pin(vault_pin)
            manager = configure_database_manager(credentials)
            manager.initialize()
            with manager.transaction():
                SchoolProfile.insert(
                    id=1,
                    school_name=self.school_name.text(),
                    academic_year=self.academic_year.text(),
                    type=",".join(self._selected_school_types()),
                    school_start_time="07:30",
                    school_end_time="13:30",
                ).on_conflict(
                    conflict_target=[SchoolProfile.id],
                    update={
                        SchoolProfile.school_name: self.school_name.text(),
                        SchoolProfile.academic_year: self.academic_year.text(),
                        SchoolProfile.type: ",".join(self._selected_school_types()),
                        SchoolProfile.school_start_time: "07:30",
                        SchoolProfile.school_end_time: "13:30",
                    },
                ).execute()
                self.created_user = User.create(
                    username=self.username.text(),
                    password_hash=hash_password(self.password.text())
                    if self.password_enabled.isChecked()
                    else None,
                    full_name=self.full_name.text(),
                    role=role,
                    avatar_color=generate_profile_color(self.username.text()),
                    can_manage_users=True,
                )
            if not ConfigManager.mark_configured():
                raise RuntimeError("پیکربندی برنامه ذخیره نشد.")
        except Exception as exc:
            self.created_user = None
            self._show_error(self._friendly_error(exc))
            return
        self.accept()

    def _show_error(self, message):
        self.setup_alert.setText(message)
        self.setup_alert.setVisible(True)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._next()
            event.accept()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _friendly_error(exc):
        if "UNIQUE constraint failed: user.username" in str(exc):
            return "این نام کاربری قبلاً استفاده شده است. نام دیگری انتخاب کنید."
        return "راه اندازی کامل نشد. لطفاً دوباره تلاش کنید."
