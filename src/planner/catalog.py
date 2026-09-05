from __future__ import annotations

import re

from src.storage.models import AcademicMajor

DEFAULT_BLOCK_MINUTES = 90
COMPRESSED_BLOCK_MINUTES = 75
HALF_BLOCK_MINUTES = 45
MIN_BREAK_MINUTES = 15

DEFAULT_SLEEP_WINDOW = ("23:30", "06:30")
MIN_SLEEP_HOURS = 7.0
DEFAULT_SCHOOL_DAYS = (0, 1, 2, 3, 4)

MEAL_WINDOWS = (("13:30", "14:30"), ("20:30", "21:15"))

DAY_THURSDAY = 5
DAY_FRIDAY = 6
FRIDAY_MOCK_WINDOW = ("08:00", "12:00")
FRIDAY_BUFFER_WINDOW = ("17:00", "20:00")

MAX_BLOCKS_SCHOOL = 4
MAX_BLOCKS_THURSDAY = 5
MAX_BLOCKS_OFF = 6

DISTINCT_ALLOWED_SCHOOL = (2, 3)
DISTINCT_ALLOWED_OFF = (3, 4)

S4_LIMIT = 2.0
S4_MIN_GAP_HOURS = 48
S4_MAX_GAP_HOURS = 72

SLOT_LABELS = ("PEAK_1", "PEAK_2", "SECONDARY", "FINAL")
PREFERRED_SLOTS = {
    "calc": ("PEAK_1", "PEAK_2"),
    "descriptive": ("SECONDARY", "PEAK_2"),
    "light": ("FINAL", "SECONDARY"),
}

DEFAULT_SOFT_WEIGHTS = {"s1": 40, "s2": 30, "s3": 20, "s4": 100, "s5": 10}

_DIGIT_TAIL = re.compile(r"[\s‌]+[0-9۰-۹٠-٩]+$")

_FAMILY_MATCHERS = (
    ("حسابان", "ریاضی"),
    ("هندسه", "ریاضی"),
    ("گسسته", "ریاضی"),
    ("ریاضی و آمار", "ریاضی"),
    ("آمار و احتمال", "ریاضی"),
    ("ریاضی", "ریاضی"),
    ("فیزیک", "فیزیک"),
    ("شیمی", "شیمی"),
    ("انسان و محیط زیست", "انسان و محیط زیست"),
    ("زیست", "زیست‌شناسی"),
    ("زمین‌شناسی", "زمین‌شناسی"),
    ("آزمایشگاه", "آزمایشگاه علوم"),
    ("فارسی", "فارسی و نگارش"),
    ("نگارش", "فارسی و نگارش"),
    ("علوم و فنون ادبی", "علوم و فنون ادبی"),
    ("عربی", "عربی"),
    ("دین و زندگی", "دین و زندگی"),
    ("پیام‌های آسمان", "دین و زندگی"),
    ("هدیه‌های آسمان", "دین و زندگی"),
    ("قرآن", "دین و زندگی"),
    ("انگلیسی", "انگلیسی"),
    ("جامعه‌شناسی", "جامعه‌شناسی"),
    ("تاریخ معاصر", "تاریخ"),
    ("تاریخ", "تاریخ"),
    ("جغرافیا", "جغرافیا"),
    ("فلسفه", "فلسفه"),
    ("منطق", "منطق"),
    ("روان‌شناسی", "روان‌شناسی"),
    ("اقتصاد", "اقتصاد"),
    ("آمادگی دفاعی", "عمومی سبک"),
    ("سلامت و بهداشت", "عمومی سبک"),
    ("هویت اجتماعی", "عمومی سبک"),
    ("مدیریت خانواده", "عمومی سبک"),
    ("تفکر", "عمومی سبک"),
    ("سواد رسانه", "عمومی سبک"),
    ("کار و فناوری", "عمومی سبک"),
    ("کار و فن", "عمومی سبک"),
    ("فرهنگ و هنر", "عمومی سبک"),
    ("هنر", "عمومی سبک"),
)

_TYPE_BY_FAMILY = {
    "ریاضی": "calc",
    "فیزیک": "calc",
    "شیمی": "calc",
    "زیست‌شناسی": "calc",
    "اقتصاد": "calc",
    "فارسی و نگارش": "descriptive",
    "علوم و فنون ادبی": "descriptive",
    "عربی": "descriptive",
    "دین و زندگی": "descriptive",
    "انگلیسی": "descriptive",
    "جامعه‌شناسی": "descriptive",
    "تاریخ": "descriptive",
    "جغرافیا": "descriptive",
    "فلسفه": "descriptive",
    "منطق": "descriptive",
    "روان‌شناسی": "descriptive",
    "زمین‌شناسی": "descriptive",
    "انسان و محیط زیست": "descriptive",
    "آزمایشگاه علوم": "light",
    "عمومی سبک": "light",
}

_COEFF_BASE = {
    "ریاضی": 8,
    "فیزیک": 8,
    "شیمی": 8,
    "زیست‌شناسی": 6,
    "فارسی و نگارش": 4,
    "علوم و فنون ادبی": 4,
    "عربی": 2,
    "دین و زندگی": 3,
    "انگلیسی": 2,
    "جامعه‌شناسی": 3,
    "تاریخ": 3,
    "جغرافیا": 3,
    "فلسفه": 3,
    "منطق": 2,
    "روان‌شناسی": 3,
    "اقتصاد": 3,
    "زمین‌شناسی": 1,
    "انسان و محیط زیست": 1,
    "آزمایشگاه علوم": 1,
    "عمومی سبک": 1,
}

_COEFF_BY_MAJOR = {
    (AcademicMajor.MATH, "ریاضی"): 12,
    (AcademicMajor.MATH, "فیزیک"): 12,
    (AcademicMajor.MATH, "شیمی"): 6,
    (AcademicMajor.EXPERIMENTAL, "زیست‌شناسی"): 12,
    (AcademicMajor.EXPERIMENTAL, "شیمی"): 9,
    (AcademicMajor.EXPERIMENTAL, "فیزیک"): 8,
    (AcademicMajor.EXPERIMENTAL, "ریاضی"): 7,
    (AcademicMajor.HUMANITIES, "ریاضی"): 4,
    (AcademicMajor.HUMANITIES, "علوم و فنون ادبی"): 6,
    (AcademicMajor.HUMANITIES, "عربی"): 4,
    (AcademicMajor.HUMANITIES, "دین و زندگی"): 4,
    (AcademicMajor.HUMANITIES, "انگلیسی"): 3,
    (AcademicMajor.HUMANITIES, "جامعه‌شناسی"): 4,
}

_DEFAULT_COEFF = 1


def subject_family(name: str) -> str:
    cleaned = _DIGIT_TAIL.sub("", (name or "").strip()).strip()
    for needle, family in _FAMILY_MATCHERS:
        if needle in cleaned:
            return family
    return cleaned


def type_for(name: str) -> str:
    return _TYPE_BY_FAMILY.get(subject_family(name), "descriptive")


def coefficient_for(name: str, major: str = AcademicMajor.GENERAL) -> int:
    family = subject_family(name)
    if (major, family) in _COEFF_BY_MAJOR:
        return _COEFF_BY_MAJOR[(major, family)]
    return _COEFF_BASE.get(family, _DEFAULT_COEFF)
