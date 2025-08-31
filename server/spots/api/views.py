from datetime import datetime, date
from typing import List, Dict
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SpotSerializer
from .permissions import IsOwnerOrReadOnly
from ..models import Spot, SunWindowCache
from ..utils.exif import parse_exif
from ..utils.sun import sun_windows_for_day, intersect_with_allowed_hours
from ..utils.weather import daily_weather_category, hourly_allowed_ranges


class SpotViewSet(viewsets.ModelViewSet):
    queryset = Spot.objects.all().select_related("user")
    serializer_class = SpotSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        spot = serializer.save(user=self.request.user)
        if spot.photo:
            ex = parse_exif(spot.photo.path)
            changed = False
            if ex.get("taken_at") and not spot.taken_at:
                spot.taken_at = datetime.fromisoformat(ex["taken_at"])
                changed = True
            if "lat" in ex and "lon" in ex and not spot.location:
                from ..utils.geo import make_point

                spot.location = make_point(ex["lat"], ex["lon"])
                changed = True
            if ex.get("img_direction") and not spot.camera_azimuth:
                spot.camera_azimuth = float(ex["img_direction"]) % 360.0
                spot.camera_azimuth_ref = ex.get("img_direction_ref", "")
                changed = True
            spot.exif = ex
            if changed:
                spot.save(
                    update_fields=[
                        "taken_at",
                        "location",
                        "camera_azimuth",
                        "camera_azimuth_ref",
                        "exif",
                        "updated_at",
                    ]
                )
        return spot

    @action(detail=True, methods=["get"])
    def windows(self, request, pk=None):
        """
        GET /api/spots/{id}/windows/?date=YYYY-MM-DD
        Returns cached or computed sun windows (weather-agnostic) for the spot/date.
        """
        try:
            q_date = date.fromisoformat(request.query_params.get("date"))
        except Exception:
            return Response(
                {"detail": "Invalid or missing date (YYYY-MM-DD)."}, status=400
            )
        spot = self.get_object()
        if not spot.location:
            return Response({"detail": "Spot has no location."}, status=400)

        cache = SunWindowCache.objects.filter(spot=spot, for_date=q_date).first()
        if not cache or spot.updated_at > cache.computed_at:
            windows = sun_windows_for_day(
                lat=spot.location.y,
                lon=spot.location.x,
                on_date=q_date,
                azimuth_intervals=spot.desired_azimuth_ranges,
                min_elevation_deg=spot.min_sun_elevation,
            )
            as_json = [
                {"start": w.start.isoformat(), "end": w.end.isoformat()}
                for w in windows
            ]
            SunWindowCache.objects.update_or_create(
                spot=spot, for_date=q_date, defaults={"windows": as_json}
            )
            return Response({"date": q_date.isoformat(), "windows": as_json})
        return Response({"date": q_date.isoformat(), "windows": cache.windows})


class SuggestionsAPI(APIView):
    """
    GET /api/suggestions/?date=YYYY-MM-DD&lat=..&lon=..[&radius_km=25]
    Returns nearby spots (owned by current user) where desired weather matches hourly forecast.
    Each spot contains time windows when the Sun is within the desired azimuth AND weather category matches.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        try:
            q_date = date.fromisoformat(request.query_params.get("date"))
        except Exception:
            return Response(
                {"detail": "Invalid or missing date (YYYY-MM-DD)."}, status=400
            )
        try:
            lat = float(request.query_params.get("lat"))
            lon = float(request.query_params.get("lon"))
        except Exception:
            return Response({"detail": "lat & lon are required."}, status=400)

        radius_km = float(request.query_params.get("radius_km", 25))
        user_point = Point(lon, lat, srid=4326)

        qs = Spot.objects.filter(user=request.user, location__isnull=False)
        qs = qs.annotate(distance=Distance("location", user_point)).order_by("distance")

        # Optional radius clip
        if radius_km > 0:
            qs = qs.filter(location__distance_lte=(user_point, radius_km * 1000))

        results = []
        for s in qs:
            desired_weather = set(s.desired_weather or [])
            # Build or read cached sun windows
            cache = SunWindowCache.objects.filter(spot=s, for_date=q_date).first()
            if not cache or s.updated_at > cache.computed_at:
                windows = sun_windows_for_day(
                    lat=s.location.y,
                    lon=s.location.x,
                    on_date=q_date,
                    azimuth_intervals=s.desired_azimuth_ranges,
                    min_elevation_deg=s.min_sun_elevation,
                )
                as_json = [
                    {"start": w.start.isoformat(), "end": w.end.isoformat()}
                    for w in windows
                ]
                cache, _ = SunWindowCache.objects.update_or_create(
                    spot=s, for_date=q_date, defaults={"windows": as_json}
                )

            # Hourly weather ranges (if no preference, accept entire day)
            if desired_weather:
                allowed = hourly_allowed_ranges(
                    s.location.y, s.location.x, q_date, desired_weather
                )
                if not allowed:
                    continue  # no hours match desired weather
                # Intersect cached windows with allowed weather hours
                sun_windows = [
                    (
                        datetime.fromisoformat(w["start"]),
                        datetime.fromisoformat(w["end"]),
                    )
                    for w in (cache.windows or [])
                ]
                from ..utils.sun import SunWindow

                merged = intersect_with_allowed_hours(
                    [SunWindow(sv[0], sv[1]) for sv in sun_windows], allowed
                )
                if not merged:
                    continue
                windows_json = [
                    {"start": w.start.isoformat(), "end": w.end.isoformat()}
                    for w in merged
                ]
            else:
                windows_json = cache.windows

            if not windows_json:
                continue

            results.append(
                {
                    "id": s.id,
                    "title": s.title,
                    "description": s.description,
                    "tags": s.tags,
                    "distance_m": float(getattr(s, "distance", 0).m),
                    "lat": s.location.y,
                    "lon": s.location.x,
                    "time_windows": windows_json,
                }
            )

        return Response(
            {"date": q_date.isoformat(), "count": len(results), "results": results}
        )
