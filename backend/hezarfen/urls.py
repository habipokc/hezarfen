from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("hezarfen.api.urls")),
    path("ops/", include("ops.urls")),
]
