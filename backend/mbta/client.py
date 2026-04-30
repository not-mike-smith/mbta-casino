from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
import structlog

logger = structlog.get_logger()

MBTA_API_BASE_URL = "https://api-v3.mbta.com"

# route_type 0 = light rail (Green Line branches)
# route_type 1 = heavy rail (Red, Orange, Blue)
SUBWAY_ROUTE_TYPES = "0,1"


class MbtaApiError(Exception):
    pass


class MbtaRateLimitError(MbtaApiError):
    pass


class MbtaAuthError(MbtaApiError):
    pass


@dataclass
class MbtaPrediction:
    mbta_prediction_id: str
    mbta_trip_id: str
    mbta_route_id: str
    mbta_stop_id: str
    direction_id: int
    stop_sequence: Optional[int]
    predicted_arrival: datetime


class MbtaClient:
    def __init__(self, api_key: str = "") -> None:
        self._session = requests.Session()
        if api_key:
            self._session.headers["x-api-key"] = api_key

    def get_predictions_for_stop(self, mbta_stop_id: str) -> list[MbtaPrediction]:
        """
        Fetch current subway predictions for a stop from the MBTA v3 API.

        Filters to subway route types only (Green, Red, Orange, Blue).
        Predictions with no arrival time (first stop of a trip) are skipped.
        """
        response = self._session.get(
            f"{MBTA_API_BASE_URL}/predictions",
            params={
                "filter[stop]": mbta_stop_id,
                "filter[route_type]": SUBWAY_ROUTE_TYPES,
            },
            timeout=10,
        )
        self._raise_for_status(response)

        results = []
        for item in response.json().get("data", []):
            prediction = self._parse_prediction(item)
            if prediction is not None:
                results.append(prediction)

        logger.debug("mbta_predictions_fetched", stop=mbta_stop_id, count=len(results))
        return results

    def _parse_prediction(self, item: dict) -> Optional[MbtaPrediction]:
        attrs = item.get("attributes", {})
        relationships = item.get("relationships", {})

        arrival_time_str: Optional[str] = attrs.get("arrival_time")
        if not arrival_time_str:
            # First stop of a trip has no arrival time — skip it.
            return None

        try:
            predicted_arrival = datetime.fromisoformat(arrival_time_str)
        except ValueError:
            logger.warning("mbta_invalid_arrival_time", prediction_id=item.get("id"), value=arrival_time_str)
            return None

        route_id: Optional[str] = relationships.get("route", {}).get("data", {}).get("id")
        trip_id: Optional[str] = relationships.get("trip", {}).get("data", {}).get("id")
        stop_id: Optional[str] = relationships.get("stop", {}).get("data", {}).get("id")

        if not (route_id and trip_id and stop_id):
            logger.warning("mbta_prediction_missing_relationships", prediction_id=item.get("id"))
            return None

        return MbtaPrediction(
            mbta_prediction_id=item["id"],
            mbta_trip_id=trip_id,
            mbta_route_id=route_id,
            mbta_stop_id=stop_id,
            direction_id=attrs.get("direction_id", 0),
            stop_sequence=attrs.get("stop_sequence"),
            predicted_arrival=predicted_arrival,
        )

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.status_code == 401 or response.status_code == 403:
            raise MbtaAuthError(f"MBTA API auth failed: {response.status_code}")
        if response.status_code == 429:
            raise MbtaRateLimitError("MBTA API rate limit exceeded")
        response.raise_for_status()
