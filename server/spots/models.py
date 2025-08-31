from django.contrib.gis.db import models as gis
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import ArrayField
from .enums import SunlightDirection, WeatherPref


User = get_user_model()


def upload_to(instance, filename):
    return f"photos/{instance.user_id}/{timezone.now().date()}/{filename}"


class Photo(models.Model):
    image = models.ImageField(upload_to=upload_to, blank=True, null=True)
    spot = models.ForeignKey("Spot", on_delete=models.CASCADE)


class Spot(models.Model):
    """
    A saved photo-spot with preferences and derived data.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="spots")

    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    # EXIF-derived
    taken_at = models.DateTimeField(null=True, blank=True)
    exif = models.JSONField(default=dict, blank=True)
    camera_azimuth = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(360.0)],
    )
    camera_azimuth_ref = models.CharField(
        max_length=1, blank=True
    )  # 'T' or 'M' if known

    # Core geometry (WGS84)
    location = gis.PointField(geography=True, srid=4326, null=True, blank=True)

    # User preferences
    tags = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    desired_directions = ArrayField(
        models.CharField(max_length=16, choices=SunlightDirection.choices),
        default=list,
        blank=True,
    )
    desired_weather = ArrayField(
        models.CharField(max_length=16, choices=WeatherPref.choices),
        default=list,
        blank=True,
    )

    # Derived absolute azimuth intervals (deg, inclusive), e.g. [{"start": 70, "end": 110}, ...]
    desired_azimuth_ranges = models.JSONField(default=list, blank=True)

    min_sun_elevation = models.FloatField(default=5.0)  # ignore very low sun

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    is_featured = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    is_draft = models.BooleanField(default=False)

    class Meta:
        indexes = [
            gis.Index(fields=["location"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return self.title or f"Spot #{self.pk}"

    # convert relative -> absolute azimuth ranges
    def compute_azimuth_ranges(self, tolerance=30.0):
        """
        Using camera_azimuth (bearing the camera points to, 0..360),
        expand user directions into absolute sun azimuth intervals.

        FRONT: around camera_azimuth
        SIDE_LEFT: camera_azimuth - 90
        SIDE_RIGHT: camera_azimuth + 90
        BACK: camera_azimuth + 180
        """
        if self.camera_azimuth is None or not self.desired_directions:
            return []

        base = self.camera_azimuth % 360.0

        def centered_range(center):
            start = (center - tolerance) % 360.0
            end = (center + tolerance) % 360.0
            return {"start": start, "end": end}

        mapping = {
            SunlightDirection.FRONT: base,
            SunlightDirection.SIDE_LEFT: (base - 90) % 360.0,
            SunlightDirection.SIDE_RIGHT: (base + 90) % 360.0,
            SunlightDirection.BACK: (base + 180) % 360.0,
        }
        ranges = []
        for d in self.desired_directions:
            center = mapping.get(d, None)
            if center is not None:
                ranges.append(centered_range(center))
        return ranges

    def save(self, *args, **kwargs):
        # refresh azimuth ranges if needed
        if self.camera_azimuth and self.desired_directions:
            self.desired_azimuth_ranges = self.compute_azimuth_ranges()
        super().save(*args, **kwargs)


class SunWindowCache(models.Model):
    """
    Cached sun windows for a specific spot & date (independent of weather).
    Windows are arrays of {start, end} ISO strings in the spot's local TZ.
    """

    spot = models.ForeignKey(Spot, on_delete=models.CASCADE, related_name="sun_caches")
    for_date = models.DateField()
    windows = models.JSONField(default=list, blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("spot", "for_date")]
        indexes = [
            models.Index(fields=["for_date"]),
            models.Index(fields=["spot", "for_date"]),
        ]

    def __str__(self):
        return f"SunWindowCache(spot={self.spot_id}, date={self.for_date})"
