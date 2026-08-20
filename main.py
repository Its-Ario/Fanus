import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from src.core.config import ConfigManager
from src.storage.db import DatabaseError, configure_database_manager
from src.storage.models import User
from src.styles.theme import MODERN_STYLE
from src.views.main_window import MainWindow
from src.views.pages.first_run_wizard import FirstRunWizard
from src.views.pages.login_dialog import LoginDialog


def main():
    app = QApplication(sys.argv)

    font_id = QFontDatabase.addApplicationFont("assets/fonts/Vazir.ttf")
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
    else:
        print("Warning: Could not load Vazir font. Using system default.")

    app.setLayoutDirection(Qt.RightToLeft)

    app.setStyleSheet(MODERN_STYLE)

    config = ConfigManager.load()
    current_user = None
    if not config.is_configured:
        wizard = FirstRunWizard()
        if wizard.exec_() != QDialog.Accepted:
            print("❌ Initial setup was not completed.")
            return
        print("✅ Wizard completed successfully!")
    else:
        try:
            manager = configure_database_manager()
            manager.initialize_public()
            users = list(
                User.select()
                .where(User.is_active)
                .order_by(User.full_name)
            )
        except DatabaseError:
            QMessageBox.critical(
                None,
                "ورود به فانوس ممکن نیست",
                "داده‌های برنامه باز نشدند. لطفا از نسخه معتبر استفاده کنید.",
            )
            return

        if not users:
            QMessageBox.critical(
                None,
                "حساب فعالی وجود ندارد",
                "تنظیمات برنامه کامل است، اما هیچ حساب فعالی برای ورود پیدا نشد.",
            )
            return

        login = LoginDialog(users)
        if login.exec_() != QDialog.Accepted:
            return
        current_user = login.authenticated_user

    window = MainWindow(current_user=current_user)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
