# Data Models - MBTA Casino v0.1

## Overview

This document defines the database schema for the MBTA Casino application. The system uses PostgreSQL as the primary database, with Django ORM managing models and migrations.

## Design Principles

### Primary Keys
- **Default**: Auto-incrementing unsigned integers for all tables
- **Exception**: Use natural keys (like MBTA IDs) where they serve as the idiomatic identifier
- **Future Consideration**: If bet IDs are exposed in URLs and creation order should be obfuscated, consider UUIDs

### Timestamps
- All entities include `created_at` timestamp
- Mutable entities include `updated_at` timestamp
- Use timezone-aware timestamps (UTC)

### Indexing
- Index all foreign keys
- Index fields used in WHERE clauses frequently
- Composite indexes for common query patterns

### Constraints
- NOT NULL for required fields
- UNIQUE constraints where business logic demands uniqueness
- CHECK constraints for data validation (e.g., positive token amounts)
- Foreign key constraints with appropriate CASCADE/PROTECT rules

## Entity Relationship Diagram

```
┌─────────────────┐
│  user_account   │
│  - id (PK)      │
│  - email        │◄───────┐
│  - token_balance│         │
│  - session_key  │         │
└─────────────────┘         │
                            │
                            │ (1:N)
                            │
                      ┌─────┴──────────┐
                      │      bet       │
                      │  - id (PK)     │
                      │  - user_id (FK)│
                      │  - prediction_id│
                      │  - amount      │
                      │  - direction   │
                      │  - status      │
                      └─────┬──────────┘
                            │
                            │ (N:1)
                            │
                      ┌─────▼──────────────┐
                      │ train_prediction   │
                      │  - id (PK)         │
                      │  - station_id (FK) │
                      │  - mbta_trip_id    │
                      │  - mbta_prediction_id│
                      │  - predicted_arrival│
                      └─────┬──────────────┘
                            │
                            │ (N:1)
                            │
                      ┌─────▼──────────┐
                      │    station     │
                      │  - id (PK)     │
                      │  - mbta_stop_id│
                      │  - name        │
                      └────────────────┘
```

## Table Definitions

### user_account

Represents a player account in the system.

**Purpose**: Store user identity, session info, and token balance.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | unsigned int | PK, auto-increment | Internal user identifier |
| email | string | NOT NULL, UNIQUE | User's email address, used as login identifier |
| token_balance | integer | NOT NULL, CHECK >= 0, DEFAULT 1000 | Current number of tokens user can bet |
| session_key | string | UNIQUE, NULLABLE | Django session identifier for cookie auth |
| created_at | timestamp | NOT NULL | Account creation time |
| updated_at | timestamp | NOT NULL | Last modification time |

**Indexes**:
- Primary key on `id`
- Unique index on `email`
- Index on `session_key` (for session lookup)

**Notes**:
- Session key links to Django's session framework
- Token balance cannot go negative (CHECK constraint)
- For v0.1, no password or email verification needed
- New accounts start with 1,000 tokens

---

### bet

Represents a single wager on a train prediction.

**Purpose**: Record all bet details including snapshot of prediction at bet time and resolution outcome.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | unsigned int | PK, auto-increment | Internal bet identifier |
| user_account_id | unsigned int | FK → user_account.id, NOT NULL | User who placed the bet |
| train_prediction_id | unsigned int | FK → train_prediction.id, NOT NULL | Prediction being bet on |
| amount | integer | NOT NULL, CHECK > 0 | Number of tokens wagered (whole number) |
| direction | enum | NOT NULL | User's bet: 'BEFORE' or 'AFTER' predicted time |
| status | enum | NOT NULL, DEFAULT 'ACTIVE' | Current bet state (see below) |
| predicted_arrival_time | timestamp | NOT NULL | Snapshot: predicted time when bet was placed |
| actual_arrival_time | timestamp | NULLABLE | Actual arrival time (populated on resolution) |
| placed_at | timestamp | NOT NULL | When bet was created |
| resolved_at | timestamp | NULLABLE | When bet was resolved (null if still active) |

**Enums**:
- **direction**: `BEFORE`, `AFTER`
- **status**: `ACTIVE`, `WON`, `LOST`, `PUSH`, `VOID`

**Indexes**:
- Primary key on `id`
- Foreign key index on `user_account_id`
- Foreign key index on `train_prediction_id`
- Index on `status` (for querying bets by status)
- Index on `placed_at` (for history queries)

**Status Values**:
- **ACTIVE**: Bet placed, waiting for train arrival
- **WON**: User's prediction was correct
- **LOST**: User's prediction was incorrect
- **PUSH**: Train arrived exactly on time, wager returned
- **VOID**: Bet cancelled due to train cancellation or system error

**Notes**:
- `predicted_arrival_time` is a snapshot captured at bet placement, ensuring fair resolution even if MBTA later updates the prediction
- `actual_arrival_time` and `resolved_at` are populated when the bet is resolved
- For v0.1 UI simplicity, users can only place one bet at a time (enforced in frontend only)
- Consider UUID for PK if bet IDs are exposed in shareable URLs

---

### train_prediction

Represents a specific MBTA train prediction that can be bet on or is being tracked.

**Purpose**: Track MBTA predictions and detect actual arrival times for bet resolution.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | unsigned int | PK, auto-increment | Internal prediction identifier |
| station_id | unsigned int | FK → station.id, NOT NULL | Which station this prediction is for |
| mbta_prediction_id | string | UNIQUE, NOT NULL | MBTA's identifier for this prediction |
| mbta_trip_id | string | NOT NULL | MBTA's trip identifier |
| mbta_route_id | string | NOT NULL | MBTA route (e.g., 'Red', 'Orange') |
| direction_id | small int | NOT NULL | MBTA direction: 0 or 1 (inbound/outbound) |
| stop_sequence | integer | NULLABLE | Position in trip sequence |
| predicted_arrival | timestamp | NOT NULL | Current predicted arrival time (updates) |
| has_arrived | boolean | NOT NULL, DEFAULT false | Flag: has train arrived yet? |
| actual_arrival | timestamp | NULLABLE | Detected actual arrival time |
| created_at | timestamp | NOT NULL | When prediction first recorded |
| updated_at | timestamp | NOT NULL | Last update from MBTA API |

**Indexes**:
- Primary key on `id`
- Unique index on `mbta_prediction_id`
- Foreign key index on `station_id`
- Composite index on `(station_id, mbta_route_id, direction_id)` (for station queries)
- Index on `has_arrived` (for filtering active predictions)
- Index on `updated_at` (for cleanup tasks)

**Notes**:
- Multiple bets can reference the same prediction (many-to-one relationship)
- `mbta_prediction_id` uniquely identifies the prediction from MBTA API
- `predicted_arrival` is mutable and updates as MBTA updates the prediction
- `actual_arrival` is set once when arrival is detected
- `has_arrived` flag enables efficient querying of unresolved predictions
- `stop_sequence` helps with vehicle tracking logic

---

### station

Reference data for MBTA subway stations.

**Purpose**: Catalog of available stations users can select for betting.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | unsigned int | PK, auto-increment | Internal station identifier |
| mbta_stop_id | string | UNIQUE, NOT NULL | MBTA's identifier for this stop |
| name | string | NOT NULL | Human-readable station name |
| route_ids | json | NOT NULL | Array of route IDs serving this station |
| latitude | decimal | NULLABLE | Station latitude (for future mapping) |
| longitude | decimal | NULLABLE | Station longitude (for future mapping) |
| created_at | timestamp | NOT NULL | When record was created |

**Indexes**:
- Primary key on `id`
- Unique index on `mbta_stop_id`
- Index on `name` (for search/autocomplete)

**Notes**:
- Only subway stations included (no bus, commuter rail, ferry)
- `route_ids` is JSON array like `["Red", "Orange"]` for transfer stations
- Reference data seeded from MBTA stops API during deployment
- Data is relatively static, updates handled via manual migrations

**Sample Data**:
```json
{
  "mbta_stop_id": "place-pktrm",
  "name": "Park Street",
  "route_ids": ["Red", "Green-B", "Green-C", "Green-D", "Green-E"],
  "latitude": 42.3565,
  "longitude": -71.0624
}
```

## Relationships

### user_account → bet (One-to-Many)
- One user can have many bets
- Foreign key: `bet.user_account_id` → `user_account.id`
- On delete: PROTECT (cannot delete user with bets)

### bet → train_prediction (Many-to-One)
- Many bets can reference the same prediction
- Each bet references exactly one prediction
- Foreign key: `bet.train_prediction_id` → `train_prediction.id`
- On delete: PROTECT (cannot delete prediction with bets)

### train_prediction → station (Many-to-One)
- Many predictions for the same station
- Each prediction is for exactly one station
- Foreign key: `train_prediction.station_id` → `station.id`
- On delete: PROTECT (cannot delete station with predictions)

## Database Constraints

**user_account**:
- `CHECK (token_balance >= 0)` - prevent negative balances
- `UNIQUE (email)` - one account per email
- `UNIQUE (session_key)` - one session per key

**bet**:
- `CHECK (amount > 0)` - must bet at least 1 token
- `CHECK (direction IN ('BEFORE', 'AFTER'))` - only valid directions
- `CHECK (status IN ('ACTIVE', 'WON', 'LOST', 'PUSH', 'VOID'))` - only valid statuses
- Foreign key constraints with PROTECT on delete

**train_prediction**:
- `UNIQUE (mbta_prediction_id)` - no duplicate MBTA predictions
- `CHECK (direction_id IN (0, 1))` - only valid MBTA directions
- Foreign key to station with PROTECT

**station**:
- `UNIQUE (mbta_stop_id)` - no duplicate stations

## Seed Data

Station reference data should be loaded from MBTA stops API during initial deployment.

## Summary

This schema provides a solid foundation for v0.1:
- **user_account**: Manages users and token balances
- **bet**: Tracks wagers with immutable prediction snapshots
- **train_prediction**: Tracks MBTA data and arrival detection
- **station**: Reference data for UI

The design prioritizes data integrity with appropriate constraints, supports efficient queries for common operations, and leaves room for future enhancements without major refactoring.
