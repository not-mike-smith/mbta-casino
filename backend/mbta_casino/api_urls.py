from django.urls import include, path

urlpatterns = [
    path("", include("users.urls")),
    path("", include("stations.urls")),
    path("", include("mbta.urls")),
]
