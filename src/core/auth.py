from __future__ import annotations

import base64
import hashlib
import hmac
import os

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return "{}${}${}${}".format(
        PASSWORD_ALGORITHM,
        PASSWORD_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded_hash: str | None) -> bool:
    if not password or not encoded_hash:
        return False

    try:
        algorithm, iterations, salt_value, expected_digest = encoded_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iteration_count = int(iterations)
        if iteration_count <= 0:
            return False
        salt = base64.b64decode(salt_value, validate=True)
        expected = base64.b64decode(expected_digest, validate=True)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iteration_count
        )
    except (TypeError, ValueError, UnicodeEncodeError):
        return False

    return hmac.compare_digest(actual, expected)
