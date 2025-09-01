from django.core.management.base import BaseCommand
from datetime import date, timedelta
from spots.models import Spot, SunWindowCache
from spots.utils.sun import sun_windows_for_day


class Command(BaseCommand):
    help = "Precompute sun windows for all spots in a date range (inclusive)."

    def add_arguments(self, parser):
        parser.add_argument("--start", required=True, help="YYYY-MM-DD")
        parser.add_argument("--end", required=True, help="YYYY-MM-DD")

    def handle(self, *args, **opts):
        d0 = date.fromisoformat(opts["start"])
        d1 = date.fromisoformat(opts["end"])
        days = (d1 - d0).days + 1
        cnt = 0
        for s in Spot.objects.exclude(location__isnull=True):
            for i in range(days):
                dt = d0 + timedelta(days=i)
                windows = sun_windows_for_day(
                    lat=s.location.y, lon=s.location.x,
                    on_date=dt, azimuth_intervals=s.desired_azimuth_ranges,
                    min_elevation_deg=s.min_sun_elevation
                )
                as_json = [{"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows]
                SunWindowCache.objects.update_or_create(
                    spot=s, for_date=dt, defaults={"windows": as_json}
                )
                cnt += 1
        self.stdout.write(self.style.SUCCESS(f"Computed {cnt} spot-days"))
