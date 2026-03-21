# User Flows - MBTA Casino v0.1

## About This Document

A user flow describes a specific goal a user wants to accomplish and the sequence of steps — across UI, API, and backend — required to accomplish it. Each flow covers one coherent user intent (e.g., "place a bet"), not a full session.

### Document Structure

Each flow is structured as follows:

- **Trigger** — what causes the user to enter this flow (a page load, a button click, a system event)
- **Preconditions** — what must be true before the flow starts (e.g., user is logged in, user has an active bet)
- **Happy Path** — the normal sequence of steps when everything works
- **Alternate Paths** — deviations from the happy path: validation errors, edge cases, empty states
- **Exit** — where the user ends up, or what flow they transition into next

Steps are written at the interaction level ("user clicks X", "system calls Y API endpoint", "UI displays Z"), not at the code level. The goal is to make the intended behavior unambiguous to anyone building or reviewing the feature.

### Flows in This Document

1. [Register / Sign In](#1-register--sign-in)
2. [Sign Out](#2-sign-out)
3. [Browse Routes and Stations](#3-browse-routes-and-stations)
4. [Place a Bet](#4-place-a-bet)
5. [Track an Active Bet](#5-track-an-active-bet)
6. [Bet Resolution](#6-bet-resolution)
7. [View Betting History](#7-view-betting-history)
8. [Token Balance Depleted](#8-token-balance-depleted)

---

## 1. Register / Sign In

**Trigger**: User visits the app without a valid session cookie.

**Preconditions**: None.

**Happy Path** (new user):

1. User navigates to the app.
2. App calls `GET /api/v1/auth/me` to check for an existing session.
3. Server returns `401` — no valid session.
4. App displays the registration screen with an email input field.
5. User enters their email address and submits.
6. App calls `POST /api/v1/auth/register` with the email.
7. Server creates a new account with 1,000 tokens, sets the session cookie, and returns `201 Created` with the user profile.
8. App stores the user profile (id, email, token_balance) in auth context.
9. App navigates to the main betting screen.

**Alternate Paths**:

- **Returning user**: Steps 1–6 are identical. At step 7 the server finds the existing account, re-issues the session cookie, and returns `200 OK`. App behavior from step 8 onward is identical.
- **Valid session on load**: At step 3, `GET /api/v1/auth/me` returns `200 OK`. App skips the registration screen entirely and navigates directly to the main betting screen.
- **Malformed email**: At step 7, server returns `400`. App displays `error_display_message` beneath the email field. User corrects input and resubmits (return to step 5).

**Exit**: User is authenticated and lands on the main betting screen.

---

## 2. Sign Out

**Trigger**: Authenticated user clicks the sign out action.

**Preconditions**: User is authenticated.

**Happy Path**:

1. User clicks the sign out button in the navigation header.
2. App calls `POST /api/v1/auth/logout`.
3. Server invalidates the session, clears the session cookie, and returns `204 No Content`.
4. App clears the user profile from auth context.
5. App navigates to the registration screen (Flow 1).

**Alternate Paths**:

- **User has an active bet**: No special handling. The bet remains active and will be resolved by the background worker regardless of session state. The outcome will be visible the next time the user signs in.

**Exit**: Session is invalidated; user is returned to the registration screen (Flow 1).

---

## 3. Browse Routes and Stations

**Trigger**: Authenticated user wants to find a train to bet on.

**Preconditions**: User is authenticated. User has no active bet (or active bet is displayed separately and does not block browsing).

**Happy Path**:

1. User is on the main betting screen.
2. App calls `GET /api/v1/routes` on page load.
3. UI displays the list of subway routes (Red, Orange, Blue, Green-B, Green-C, Green-D, Green-E).
4. User selects a route.
5. App calls `GET /api/v1/stations?route_id={route_id}`.
6. UI displays the list of stations for that route.
7. User selects a station.
8. App calls `GET /api/v1/stations/{station_id}/predictions`.
9. UI displays the list of bettable predictions for the station, each showing: route, direction label (e.g., "Alewife"), predicted arrival time, and minutes until arrival.
10. App re-polls `GET /api/v1/stations/{station_id}/predictions` every 30 seconds to keep the list fresh.

**Alternate Paths**:

- **Route or station list fails to load**: UI displays `error_display_message`. User can retry. No navigation occurs.
- **No bettable predictions at selected station**: Step 8 returns an empty list. UI displays "No predictions available right now" and suggests checking back or selecting a different station. Auto-refresh continues so the list populates when predictions appear.
- **Predictions endpoint unavailable** (MBTA API down): Step 8 returns an error. UI displays `error_display_message`. User can retry or go back to select a different station.

**Notes**:

- Routes and stations are static seeded data and do not depend on MBTA API availability. Predictions do.
- An active bet does not block browsing — it is displayed as a persistent banner and does not prevent the user from navigating routes and stations.
- Back navigation is supported at each step: pressing back from the station list returns to the route list; pressing back from the predictions view returns to the station list. This applies to both the browser back button and swipe-back on mobile.

**Exit**: User is viewing the predictions list for a station and may select a prediction to proceed to Flow 4, or navigates away.

---

## 4. Place a Bet

**Trigger**: User selects a prediction from the list at the end of Flow 3.

**Preconditions**: User is authenticated. User has no active bet. User has at least 1 token. Predictions list is visible (from Flow 3).

**Happy Path**:

1. User selects a prediction from the list.
2. UI displays the bet form with a static snapshot of the selected prediction (route, direction, predicted arrival time). Auto-refresh of the predictions list stops while the form is open — the displayed prediction does not change under the user.
3. User selects Before or After.
4. User enters a whole-number token amount. UI enforces min 1, max current balance client-side.
5. User submits the bet.
6. App calls `POST /api/v1/bets` with `prediction_id`, `direction`, and `amount`.
7. Server validates: no existing active bet, sufficient balance, prediction still outside the betting window cutoff.
8. Server snapshots the current `predicted_arrival` onto the bet, deducts tokens, and returns `201 Created`.
9. App calls `GET /api/v1/auth/me` to refresh the token balance in auth context.
10. UI transitions to the active bet tracking view (Flow 5).

**Alternate Paths**:

- **Prediction expires while form is open**: User submits at step 5, server returns `422` (prediction is now inside the betting window or has already arrived). UI displays `error_display_message` and returns the user to the predictions list with a fresh fetch.
- **Insufficient tokens**: Server returns `422` at step 7. UI displays `error_display_message` on the form. The amount field is re-enabled for correction.
- **User already has an active bet**: Server returns `409` at step 7. Should not be reachable through the normal UI (precondition requires no active bet), but the API enforces it regardless. UI displays `error_display_message`.

**Notes**:

- Auto-refresh is intentionally paused while the bet form is open. Updating the prediction mid-entry would be disorienting and could silently change what the user is betting on.
- The server re-validates the betting window at step 7, not just at display time. This is the authoritative check — client-side filtering is a convenience only.
- The snapshotted `predicted_arrival_time` recorded on the bet at step 8 is the value used for resolution, regardless of any subsequent MBTA updates.

**Exit**: Bet is placed; user transitions to Flow 5 (Track Active Bet).

---

## 5. Track an Active Bet

**Trigger**: User has an active bet and wants to monitor its status.

**Preconditions**: User is authenticated. User has an active bet.

**Happy Path**:

1. User is on any screen with an active bet. The active bet banner is visible.
2. App calls `GET /api/v1/bets/active` to load the bet details, including the snapshotted `predicted_arrival_time` — the time the bet is locked against.
3. App calls `GET /api/v1/predictions/{prediction_id}/status` to load the current live prediction.
4. UI displays the active bet with a clear distinction between two times:
   - **Your bet**: the original snapshotted predicted arrival time (immutable — this is what the bet resolves against).
   - **Current prediction**: the live predicted arrival time from MBTA (may differ from the snapshot).
5. UI also displays: station, route, direction, bet direction (Before/After), tokens wagered, and a countdown to the snapshotted arrival time.
6. App polls `GET /api/v1/predictions/{prediction_id}/status` every 15–30 seconds.
7. UI updates the current prediction time and countdown on each poll.
8. When `has_arrived: true` is returned, app transitions to Flow 6 (Bet Resolution).

**Alternate Paths**:

- **MBTA updates the prediction after bet placement**: The live `predicted_arrival` on the status endpoint changes. UI updates the "current prediction" display but the "your bet" snapshot remains unchanged. The user can see the divergence clearly.
- **Train is cancelled**: Background worker detects the prediction has disappeared and marks the bet as `VOID`. On the next poll, `GET /api/v1/bets/active` returns the bet with `status: VOID`, triggering Flow 6 with a void outcome.
- **Status endpoint unreachable**: UI retains the last known prediction data and indicates it may be stale. Polling continues.

**Notes**:

- The snapshotted `predicted_arrival_time` on the bet is the single source of truth for resolution. The live prediction is informational only.
- The UI should make this unambiguous so the user always knows exactly what they bet on.

**Exit**: `has_arrived: true` detected on the prediction status; user transitions to Flow 6 (Bet Resolution).

---

## 6. Bet Resolution

**Trigger**: Background worker detects that the train has arrived.

**Preconditions**: User has an active bet. Train arrival has been detected by the monitoring worker.

**Happy Path**:

Backend (background worker):

1. Worker detects arrival — prediction disappears from MBTA API or time threshold is exceeded.
2. Worker records `actual_arrival` on the `train_prediction` and sets `has_arrived: true`.
3. Worker compares `actual_arrival` to the bet's snapshotted `predicted_arrival_time`.
4. Worker applies push tolerance (`PUSH_TOLERANCE_SECONDS`): if the difference is within ±30 seconds, outcome is `PUSH`; otherwise `WON` or `LOST` based on bet direction.
5. Worker sets `bet.status` to `WON`, `LOST`, or `PUSH`, updates `resolved_at`, and adjusts the user's token balance (doubles the wager for `WON`, no change for `LOST`, returns the wager for `PUSH`).

Frontend:

1. Frontend poll of `GET /api/v1/predictions/{prediction_id}/status` returns `has_arrived: true`.
2. App switches to polling `GET /api/v1/bets/active` until `status` transitions away from `ACTIVE` (handles the brief window between arrival detection and bet resolution).
3. App calls `GET /api/v1/auth/me` to refresh the user's token balance in auth context.
4. UI displays the resolution outcome:
   - **Won**: "You won! Train arrived [before/after] predicted time. +X tokens."
   - **Lost**: "You lost. Train arrived [before/after] predicted time. -X tokens."
   - **Push**: "Push. Train arrived within 30 seconds of predicted time. Tokens returned."
5. UI updates the displayed token balance.
6. Active bet banner is cleared; user can now place a new bet.
7. If token balance is zero, transition to Flow 8.

**Alternate Paths**:

- **Push**: Outcome determined at backend step 4 when `actual_arrival` is within `PUSH_TOLERANCE_SECONDS` of snapshot. Frontend displays the push message and returns the wager.
- **Void** (train cancelled or arrival undetectable): Worker marks bet as `VOID` and returns the wager. Frontend displays: "Bet voided. The train was cancelled or its arrival could not be confirmed. Tokens returned."

**Notes**:

- The token balance update (step 8) is authoritative — the frontend fetches it from the server rather than computing it locally from the bet outcome.
- Steps 6–7 decouple the frontend from the exact timing of the background worker, making the flow resilient to brief processing delays.

**Exit**: Bet is resolved and token balance updated. User can place a new bet (Flow 4), or if balance is zero, transitions to Flow 8.

---

## 7. View Betting History

**Trigger**: User navigates to their history view.

**Preconditions**: User is authenticated.

**Happy Path**:

1. User clicks the history navigation item.
2. App calls `GET /api/v1/bets/history?page=1&page_size=20`.
3. UI displays the list of resolved bets, most recent first.
4. Each entry shows: station and line, direction (Inbound/Outbound), predicted vs. actual arrival time, bet direction (Before/After), tokens wagered, outcome (Won/Lost/Push), and token delta.
5. If the total bet count exceeds the page size, pagination controls are shown.
6. User clicks to a subsequent page; app calls `GET /api/v1/bets/history?page=2&page_size=20` and updates the list.

**Alternate Paths**:

- **No history yet**: UI displays an empty state message ("No bets placed yet"). No pagination controls shown.
- **API failure**: UI displays `error_display_message`. User can retry.

**Notes**:

- The active bet (if any) is not shown here — it appears in the persistent banner. History contains only resolved bets.

**Exit**: User navigates away or continues paging through history.

---

## 8. Token Balance Depleted

**Trigger**: Bet resolves and user's token balance reaches zero (entered from Flow 6).

**Preconditions**: User is authenticated. User's token balance is 0 after bet resolution.

**Happy Path**:

1. Bet resolution completes (Flow 6 step 5).
2. App refreshes the user profile from auth context; token balance is 0.
3. UI replaces the "place a bet" interface with a depleted-balance message.
4. Browsing routes, stations, and predictions (Flows 3 and 4) remains accessible. The bet placement form is replaced with the depleted-balance message.
5. Betting history (Flow 7) remains accessible.

**Alternate Paths**:

- None for v0.1 — token refill is out of scope

**Notes**:

- This flow is a deliberate dead end in v0.1. The depleted state should be clearly communicated but not punishing in tone — the user should feel the door is open, not closed permanently.
- Token refill with humorous messaging is planned for v0.2.

**Exit**: User remains on the depleted-balance state until a future version provides a refill mechanism.
