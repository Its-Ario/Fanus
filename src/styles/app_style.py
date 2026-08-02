from src.styles.theme import Colors

APP_STYLE = f"""
/* ================= ROOT WINDOW ================= */
QWidget#CentralWrapper {{
    background-color: {Colors.SURFACE};
    border-radius: 8px;
    border: 1px solid {Colors.BORDER};
}}

/* ================= CUSTOM TITLE BAR ================= */
QFrame#TitleBar {{
    background-color: {Colors.SURFACE};
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border-bottom: 1px solid {Colors.BORDER};
}}

QLabel#AppTitle {{
    color: {Colors.TEXT_MAIN};
    font-size: 13px;
    font-weight: 700;
}}

/* Window Control Buttons (Minimize/Maximize/Close) */
QPushButton.WindowBtn {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: {Colors.TEXT_MUTED};
    font-size: 13px;
}}
QPushButton.WindowBtn:hover {{
    background-color: {Colors.SURFACE_HOVER};
}}
QPushButton#CloseBtn:hover {{
    background-color: {Colors.ERROR};
    color: white;
}}

/* ================= SIDEBAR ================= */
QFrame#Sidebar {{
    background-color: {Colors.BACKGROUND};
    border-left: 1px solid {Colors.BORDER};
}}

QPushButton.NavItem {{
    text-align: left;
    padding-left: 12px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    color: {Colors.TEXT_MUTED};
    background-color: transparent;
}}
QPushButton.NavItem:hover {{
    background-color: {Colors.SURFACE_HOVER};
    color: {Colors.TEXT_MAIN};
}}
QPushButton.NavItem:checked {{
    background-color: {Colors.PRIMARY}18;
    color: {Colors.PRIMARY};
}}

QPushButton#ToggleBtn {{
    background-color: transparent;
    border: none;
    color: {Colors.TEXT_MUTED};
    font-size: 16px;
    border-radius: 8px;
}}
QPushButton#ToggleBtn:hover {{
    background-color: {Colors.SURFACE_HOVER};
}}

/* ================= FOOTER / CREDITS BAR ================= */
QFrame#Footer {{
    background-color: {Colors.BACKGROUND};
    border-top: 1px solid {Colors.BORDER};
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
}}
QLabel#FooterText {{
    color: {Colors.TEXT_DISABLED};
    font-size: 11px;
}}

/* ================= CONTENT PAGES ================= */
QStackedWidget#Pages {{
    background-color: {Colors.BACKGROUND};
}}
"""
