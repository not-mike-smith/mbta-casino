from django.urls import path

from . import views

urlpatterns = [
    path("routes", views.list_routes),
    path("stations", views.list_stations),
]
