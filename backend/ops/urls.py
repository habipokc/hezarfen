from django.urls import path

from . import views

app_name = "ops"

urlpatterns = [
    path("", views.index, name="index"),
    path("ingest", views.ingest_partial, name="ingest"),
    path("events", views.events_partial, name="events"),
    path("geofences/<int:pk>/active", views.geofence_active, name="geofence-active"),
    path("retention", views.retention, name="retention"),
]
