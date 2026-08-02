from src.utils.persian_utils import to_persian_digits


def test_convert_english_digits_to_persian():
    assert to_persian_digits(123) == "۱۲۳"
    assert to_persian_digits("Score: 95%") == "Score: ۹۵%"
    assert to_persian_digits(0) == "۰"


def test_already_persian_digits_unchanged():
    assert to_persian_digits("۱۲۳") == "۱۲۳"


def test_mixed_strings():
    assert to_persian_digits("Grade 10 - Math 20") == "Grade ۱۰ - Math ۲۰"
