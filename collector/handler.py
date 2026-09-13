"""
MBTA subway snapshot collector (AWS Lambda).

Runs once a minute on an EventBridge schedule. Each run fetches the full MBTA
predictions and vehicles responses for every subway route and saves them to S3
as gzipped JSON, unmodified apart from a small wrapper recording when they were
fetched:

    s3://<bucket>/raw/predictions/date=2026-09-12/2026-09-12T22-19-00Z.json.gz
    s3://<bucket>/raw/vehicles/date=2026-09-12/2026-09-12T22-19-00Z.json.gz

This replaced the Celery poller + RDS while the app is paused, to keep collecting
data for analysis at ~$1/month. See notes/2026-09-cost-reduction.md for why.

Only the standard library and boto3 (built into the Lambda Python runtime) are
used, so there is nothing to package.
"""

import gzip
import json
import os
import urllib.request
from datetime import datetime, timezone

import boto3

MBTA_API_BASE_URL = "https://api-v3.mbta.com"

# One request per endpoint covers every subway route. Mattapan is included even
# though the betting app doesn't use it — it's free to collect.
SUBWAY_ROUTE_IDS = "Red,Mattapan,Orange,Blue,Green-B,Green-C,Green-D,Green-E"

ENDPOINTS = {
    # include=trip sideloads headsigns, same as backend/mbta/client.py
    "predictions": f"{MBTA_API_BASE_URL}/predictions?filter[route]={SUBWAY_ROUTE_IDS}&include=trip",
    "vehicles": f"{MBTA_API_BASE_URL}/vehicles?filter[route]={SUBWAY_ROUTE_IDS}",
}

s3 = boto3.client("s3")
ssm = boto3.client("ssm")

# Cached for the lifetime of the Lambda container so SSM isn't called every minute.
_api_key: str | None = None


def _get_api_key() -> str:
    global _api_key
    if _api_key is None:
        response = ssm.get_parameter(Name=os.environ["MBTA_API_KEY_PARAMETER"], WithDecryption=True)
        _api_key = response["Parameter"]["Value"]
    return _api_key


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"x-api-key": _get_api_key()})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def handler(event, context) -> dict:
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0)
    date_part = fetched_at.strftime("%Y-%m-%d")
    # Colons are legal in S3 keys but awkward in shells and local filenames.
    file_name = fetched_at.strftime("%Y-%m-%dT%H-%M-%SZ") + ".json.gz"

    failures = []
    for name, url in ENDPOINTS.items():
        try:
            body = _fetch_json(url)
        except Exception as exc:  # keep going so one bad endpoint doesn't lose the other
            print(json.dumps({"event": "fetch_failed", "endpoint": name, "error": str(exc)}))
            failures.append(name)
            continue

        snapshot = {"fetched_at": fetched_at.isoformat(), "url": url, "response": body}
        key = f"raw/{name}/date={date_part}/{file_name}"
        s3.put_object(
            Bucket=os.environ["DATA_BUCKET"],
            Key=key,
            Body=gzip.compress(json.dumps(snapshot).encode()),
            ContentType="application/json",
            ContentEncoding="gzip",
        )
        print(json.dumps({"event": "snapshot_saved", "key": key, "records": len(body.get("data", []))}))

    if failures:
        # Raising marks the invocation as failed so it shows up in the Lambda Errors metric.
        raise RuntimeError(f"Failed to fetch: {', '.join(failures)}")

    return {"fetched_at": fetched_at.isoformat()}
