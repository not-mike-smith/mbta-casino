from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Station

# MBTA subway routes are static domain knowledge — no DB table needed.
ROUTES = [
    {"id": "Red", "name": "Red Line"},
    {"id": "Orange", "name": "Orange Line"},
    {"id": "Blue", "name": "Blue Line"},
    {"id": "Green-B", "name": "Green Line (B Branch)"},
    {"id": "Green-C", "name": "Green Line (C Branch)"},
    {"id": "Green-D", "name": "Green Line (D Branch)"},
    {"id": "Green-E", "name": "Green Line (E Branch)"},
]


def _station_data(station: Station) -> dict:
    return {
        "id": station.id,
        "mbta_stop_id": station.mbta_stop_id,
        "name": station.name,
        "route_ids": station.route_ids,
        "latitude": station.latitude,
        "longitude": station.longitude,
    }


@api_view(["GET"])
def list_routes(request: Request) -> Response:
    return Response(ROUTES)


@api_view(["GET"])
def list_stations(request: Request) -> Response:
    stations = Station.objects.order_by("name")

    route_id = request.query_params.get("route_id")
    if route_id:
        # JSONField __contains checks if the array is a superset of the given value.
        # Passing a list ["Red"] checks that "Red" is an element of the route_ids array.
        stations = stations.filter(route_ids__contains=[route_id])

    return Response([_station_data(s) for s in stations])
