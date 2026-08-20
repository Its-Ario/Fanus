import colorsys
import hashlib


def generate_profile_color(uuid: str) -> str:
    digest = hashlib.sha256(uuid.encode("utf-8")).digest()

    hue = int.from_bytes(digest[:2], "big") / 65535

    saturation = 0.65
    lightness = 0.55

    r, g, b = colorsys.hls_to_rgb(
        hue,
        lightness,
        saturation,
    )

    return "#{:02x}{:02x}{:02x}".format(
        round(r * 255),
        round(g * 255),
        round(b * 255),
    )
