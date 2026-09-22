import logging
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from src.core.config import ConfigManager
from src.core.logger import setup_logging
from src.storage import backup_ops
from src.storage.db import DatabaseError, configure_database_manager, get_database_manager
from src.storage.models import User
from src.styles.theme import MODERN_STYLE
from src.views.main_window import MainWindow
from src.views.pages.first_run_wizard import FirstRunWizard
from src.views.pages.login_dialog import LoginDialog

logger = logging.getLogger(__name__)

APP_NAME = "Fanus"
APP_DISPLAY_NAME = "فانوس"
APP_USER_MODEL_ID = "ir.itsario.fanus"


def _app_asset_path(filename: str) -> Path:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir / "assets" / filename


def _set_windows_app_identity():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        logger.debug("Windows application identity could not be set.", exc_info=True)


def main():
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setOrganizationName(APP_NAME)
    _set_windows_app_identity()

    font_id = QFontDatabase.addApplicationFont(str(_app_asset_path("fonts/Vazir.ttf")))
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
    else:
        logger.warning("Could not load Vazir font. Using system default.")

    app.setLayoutDirection(Qt.RightToLeft)

    app.setStyleSheet(MODERN_STYLE)

    config = ConfigManager.load()
    backup_ops.heal_interrupted_restore()
    current_user = None
    if not config.is_configured:
        wizard = FirstRunWizard()
        if wizard.exec_() != QDialog.Accepted:
            logger.info("Initial setup was not completed.")
            return
        current_user = wizard.created_user
        if current_user is None:
            logger.error("Initial setup completed without creating a user.")
            return
        logger.info("Wizard completed successfully!")
    else:
        try:
            manager = configure_database_manager()
            manager.initialize_public()
            users = list(User.select().where(User.is_active).order_by(User.full_name))
        except DatabaseError:
            QMessageBox.critical(
                None,
                "ورود به فانوس ممکن نیست",
                "داده های برنامه باز نشدند. لطفا از نسخه معتبر استفاده کنید.",
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

    app.aboutToQuit.connect(get_database_manager().close)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
