from __future__ import annotations
import requests
from datetime import date, datetime, timedelta
from typing import Literal, Optional, List, Tuple

# Open-Meteo free API; uses WMO "weather_code".
# Docs & features: open-meteo.com (no API key)
# We'll use daily weather_code as a coarse filter.
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


# Map Open-Meteo WMO weather codes to our coarse categories.
# See: "weather_code" follows WMO ww interpretations (28 conditions).
# We'll collapse them into Sunny/Partly/Cloudy/Overcast/Rain/Snow.
def code_to_category(code: int) -> str:
    if code == 0:
        return "sunny"
    if code in (1,):
        return "mostly_clear"  # mostly clear
    if code in (2,):
        return "partly_cloudy"
    if code in (3,):
        return "cloudy"
    if code in (45, 48):
        return "overcast"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    # default fallback
    return "cloudy"


def daily_weather_category(
    lat: float, lon: float, on_date: date, tz: Optional[str] = None
) -> Optional[str]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode",
        "timezone": tz or "auto",
        "start_date": on_date.isoformat(),
        "end_date": on_date.isoformat(),
    }
    r = requests.get(OPEN_METEO, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    codes = data.get("daily", {}).get("weathercode") or []
    if not codes:
        return None
    return code_to_category(int(codes[0]))


def hourly_allowed_ranges(
    lat: float,
    lon: float,
    on_date: date,
    desired: set[str],
    tzname: str | None = "auto",
) -> List[Tuple[datetime, datetime]]:
    """
    Returns a list of (start,end) datetimes within the given date where
    the hourly weather code category is in 'desired'.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "weathercode",
        "timezone": tzname or "auto",
        "start_date": on_date.isoformat(),
        "end_date": on_date.isoformat(),
    }
    r = requests.get(OPEN_METEO, params=params, timeout=10)
    r.raise_for_status()
    j = r.json()
    times = j.get("hourly", {}).get("time") or []
    codes = j.get("hourly", {}).get("weathercode") or []
    if not times or not codes:
        return []

    out: List[Tuple[datetime, datetime]] = []
    cur_start = None
    for i, ts in enumerate(times):
        dt = datetime.fromisoformat(ts)
        cat = code_to_category(int(codes[i]))
        ok = (not desired) or (cat in desired)
        if ok and cur_start is None:
            cur_start = dt
        elif not ok and cur_start is not None:
            out.append((cur_start, dt))
            cur_start = None
    if cur_start is not None:
        # extend to the end of day hour
        last_dt = datetime.fromisoformat(times[-1]) + timedelta(hours=1)
        out.append((cur_start, last_dt))
    return out
