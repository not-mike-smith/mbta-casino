from django.urls import path

from . import views

urlpatterns = [
    path("stations/<int:station_id>/predictions", views.station_predictions),
    path("predictions/<int:prediction_id>/status", views.prediction_status),
]
