_EN_TO_FA_MAP = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def to_persian_digits(value) -> str:
    return str(value).translate(_EN_TO_FA_MAP)


def to_ascii_digits(value) -> str:
    return str(value).translate(_FA_TO_EN)
