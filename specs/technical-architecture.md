# Technical Architecture - MBTA Casino v0.1

## System Overview

MBTA Casino is a full-stack web application that integrates with the MBTA v3 API to provide real-time train prediction betting. The system consists of a React frontend, Django REST backend, PostgreSQL database, and background workers for tracking train arrivals.

## Architecture Diagram

```text
┌─────────────────┐
│   Browser       │
│  (React/Vite)   │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────────────────────────────┐
│         AWS ALB / CloudFront            │
└────────────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│      Django Application                 │
│      (Django REST Framework)            │
│  ┌──────────────────────────────────┐   │
│  │ REST API Endpoints               │   │
│  │ - Auth (email/cookie)            │   │
│  │ - Stations & Predictions         │   │
│  │ - Bet Management                 │   │
│  │ - User Balance                   │   │
│  └──────────────────────────────────┘   │
└─────┬──────────────────────┬────────────┘
      │                      │
      ▼                      ▼
┌─────────────┐    ┌──────────────────────┐
│  PostgreSQL │    │  Background Workers  │
│  (RDS)      │    │  (Celery + Redis)    │
│             │    │                      │
│  - Users    │    │  - Poll MBTA API     │
│  - Bets     │    │  - Track Arrivals    │
│  - Trains   │    │  - Resolve Bets      │
└─────────────┘    └──────────┬───────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   MBTA v3 API    │
                    │  (External)      │
                    └──────────────────┘
```

## Technology Stack

### Frontend

- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **State Management**: React Query for server state, Context API for auth
- **Routing**: React Router v6
- **Styling**: CSS framework of choice (Tailwind, Material-UI, etc.)
- **HTTP Client**: Standard HTTP library

### Backend

- **Framework**: Django with Django REST Framework
- **Task Queue**: Celery with Redis broker
- **Authentication**: Django sessions with cookie-based auth
- **MBTA Integration**: HTTP client for MBTA v3 API calls
- **WSGI Server**: Production WSGI server (e.g., Gunicorn)

### Data Layer

- **Primary Database**: PostgreSQL on AWS RDS
- **Cache/Message Broker**: Redis (for Celery and optional caching)

### Infrastructure

- **Cloud Provider**: AWS
- **Infrastructure as Code**: AWS CDK (Python)
- **Compute**: Container orchestration (ECS) or VM-based
- **Load Balancing**: Application Load Balancer
- **Static Assets**: S3 with optional CDN
- **Secrets**: AWS Secrets Manager for API keys and credentials

## Key Technical Challenges

### Challenge 1: Tracking Actual Train Arrivals

**Problem**: The MBTA API does not provide historical arrival data. To resolve bets, we must determine when trains actually arrived, but there is no endpoint that shows "train X arrived at stop Y at time Z" after the fact.

**Solution Strategy**: Implement real-time arrival tracking using background workers that poll the MBTA API.

#### Approach

1. Capture Prediction Snapshot at Bet Time
   - Store the original prediction details when user places bet
   - Include: trip identifier, stop identifier, predicted arrival time, bet placement timestamp
   - This creates an immutable record of what the user bet against
2. Continuous Monitoring
   - Background workers poll MBTA predictions endpoint at regular intervals (every 15-30 seconds)
   - Track all predictions associated with active bets
   - Monitor how predictions change as trains approach stations
3. Arrival Detection
   - Use multiple heuristics to detect when train has arrived:
     - **Disappearance**: Prediction removed from API response (most reliable indicator)
     - **Time-based**: Current time exceeds predicted time + reasonable buffer
     - **Vehicle tracking**: Query vehicle positions to confirm vehicle passed the stop
   - Combine signals to determine best estimate of actual arrival time
4. Bet Resolution
   - Compare actual arrival time to originally predicted time
   - Apply betting rules: before/after/exact match
   - Update bet status and user token balance

#### Trade-offs

- Arrival times are estimates, not perfectly precise measurements
- Acceptable for demonstration/entertainment purposes
- Cancelled trains or missing data handled as edge cases (void bet or push)

### Challenge 2: MBTA API Rate Limits

**Problem**: MBTA API allows 1,000 requests per minute. With multiple users and frequent background polling, we could exceed this limit.

**Solution Strategy**:

- **Batch Requests**: Single poller fetches predictions for multiple stops in one request
- **Caching**: Cache prediction responses for 15-30 seconds to reduce redundant calls
- **Smart Polling**: Only poll for stops with active bets
- **Error Handling**: Implement exponential backoff when rate limited
- **Key Management**: Secure storage of API key in AWS Secrets Manager

### Challenge 3: Cookie-Based Session Management

**Problem**: Need to maintain user sessions without passwords, using only email and cookies.

**Solution Strategy**:

- Django session framework stores session data in database
- Session ID stored in HTTP-only, secure cookie
- Email serves as unique identifier, linked to session
- Sessions persist across browser restarts
- Registering with an existing email re-issues a session for the existing account (`get_or_create` semantics) — no duplicate accounts, no error
- For v0.1: Simple approach, can enhance in future versions

### Challenge 4: Cross-Origin Requests (Frontend ↔ Backend on Separate Subdomains)

**Problem**: Frontend (`app.domain.com`) and backend API (`api.domain.com`) are on different origins, requiring careful CORS and CSRF configuration.

**Solution Strategy**:

- Frontend and backend share the same registrable domain (eTLD+1), so they are **same-site** — SameSite session cookies work across subdomains
- Session cookie set with `Domain=.domain.com` to be shared across subdomains
- CORS configured via `django-cors-headers` to allow the frontend origin explicitly
- CSRF protection via Django's standard CSRF cookie + `X-CSRFToken` request header (React reads token from cookie and sends in header)
- In local development: frontend on `localhost:5173` (Vite), backend on `localhost:8000` (Django); CORS allows `http://localhost:5173`
- In production: CORS allows `https://app.domain.com` only; no wildcard origins

## Data Models (Conceptual)

### User Entity

**Purpose**: Represent a player account

**Key Data**:

- Unique email address (identifier)
- Current token balance (starts at 1,000)
- Session reference for cookie-based auth
- Account creation timestamp

**Important**: Need to prevent duplicate emails and ensure token balance cannot go negative.

### Bet Entity

**Purpose**: Record of a single wager

**Key Data**:

- Reference to user who placed bet
- Reference to train prediction being bet on
- Token amount wagered (must be whole number)
- Bet direction (BEFORE or AFTER predicted time)
- Bet status (active, won, lost, push, void)
- Timestamps for placement and resolution

**Critical Snapshot Data**:

- Original predicted arrival time (captured at bet placement)
- Actual arrival time (recorded after train arrives)
- These timestamps are immutable and essential for fair bet resolution

**Important**: A user can only have ONE active bet at a time for v0.1. Enforce this at application level only so user can have multiple concurrent bets in later versions.

### Train Prediction Entity

**Purpose**: Track a specific MBTA prediction and its outcome

**Key Data**:

- MBTA identifiers (prediction ID, trip ID, stop ID, route ID)
- Direction and stop sequence information
- Predicted arrival time (updates as MBTA updates prediction)
- Arrival status flag (has train arrived yet?)
- Actual arrival time (determined by arrival detection logic)
- Timestamps for creation and last update

**Important**: This entity gets updated frequently by background workers. Need to track when prediction was first created vs. its current state.

### Station Reference Entity

**Purpose**: Catalog of MBTA subway stations

**Key Data**:

- MBTA stop identifier
- Human-readable station name
- Associated route(s) (e.g., Red Line, Green Line)
- Geographic coordinates (for future mapping features)

**Important**: This is mostly static reference data, loaded during initial deployment. Can be seeded from MBTA stops API.

### Relationships

- User has many Bets (one-to-many)
- Bet references one Train Prediction (many-to-one)
- Train Prediction references one Station (many-to-one)
- User can have only ONE active Bet at a time (application constraint)

## API Endpoints (REST)

### Authentication & User Management

- Register new user (email only)
- Logout current user
- Get current user profile
- Get user token balance

### Stations & Predictions

- List available subway stations
- Get current predictions for a specific station
- Predictions should be filtered to only show bettable trains (not too soon to arrival)

### Betting

- Place a new bet (validates one-active-bet rule, sufficient balance)
- Get user's current active bet (returns null if none)
- Get user's betting history (paginated list of past bets)

### Real-time Updates (Future Enhancement)

- For v0.1: Frontend polls for active bet status
- For v0.2: Consider WebSockets for push updates

## Background Workers

### Task: Monitor Active Predictions

**Purpose**: Poll MBTA API for predictions related to active bets

**Frequency**: Every 15-30 seconds (balance between freshness and rate limits)

**Logic**:

1. Query database for all active bets
2. Extract unique stops/routes to minimize API calls
3. Fetch current predictions from MBTA API
4. Update train prediction records
5. Check if any trains have arrived (prediction disappeared or passed time threshold)
6. Trigger bet resolution for arrived trains

### Task: Resolve Bet

**Purpose**: Determine outcome and update balances

**Trigger**: When arrival detection signals train has arrived

**Logic**:

1. Retrieve bet and its snapshot of predicted time
2. Compare actual arrival to predicted arrival
3. Apply betting rules (before/after/push)
4. Update bet status (won/lost/push)
5. Adjust user token balance (add winnings or leave for loss)
6. Record resolution timestamp

### Task: Cleanup Stale Data

**Purpose**: Remove old prediction data no longer needed

**Frequency**: Periodic (hourly or daily)

**Logic**: Delete predictions older than retention threshold (e.g., 24 hours) that have no associated active bets

## Application Structure

### Django Backend Organization

```text
mbta_casino/
├── apps/
│   ├── users/          # User models, auth logic
│   ├── betting/        # Bet models, placement logic, history
│   ├── mbta/           # MBTA API client, prediction tracking
│   │   ├── client.py   # HTTP client for MBTA API
│   │   ├── tasks.py    # Celery background tasks
│   │   └── tracker.py  # Arrival detection logic
│   └── stations/       # Station reference data
└── config/             # Django settings, URLs, WSGI
```

**Design Principle**: Separate concerns into focused apps. The `mbta` app encapsulates all external API interaction and arrival tracking complexity.

### React Frontend Organization

```text
frontend/src/
├── components/
│   ├── auth/           # Registration form
│   ├── betting/        # Station selector, prediction list, bet form
│   ├── history/        # Betting history display
│   └── layout/         # Header, token balance, nav
├── services/           # API client functions
├── hooks/              # Custom React hooks for data fetching
├── context/            # Auth context for session state
└── types/              # TypeScript type definitions
```

**Design Principle**: Component-based architecture. Keep API logic in services layer, use React Query for server state management.

## AWS Infrastructure

### Core Resources

1. **VPC**: Network isolation with public/private subnets
2. **RDS PostgreSQL**: Managed database service
3. **Container Service**: Run Django application (ECS Fargate or similar)
4. **Application Load Balancer**: Route HTTP traffic
5. **ElastiCache Redis**: Celery message broker and caching
6. **S3 Bucket**: Static asset hosting for React build
7. **CloudFront** (optional): CDN for frontend assets
8. **Secrets Manager**: Secure storage for MBTA API key, database credentials
9. **CloudWatch**: Logging and monitoring

### Deployment Architecture

- **Backend**: Containerized Django app running on ECS with Celery workers
- **Frontend**: Static files in S3, served via CloudFront or ALB
- **Database**: RDS in private subnet, accessed only by backend
- **Queue**: Redis for Celery task queue

## Security Considerations

### Authentication & Sessions

- HTTP-only cookies prevent XSS attacks
- Secure flag ensures HTTPS-only transmission
- CSRF protection via Django middleware
- Rate limiting on sensitive endpoints

### Input Validation

- Validate all user inputs server-side
- Sanitize email addresses
- Enforce positive integer token amounts
- Check user balance before accepting bets

### External API

- Store MBTA API key securely (never in code)
- Make MBTA calls only from backend (never expose key to frontend)
- Implement retry logic with backoff for resilience

### Database

- Use ORM to prevent SQL injection
- Implement proper indexing for query performance
- Consider connection pooling for scalability

## Performance Targets

- **Page Load**: < 2-3 seconds for initial load
- **API Response**: < 500ms for bet placement, balance checks
- **Prediction Freshness**: < 30 seconds staleness for displayed predictions
- **Bet Resolution**: Within 1-2 minutes of actual train arrival
- **Concurrent Users**: Support 10-50 users for v0.1 demonstration

## Monitoring & Observability

### Key Metrics

- API endpoint response times and error rates
- Celery task queue length and processing times
- MBTA API success/failure rates
- Database query performance
- Active bet count and resolution times

### Logging

All application logging uses **`structlog`** for structured, context-aware log output.

**Log format**:

- Production: JSON, one object per line, shipped to CloudWatch Logs
- Local development: human-readable console output

**Required fields on every log record**:

- `timestamp` — ISO 8601 UTC
- `level` — `INFO`, `WARNING`, `ERROR`, etc.
- `message` — human-readable description of the event

**Contextual fields**:

Additional fields such as `user_id`, `bet_id`, and `request_id` are bound at request or task boundaries using `structlog.contextvars.bind_contextvars()` and automatically appear on all log records within that context. Specific fields are determined during implementation.

**Correlation IDs** (planned, may slip for v0.1):

A correlation ID generated at the Django request boundary would be propagated into any Celery tasks spawned during that request, enabling end-to-end tracing of a single user action across both log groups.

**CloudWatch log groups**:

- `/mbta-casino/app` — Django application logs
- `/mbta-casino/worker` — Celery worker logs

### Alerts

- High error rates from MBTA API
- Database connection issues
- Celery worker failures or queue backup
- Application crashes or high error rates

## Development Workflow

### Local Development Setup

1. PostgreSQL and Redis via Docker Compose
2. Django development server (`manage.py runserver`)
3. Celery worker process
4. Vite development server with hot reload

### Environment Configuration

- Use environment variables for all config (database URLs, API keys, etc.)
- Never commit secrets to version control
- Provide an example `.env` file for local setup

### Testing Strategy

**Framework**: `pytest` with `pytest-django`.

**Scope**: Unit tests for backend business logic — primarily bet resolution, token balance updates, and betting window validation. MBTA API calls are mocked in tests. Integration tests for API endpoints are desirable but secondary. No fixed coverage target; coverage will be added where confidence is most valuable and mocking is practical.

**Mocking approach**: To be determined during implementation based on what dependency injection patterns emerge naturally in Django. The goal is testable seams around the MBTA API client and background task logic.

## Deployment Strategy

### Database Migrations

Django's migration system generates Python migration files from model changes (`manage.py makemigrations`). These files are committed to version control and applied explicitly with `manage.py migrate`.

**Strategy**:

- Migrations are a separate, explicit step — never bundled into the application container entrypoint.
- The application will start and operate against the database even if migrations are pending. This decouples migration failures from application availability.
- For v0.1: migrations are run manually before deploying a new application version.
- Rolling back a migration is done by targeting a specific prior migration name: `manage.py migrate <app_label> <migration_name>`.

### Initial Deployment

1. Provision AWS infrastructure via CDK (`cdk deploy`)
2. Run database migrations (`manage.py migrate`)
3. Seed station reference data (Django management command)
4. Deploy backend application container
5. Build and deploy frontend static assets to S3
6. Configure load balancer routing

### Ongoing Updates

1. Run database migrations as a separate step before deploying new application code
2. Deploy backend with rolling updates
3. Build and upload new frontend bundle to S3
4. Invalidate CloudFront cache if applicable

### CI/CD

**CI**: GitHub Actions, triggered on push to `main`.

CI checks (to be expanded during implementation):

- `pytest` test suite
- Linting and formatting checks

**CD**: Manual for v0.1. Deployments are performed by running CDK and application deploy commands locally, following the initial deployment runbook above.

**Environments**: Single production environment for v0.1. A second environment is a future milestone and a test of infrastructure automation completeness.

## Open Questions & Future Enhancements

1. **WebSocket Support**: For v0.2, add real-time push updates instead of polling
2. **Prediction Quality**: How to handle highly inaccurate or frequently updated predictions?
3. **Mobile Experience**: Optimize UI for mobile betting on-the-go
4. **Historical Analytics**: Track long-term accuracy of bets by line, time of day, etc.
5. **Scaling**: Current design targets small user base; what changes needed for 1,000+ concurrent users?

## References

- [MBTA v3 API Documentation](https://www.mbta.com/developers/v3-api)
- [MBTA Best Practices](https://www.mbta.com/developers/v3-api/best-practices)
- [Django REST Framework Docs](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [AWS CDK Python Guide](https://docs.aws.amazon.com/cdk/api/v2/python/)
