from django.db import models


class SunlightDirection(models.TextChoices):
    FRONT = "front", "Front light"           # Sun behind photographer, lighting subject
    FRONT_LEFT = "front left", "Front left light"
    FRONT_RIGHT = "front right", "Front right light"
    SIDE_LEFT = "side_left", "Side light (left)"
    SIDE_RIGHT = "side_right", "Side light (right)"
    BACK = "back", "Backlight"


class WeatherPref(models.TextChoices):
    CLEAR = "sunny", "Clear"
    MOSTLY_CLEAR = "mostly clear", "Mostly clear"
    PARTLY_CLOUDY = "partly_cloudy", "Partly cloudy"
    CLOUDY = "cloudy", "Cloudy"
    OVERCAST = "overcast", "Overcast"
    FOG = "fog", "Fog"
    DRIZZLE = "drizzle", "Drizzle"
    RAIN = "rain", "Rain"
    THUNDER = "thunder", "Thunder"
    SNOW = "snow", "Snow"
