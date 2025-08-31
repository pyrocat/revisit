from typing import Any, Dict, Optional, Tuple
from PIL import Image
import pillow_heif  # enables HEIC in Pillow
import exifread
from datetime import datetime
from fractions import Fraction

# Ensure HEIF opener is registered
pillow_heif.register_heif_opener()


def _to_deg(value):
    """
    Convert exifread GPSTags like [deg, min, sec] rationals to float degrees.
    """
    d, m, s = value.values

    def f(x):
        if isinstance(x, Fraction):
            return float(x)
        return float(x.num) / float(x.den) if hasattr(x, "num") else float(x)

    return f(d) + f(m) / 60.0 + f(s) / 3600.0


def parse_exif(fp) -> Dict[str, Any]:
    """
    Extract taken_at, GPS lat/lon, GPSImgDirection if available.
    Returns dict with keys: taken_at, lat, lon, img_direction, img_direction_ref, raw
    """
    with open(fp, "rb") as f:
        tags = exifread.process_file(f, details=False)

    out: Dict[str, Any] = {"raw": {}}
    out["raw"] = {k: str(v) for k, v in tags.items()}

    # Time
    dt = tags.get("EXIF DateTimeOriginal") or tags.get("EXIF DateTimeDigitized")
    if dt:
        # EXIF has no TZ by default; you can store offsets in newer specs, but many files lack it.
        # We'll parse naive and let the app localize later.
        try:
            out["taken_at"] = datetime.strptime(
                str(dt), "%Y:%m:%d %H:%M:%S"
            ).isoformat()
        except Exception:
            pass

    # GPS position
    lat_tag = tags.get("GPS GPSLatitude")
    lat_ref = tags.get("GPS GPSLatitudeRef")
    lon_tag = tags.get("GPS GPSLongitude")
    lon_ref = tags.get("GPS GPSLongitudeRef")
    if lat_tag and lat_ref and lon_tag and lon_ref:
        lat = _to_deg(lat_tag)
        lon = _to_deg(lon_tag)
        if str(lat_ref).upper() == "S":
            lat = -lat
        if str(lon_ref).upper() == "W":
            lon = -lon
        out["lat"], out["lon"] = lat, lon

    # Camera azimuth (bearing). iPhone stores in GPSImgDirection (+ Ref = 'T' or 'M').
    # See: GPSImgDirection EXIF tag.
    img_dir = tags.get("GPS GPSImgDirection")
    img_dir_ref = tags.get("GPS GPSImgDirectionRef")
    if img_dir:
        try:
            out["img_direction"] = float(
                Fraction(str(img_dir))
            )  # often rational like '350/1'
        except Exception:
            try:
                out["img_direction"] = float(str(img_dir))
            except Exception:
                pass
    if img_dir_ref:
        out["img_direction_ref"] = str(img_dir_ref)[0].upper()

    return out
