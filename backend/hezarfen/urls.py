from django.contrib import admin
from django.urls import path

from ops.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health, name="health"),
]
