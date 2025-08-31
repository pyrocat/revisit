from django.contrib.gis.geos import Point


def make_point(lat: float, lon: float) -> Point:
    return Point(lon, lat, srid=4326)
