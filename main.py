import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication

from src.styles.theme import MODERN_STYLE
from src.views.main_window import MainWindow


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

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
