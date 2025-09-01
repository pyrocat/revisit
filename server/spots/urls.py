from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import SpotViewSet, SuggestionsAPI

router = DefaultRouter()
router.register(r"spots", SpotViewSet, basename="spot")

urlpatterns = [
    path("", include(router.urls)),
    path("suggestions/", SuggestionsAPI.as_view(), name="suggestions"),
]
