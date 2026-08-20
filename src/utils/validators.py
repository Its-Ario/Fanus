import re


def validate_username(username: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9]{3,20}", username))


def validate_academic_year(value: str) -> bool:
    if not re.fullmatch(r"[1۱][0-9۰-۹]{3}-[1۱][0-9۰-۹]{3}", value):
        return False

    num1, num2 = value.split("-")

    num1 = int(num1.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    num2 = int(num2.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))

    return num1 + 1 == num2
