class Colors:
    # Primary (Teal)
    PRIMARY = "#0D9488"
    PRIMARY_HOVER = "#115E59"
    PRIMARY_ACTIVE = "#0F766E"

    # AI Accent (Purple)
    AI_ACCENT = "#7C3AED"
    AI_BG = "#F5F3FF"
    AI_BORDER = "#DDD6FE"

    # Status & Alerts
    SUCCESS = "#047857"
    SUCCESS_BG = "#D1FAE5"
    WARNING = "#B45309"
    WARNING_BG = "#FEF3C7"
    ERROR = "#B91C1C"
    ERROR_BG = "#FEE2E2"

    # Surfaces
    BACKGROUND = "#F8FAFC"
    SURFACE = "#FFFFFF"
    SURFACE_HOVER = "#F1F5F9"
    BORDER = "#E2E8F0"

    # Text
    TEXT_MAIN = "#0F172A"
    TEXT_MUTED = "#475569"
    TEXT_DISABLED = "#94A3B8"


MODERN_STYLE = f"""
QMainWindow, QDialog {{
    background-color: {Colors.BACKGROUND};
    font-family: 'Vazirmatn', 'Tahoma', sans-serif;
}}

QFrame#Card {{
    background-color: {Colors.SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
}}

QFrame#AICard {{
    background-color: {Colors.AI_BG};
    border: 1px solid {Colors.AI_BORDER};
    border-radius: 8px;
}}

QPushButton#PrimaryButton {{
    background-color: {Colors.PRIMARY};
    color: #FFFFFF;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px 16px;
    border: none;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {Colors.PRIMARY_HOVER};
}}

QPushButton#PrimaryButton:pressed {{
    background-color: {Colors.PRIMARY_ACTIVE};
}}

QLabel#BadgeHighRisk {{
    background-color: {Colors.ERROR_BG};
    color: {Colors.ERROR};
    font-weight: bold;
    padding: 4px 8px;
    border-radius: 4px;
}}

QLabel#BadgeBurnoutAI {{
    background-color: {Colors.AI_BG};
    color: {Colors.AI_ACCENT};
    font-weight: bold;
    padding: 4px 8px;
    border: 1px solid {Colors.AI_BORDER};
    border-radius: 4px;
}}
"""
