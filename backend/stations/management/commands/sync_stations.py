import structlog
from django.conf import settings
from django.core.management.base import BaseCommand

from mbta.client import MbtaClient
from stations.models import Station

logger = structlog.get_logger()

# Subway route IDs to sync — matches the hard-coded ROUTES list in stations/views.py.
SUBWAY_ROUTE_IDS = ["Red", "Orange", "Blue", "Green-B", "Green-C", "Green-D", "Green-E"]


class Command(BaseCommand):
    help = "Seed the stations table from the MBTA API."

    def handle(self, *args, **options) -> None:
        client = MbtaClient(api_key=settings.MBTA_API_KEY)

        # Collect stops across all routes, merging route_ids per stop since
        # a station can be served by multiple routes (e.g. Park Street: Red + Green).
        stops_by_id: dict[str, dict] = {}
        for route_id in SUBWAY_ROUTE_IDS:
            for stop in client.get_stops_for_route(route_id):
                if stop.mbta_stop_id not in stops_by_id:
                    stops_by_id[stop.mbta_stop_id] = {
                        "name": stop.name,
                        "latitude": stop.latitude,
                        "longitude": stop.longitude,
                        "route_ids": [],
                    }
                stops_by_id[stop.mbta_stop_id]["route_ids"].append(route_id)

        created_count = updated_count = 0
        for mbta_stop_id, data in stops_by_id.items():
            _, was_created = Station.objects.update_or_create(
                mbta_stop_id=mbta_stop_id,
                defaults={
                    "name": data["name"],
                    "latitude": data["latitude"],
                    "longitude": data["longitude"],
                    "route_ids": data["route_ids"],
                },
            )
            if was_created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Stations synced: {created_count} created, {updated_count} updated."
            )
        )
        logger.info("stations_synced", created=created_count, updated=updated_count)
