from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from typing import List, Dict, Tuple
from astral import sun as asun
from timezonefinder import TimezoneFinder
import pytz

MIN_STEP_MINUTES = 5


@dataclass
class SunWindow:
    start: datetime
    end: datetime


def _wrap_contains(interval: Dict[str, float], angle: float) -> bool:
    s = interval["start"] % 360.0
    e = interval["end"] % 360.0
    a = angle % 360.0
    return (s <= e and s <= a <= e) or (s > e and (a >= s or a <= e))


def _timezone_for(lat: float, lon: float):
    tzname = TimezoneFinder().timezone_at(lat=lat, lng=lon) or "UTC"
    return pytz.timezone(tzname)


def _sun_angles(dt: datetime, lat: float, lon: float) -> Tuple[float, float]:
    # astral.sun.azimuth/elevation expect aware dt
    az = float(asun.azimuth((lat, lon), dt))
    el = float(asun.elevation((lat, lon), dt))
    return az, el


def sun_windows_for_day(
    lat: float,
    lon: float,
    on_date: date,
    azimuth_intervals: List[Dict[str, float]],
    min_elevation_deg: float = 5.0,
    step_minutes: int = MIN_STEP_MINUTES,
) -> List[SunWindow]:
    if not azimuth_intervals:
        return []
    tz = _timezone_for(lat, lon)
    start = tz.localize(datetime.combine(on_date, time(0, 0)))
    end = start + timedelta(days=1)
    step = timedelta(minutes=step_minutes)

    cur_on, cur_start = False, None
    windows: List[SunWindow] = []
    t = start
    while t <= end:
        az, el = _sun_angles(t, lat, lon)
        good = el >= min_elevation_deg and any(
            _wrap_contains(iv, az) for iv in azimuth_intervals
        )
        if good and not cur_on:
            cur_on, cur_start = True, t
        elif not good and cur_on:
            cur_on = False
            windows.append(SunWindow(start=cur_start, end=t))
        t += step
    if cur_on and cur_start:
        windows.append(SunWindow(start=cur_start, end=end))
    return merge_adjacent(windows, step_minutes)


def merge_adjacent(windows: List[SunWindow], step_minutes: int) -> List[SunWindow]:
    if not windows:
        return []
    windows.sort(key=lambda w: w.start)
    out = [windows[0]]
    tol = timedelta(minutes=step_minutes)
    for w in windows[1:]:
        if (w.start - out[-1].end) <= tol:
            out[-1].end = max(out[-1].end, w.end)
        else:
            out.append(w)
    return out


def intersect_with_allowed_hours(
    windows: List[SunWindow], allowed: List[Tuple[datetime, datetime]]
) -> List[SunWindow]:
    """Intersect sun windows with allowed (weather-matching) time ranges."""
    out: List[SunWindow] = []
    for ws in windows:
        for a_start, a_end in allowed:
            s = max(ws.start, a_start)
            e = min(ws.end, a_end)
            if s < e:
                out.append(SunWindow(s, e))
    return merge_adjacent(out, MIN_STEP_MINUTES)
