from django.contrib import admin
from .models import Spot, SunWindowCache


@admin.register(Spot)
class SpotAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "created_at")
    list_filter = ("user", "created_at")
    search_fields = ("title", "description", "tags")
    readonly_fields = ("desired_azimuth_ranges", "created_at", "updated_at")


@admin.register(SunWindowCache)
class SunWindowCacheAdmin(admin.ModelAdmin):
    list_display = ("spot", "for_date", "computed_at")
    list_filter = ("for_date",)
