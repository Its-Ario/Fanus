import re

from src.utils.persian_utils import to_ascii_digits


def validate_username(username: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9]{3,20}", username))


def validate_academic_year(value: str) -> bool:
    if not re.fullmatch(r"[1۱][0-9۰-۹]{3}-[1۱][0-9۰-۹]{3}", value):
        return False

    num1, num2 = value.split("-")

    num1 = int(to_ascii_digits(num1))
    num2 = int(to_ascii_digits(num2))

    return num1 + 1 == num2
