# API Specification - MBTA Casino v0.1

## Overview

REST API served by Django REST Framework. All endpoints are prefixed with `/api/v1/`.

Authentication is cookie-based (Django sessions). All endpoints require an authenticated user unless noted. Unauthenticated requests return `401 Unauthorized`.

## Conventions

- Request and response bodies are JSON
- Timestamps are ISO 8601 strings in UTC (e.g., `"2024-03-21T14:30:00Z"`)
- All list endpoints use offset pagination via `?page=` and `?page_size=` query params
- Errors follow a consistent shape (see Error Responses)

## Error Responses

All errors return a JSON body with `error_display_message` (always present, safe to show in the UI) and an optional `error_detail` (additional context for debugging — the UI should not parse or depend on this field).

```json
{
  "error_display_message": "You don't have enough tokens to place that bet.",
  "error_detail": "Requested amount 500 exceeds balance 120."
}
```

## Pagination

Paginated endpoints accept:

- `page` — 1-indexed page number (default: `1`)
- `page_size` — results per page (default: `20`, max: `100`)

Paginated responses wrap results in an envelope:

```json
{
  "count": 42,
  "page": 2,
  "page_size": 20,
  "results": []
}
```

---

## Endpoints

### Auth

#### POST `/api/v1/auth/register`

Create a new account or re-issue a session for an existing email. No password required.

**Auth required**: No

**Request**:

```json
{
  "email": "user@example.com"
}
```

**Response `200 OK`** (existing account, session re-issued):

```json
{
  "id": 1,
  "email": "user@example.com",
  "token_balance": 850,
  "created_at": "2024-03-01T10:00:00Z"
}
```

**Response `201 Created`** (new account):

```json
{
  "id": 2,
  "email": "new@example.com",
  "token_balance": 1000,
  "created_at": "2024-03-21T14:30:00Z"
}
```

**Error responses**:

- `400` — missing or malformed email address

**Notes**:

- Sets a session cookie (`HttpOnly`, `Secure`, `SameSite=Lax`) on success
- Session cookie domain is `.domain.com` in production to allow sharing across subdomains

---

#### POST `/api/v1/auth/logout`

Invalidate the current session.

**Auth required**: Yes

**Request**: Empty body

**Response `204 No Content`**: Session cookie cleared

---

#### GET `/api/v1/auth/me`

Get the current authenticated user's profile and token balance.

**Auth required**: Yes

**Response `200 OK`**:

```json
{
  "id": 1,
  "email": "user@example.com",
  "token_balance": 850,
  "created_at": "2024-03-01T10:00:00Z"
}
```

---

### Routes

#### GET `/api/v1/routes`

List all subway routes available for betting.

**Auth required**: Yes

**Query params**: None (no pagination — route list is small and static)

**Response `200 OK`**:

```json
[
  {
    "id": "Red",
    "name": "Red Line"
  },
  {
    "id": "Orange",
    "name": "Orange Line"
  },
  {
    "id": "Blue",
    "name": "Blue Line"
  },
  {
    "id": "Green-B",
    "name": "Green Line B"
  },
  {
    "id": "Green-C",
    "name": "Green Line C"
  },
  {
    "id": "Green-D",
    "name": "Green Line D"
  },
  {
    "id": "Green-E",
    "name": "Green Line E"
  }
]
```

**Notes**:

- `id` matches the MBTA route identifier used throughout the API
- Route list is seeded at deployment and does not change at runtime

---

### Stations

#### GET `/api/v1/stations`

List subway stations available for betting, optionally filtered by route.

**Auth required**: Yes

**Query params**:

- `route_id` _(optional)_ — filter to stations served by this route (e.g., `?route_id=Red`)

**Response `200 OK`**:

```json
[
  {
    "id": 1,
    "mbta_stop_id": "place-pktrm",
    "name": "Park Street",
    "route_ids": ["Red", "Green-B", "Green-C", "Green-D", "Green-E"],
    "latitude": 42.3565,
    "longitude": -71.0624
  }
]
```

**Error responses**:

- `400` — unrecognised `route_id` value

---

### Predictions

#### GET `/api/v1/stations/{station_id}/predictions`

Get current predictions at a station that are still within the betting window.

**Auth required**: Yes

**Path params**:

- `station_id` — internal station ID

**Response `200 OK`**:

```json
[
  {
    "id": 99,
    "mbta_prediction_id": "prediction-xyz",
    "mbta_trip_id": "trip-123",
    "mbta_route_id": "Red",
    "direction_id": 0,
    "direction_label": "Alewife",
    "predicted_arrival": "2024-03-21T14:35:00Z",
    "minutes_until_arrival": 4
  }
]
```

**Error responses**:

- `404` — station not found

**Notes**:

- Only predictions where `predicted_arrival` is more than `BETTING_WINDOW_MINUTES` (2 min) in the future are returned

---

#### GET `/api/v1/predictions/{prediction_id}/status`

Get the current status of a single prediction. Used by the frontend to poll an active bet's train status.

**Auth required**: Yes

**Path params**:

- `prediction_id` — internal prediction ID

**Response `200 OK`**:

```json
{
  "id": 99,
  "mbta_route_id": "Red",
  "direction_label": "Alewife",
  "predicted_arrival": "2024-03-21T14:35:00Z",
  "minutes_until_arrival": 2,
  "has_arrived": false,
  "actual_arrival": null
}
```

**Error responses**:

- `404` — prediction not found

**Notes**:

- `predicted_arrival` reflects the latest value from the MBTA API (may differ from the snapshot stored on the bet)
- Frontend should poll this endpoint every 15–30 seconds while a bet is active
- Future: replace polling with a webhook/WebSocket push

---

### Bets

#### POST `/api/v1/bets`

Place a new bet on a prediction.

**Auth required**: Yes

**Request**:

```json
{
  "prediction_id": 99,
  "direction": "BEFORE",
  "amount": 100
}
```

**Response `201 Created`**:

```json
{
  "id": 42,
  "prediction_id": 99,
  "station_name": "Park Street",
  "mbta_route_id": "Red",
  "direction_label": "Alewife",
  "predicted_arrival_time": "2024-03-21T14:35:00Z",
  "direction": "BEFORE",
  "amount": 100,
  "status": "ACTIVE",
  "placed_at": "2024-03-21T14:31:00Z",
  "resolved_at": null,
  "actual_arrival_time": null
}
```

**Error responses**:

- `400` — missing or invalid fields
- `409` — user already has an active bet
- `422` — insufficient token balance, prediction no longer bettable (inside betting window or already arrived)

**Notes**:

- Atomically deducts `amount` from user's token balance and creates the bet record
- `predicted_arrival_time` on the bet is a snapshot of the prediction's value at placement time
- Validates that `predicted_arrival` is still more than `BETTING_WINDOW_MINUTES` in the future at placement time

---

#### GET `/api/v1/bets/active`

Get the current user's active bet, if any.

**Auth required**: Yes

**Response `200 OK`** (bet exists):

```json
{
  "id": 42,
  "prediction_id": 99,
  "station_name": "Park Street",
  "mbta_route_id": "Red",
  "direction_label": "Alewife",
  "predicted_arrival_time": "2024-03-21T14:35:00Z",
  "direction": "BEFORE",
  "amount": 100,
  "status": "ACTIVE",
  "placed_at": "2024-03-21T14:31:00Z",
  "resolved_at": null,
  "actual_arrival_time": null
}
```

**Response `200 OK`** (no active bet):

```json
null
```

**Notes**:

- Frontend polls this endpoint after bet resolution is detected via the prediction status endpoint
- Returns `null` (not `404`) when no active bet exists, to distinguish from "bet not found"

---

#### GET `/api/v1/bets/history`

Get the current user's resolved betting history, most recent first.

**Auth required**: Yes

**Query params**: `page`, `page_size`

**Response `200 OK`**:

```json
{
  "count": 15,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "id": 41,
      "station_name": "Park Street",
      "mbta_route_id": "Red",
      "direction_label": "Alewife",
      "predicted_arrival_time": "2024-03-21T13:10:00Z",
      "actual_arrival_time": "2024-03-21T13:09:20Z",
      "direction": "BEFORE",
      "amount": 50,
      "status": "WON",
      "token_delta": 50,
      "placed_at": "2024-03-21T13:06:00Z",
      "resolved_at": "2024-03-21T13:09:30Z"
    }
  ]
}
```

**Notes**:

- Only returns resolved bets (`status` in `WON`, `LOST`, `PUSH`, `VOID`)
- `token_delta` is the net change: `+amount` for WON, `-amount` for LOST, `0` for PUSH/VOID
- Active bet is excluded; use `GET /bets/active` for that
