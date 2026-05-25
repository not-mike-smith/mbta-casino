from datetime import timedelta

import structlog
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from mbta_casino.responses import error_response
from stations.models import Station
from users.auth import get_current_user

from .models import TrainPrediction

logger = structlog.get_logger()


def _prediction_list_data(prediction: TrainPrediction, now) -> dict:
    minutes = max(0, int((prediction.predicted_arrival - now).total_seconds() / 60))
    return {
        "id": prediction.id,
        "mbta_prediction_id": prediction.mbta_prediction_id,
        "mbta_trip_id": prediction.mbta_trip_id,
        "mbta_route_id": prediction.mbta_route_id,
        "direction_id": prediction.direction_id,
        "direction_label": prediction.direction_label,
        "predicted_arrival": prediction.predicted_arrival.isoformat(),
        "minutes_until_arrival": minutes,
    }


def _prediction_status_data(prediction: TrainPrediction, now) -> dict:
    minutes = max(0, int((prediction.predicted_arrival - now).total_seconds() / 60))
    return {
        "id": prediction.id,
        "mbta_route_id": prediction.mbta_route_id,
        "direction_label": prediction.direction_label,
        "predicted_arrival": prediction.predicted_arrival.isoformat(),
        "minutes_until_arrival": minutes,
        "has_arrived": prediction.has_arrived,
        "actual_arrival": prediction.actual_arrival.isoformat() if prediction.actual_arrival else None,
    }


@api_view(["GET"])
def station_predictions(request: Request, station_id: int) -> Response:
    user = get_current_user(request)
    if user is None:
        return error_response("Not authenticated.", status_code=401)

    try:
        station = Station.objects.get(id=station_id)
    except Station.DoesNotExist:
        return error_response("Station not found.", status_code=404)

    now = timezone.now()
    cutoff = now + timedelta(minutes=settings.BETTING_WINDOW_MINUTES)

    predictions = TrainPrediction.objects.filter(
        station=station,
        has_arrived=False,
        predicted_arrival__gt=cutoff,
    ).order_by("predicted_arrival")

    return Response([_prediction_list_data(p, now) for p in predictions])


@api_view(["GET"])
def prediction_status(request: Request, prediction_id: int) -> Response:
    user = get_current_user(request)
    if user is None:
        return error_response("Not authenticated.", status_code=401)

    try:
        prediction = TrainPrediction.objects.get(id=prediction_id)
    except TrainPrediction.DoesNotExist:
        return error_response("Prediction not found.", status_code=404)

    return Response(_prediction_status_data(prediction, timezone.now()))
