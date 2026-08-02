_EN_TO_FA_MAP = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(value) -> str:
    """Converts any number or string containing numbers into Persian digits."""
    return str(value).translate(_EN_TO_FA_MAP)
