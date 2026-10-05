from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import SimpleRouter

from geofencing.api import GeofenceEventList, GeofenceViewSet
from ops.views import health
from reference.api import AirportList, ProvinceList
from terrain.api import ElevationView
from tracking.api import (
    AircraftDetailView,
    AircraftLiveView,
    AircraftTrackView,
    PlaybackView,
    StatsView,
)

from .errors import not_found

router = SimpleRouter()
router.register("geofences", GeofenceViewSet, basename="geofence")

# Paths follow ICD §7.2 exactly, trailing slashes included.
urlpatterns = [
    path("health", health, name="health"),
    path("aircraft/live", AircraftLiveView.as_view(), name="aircraft-live"),
    path("aircraft/<str:icao24>/", AircraftDetailView.as_view(), name="aircraft-detail"),
    path("aircraft/<str:icao24>/track", AircraftTrackView.as_view(), name="aircraft-track"),
    path("playback", PlaybackView.as_view(), name="playback"),
    path("geofence-events", GeofenceEventList.as_view(), name="geofence-events"),
    path("provinces/", ProvinceList.as_view(), name="provinces"),
    path("airports/", AirportList.as_view(), name="airports"),
    path("stats", StatsView.as_view(), name="stats"),
    path("terrain/elevation", ElevationView.as_view(), name="terrain-elevation"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("", include(router.urls)),
    re_path(r"^.*$", not_found),
]
