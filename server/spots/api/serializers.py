from rest_framework import serializers
from django.contrib.gis.geos import Point
from ..models import Spot
from ..enums import SunlightDirection, WeatherPref


class SpotSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(write_only=True, required=False)
    lon = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = Spot
        fields = [
            "id",
            "title",
            "description",
            "photo",
            "taken_at",
            "exif",
            "camera_azimuth",
            "camera_azimuth_ref",
            "location",
            "lat",
            "lon",
            "tags",
            "desired_directions",
            "desired_weather",
            "desired_azimuth_ranges",
            "min_sun_elevation",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "desired_azimuth_ranges",
            "created_at",
            "updated_at",
            "location",
        ]

    def validate(self, attrs):
        if "lat" in attrs and "lon" in attrs:
            attrs["location"] = Point(attrs["lon"], attrs["lat"])
        return attrs

    def create(self, validated):
        validated["user"] = self.context["request"].user
        return super().create(validated)
