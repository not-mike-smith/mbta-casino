import structlog
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from betting.resolution import resolve_bets_for_arrived_predictions
from mbta.client import MbtaApiError, MbtaClient
from mbta.models import TrainPrediction
from stations.models import Station

logger = structlog.get_logger()


@shared_task(name="mbta.tasks.poll_all_station_predictions")
def poll_all_station_predictions() -> None:
    """
    Fetch current MBTA predictions for every station and upsert them into the DB.

    Also detects arrivals: any prediction that has disappeared from the MBTA API
    after its predicted arrival time is assumed to have arrived and is marked as such.
    Runs every 60 seconds via celery beat.
    """
    client = MbtaClient(api_key=settings.MBTA_API_KEY)
    stations = list(Station.objects.all())
    now = timezone.now()

    created_total = updated_total = arrived_total = 0

    for station in stations:
        try:
            live_predictions = client.get_predictions_for_stop(station.mbta_stop_id)
        except MbtaApiError as exc:
            logger.warning("mbta_poll_failed", stop=station.mbta_stop_id, error=str(exc))
            continue

        live_ids = {p.mbta_prediction_id for p in live_predictions}

        # Upsert all predictions currently returned by the MBTA API.
        for p in live_predictions:
            _, was_created = TrainPrediction.objects.update_or_create(
                mbta_prediction_id=p.mbta_prediction_id,
                defaults={
                    "station": station,
                    "mbta_trip_id": p.mbta_trip_id,
                    "mbta_route_id": p.mbta_route_id,
                    "direction_id": p.direction_id,
                    "direction_label": p.direction_label,
                    "stop_sequence": p.stop_sequence,
                    "predicted_arrival": p.predicted_arrival,
                },
            )
            if was_created:
                created_total += 1
            else:
                updated_total += 1

        # Arrival detection: a prediction that has dropped off the MBTA API response
        # after its predicted arrival time has most likely arrived.
        arrived_qs = TrainPrediction.objects.filter(
            station=station,
            has_arrived=False,
            predicted_arrival__lte=now,
        ).exclude(mbta_prediction_id__in=live_ids)

        arrived_ids = list(arrived_qs.values_list("id", flat=True))
        count = arrived_qs.update(has_arrived=True, actual_arrival=now)
        arrived_total += count

        if arrived_ids:
            resolve_bets_for_arrived_predictions(arrived_ids, now)

    logger.info(
        "predictions_polled",
        created=created_total,
        updated=updated_total,
        arrived=arrived_total,
    )
