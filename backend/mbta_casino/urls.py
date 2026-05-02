from django.urls import include, path

from mbta_casino.views import health_check

urlpatterns = [
    path("health_check", health_check),
    path("api/v1/", include("mbta_casino.api_urls")),
]
