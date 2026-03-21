# Product Requirements Document - MBTA Casino v0.1

## Product Vision

A simple, engaging web application that allows users to bet virtual tokens on MBTA subway train arrival times. The app demonstrates modern full-stack development skills while providing an entertaining way to interact with real-time transit data.

## Target Users

- Web developers reviewing portfolio projects
- Transit enthusiasts familiar with MBTA reliability patterns

## Core Features

### 1. User Account Creation

**Description**: Minimal friction account creation using only an email address.

**Requirements**:
- User provides email address only (no password)
- No email verification required for v0.1
- System creates session and issues browser cookie
- Cookie persists user identity across sessions
- Each new account starts with 1,000 tokens

**User Story**: "As a new user, I want to quickly create an account with just my email so I can start betting immediately without complex registration."

### 2. Station and Line Selection

**Description**: Users browse MBTA subway stations to find trains to bet on.

**Requirements**:
- Display all MBTA subway lines (Red, Orange, Blue, Green-B, Green-C, Green-D, Green-E)
- Allow selection of specific station
- Show only stations with active predictions available
- Interface should be intuitive for users unfamiliar with all MBTA stations

**User Story**: "As a user, I want to select a subway station and line so I can see upcoming train predictions to bet on."

### 3. View Train Predictions

**Description**: Display real-time MBTA predictions for selected station.

**Requirements**:
- Show list of upcoming train arrivals at selected station/line
- Display predicted arrival time in clear, readable format (e.g., "Arrives at 2:45 PM" and "in 3 minutes")
- Show train direction (Inbound/Outbound or terminal destination)
- Only show predictions where betting window is still open
- Refresh predictions automatically (at least every 30 seconds)
- Indicate which predictions are available for betting

**User Story**: "As a user, I want to see upcoming train predictions with clear timing information so I can decide which train to bet on."

### 4. Place Bet

**Description**: Users wager tokens on whether a train will arrive before or after its predicted time.

**Requirements**:
- User can only have ONE active bet at a time
- User selects "Before" or "After" predicted arrival time
- User enters whole-number token amount to wager (minimum: 1, maximum: current balance)
- System validates user has sufficient tokens
- System confirms bet placement with summary:
  - Station and line
  - Predicted arrival time
  - Bet direction (Before/After)
  - Token amount wagered
- Once bet is placed, tokens are locked until bet resolves
- User cannot place another bet until current bet resolves

**Betting Rules**:
- If train arrives BEFORE predicted time and user bet "Before": User wins (2x tokens)
- If train arrives AFTER predicted time and user bet "After": User wins (2x tokens)
- If train arrives EXACTLY at predicted time: Push (user gets original wager back)
- If train arrives opposite of user's bet: User loses wagered tokens
- All bets are against the house at 1:1 odds

**User Story**: "As a user, I want to bet tokens on whether a train will arrive before or after its predicted time so I can test my knowledge of MBTA reliability."

### 5. Track Active Bet

**Description**: Users can see their current active bet and its real-time status.

**Requirements**:
- Display prominently on main screen when user has active bet
- Show:
  - Station/line/direction
  - Predicted arrival time
  - Actual bet placement time
  - Tokens wagered
  - Bet direction (Before/After)
  - Current status of train (e.g., "Approaching", "Prediction updated")
  - Countdown or time remaining until predicted arrival
- Update automatically as predictions change
- Clear indication when bet is about to resolve

**User Story**: "As a user with an active bet, I want to watch my train's status in real-time so I can see if I'm going to win."

### 6. Bet Resolution

**Description**: System automatically resolves bets when trains arrive and credits/debits tokens.

**Requirements**:
- System tracks actual arrival time of train
- Compares actual arrival to original predicted time (from when bet was placed)
- Determines outcome (Win/Loss/Push) based on betting rules
- Updates user token balance immediately
- Shows clear outcome message:
  - "You Win! Train arrived [before/after] predicted time."
  - "You Lose. Train arrived [before/after] predicted time."
  - "Push. Train arrived exactly on time."
  - Token change (+/- amount)
  - New token balance
- Allows user to place new bet after resolution

**User Story**: "As a user, I want to immediately see whether I won or lost my bet and my updated token balance so I can place my next bet."

### 7. Betting History

**Description**: Users can review their past bets and outcomes.

**Requirements**:
- Display list of all past bets (most recent first)
- For each bet show:
  - Date/time of bet
  - Station/line/direction
  - Predicted vs actual arrival time
  - Bet direction (Before/After)
  - Tokens wagered
  - Outcome (Win/Loss/Push)
  - Token change
- Persist history across sessions
- Indicate current active bet separately from history

**User Story**: "As a user, I want to see my betting history so I can track my performance and learn from patterns."

### 8. Token Balance Display

**Description**: Always show current token balance prominently.

**Requirements**:
- Display token balance on all screens
- Update in real-time as bets resolve
- Show clear indication when balance is low (< 100 tokens)
- For v0.1: Show message when user reaches 0 tokens (no refill mechanism yet)

**User Story**: "As a user, I want to always see my current token balance so I know how much I can bet."

## Success Criteria

### Functional Success

- Users can create account and receive 1,000 tokens
- Users can select station and view real-time predictions
- Users can place bets on Before/After with token amounts
- System correctly resolves bets based on actual arrivals vs predictions
- Token balances update correctly
- Betting history displays accurately
- Only one active bet allowed at a time

### User Experience Success

- Account creation takes < 30 seconds
- Predictions load within 2 seconds
- Bet placement is intuitive and requires < 3 clicks
- Real-time updates feel responsive (< 30 second delay)
- UI is clear on mobile and desktop browsers

### Technical Success

- Successfully integrates with MBTA v3 API
- Handles MBTA API rate limits appropriately
- Tracks actual train arrivals for bet resolution
- Cookie-based sessions persist correctly
- Database schema supports all required data

## Non-Functional Requirements

### Performance

- Page load time < 3 seconds
- Prediction refresh < 2 seconds
- Support at least 10 concurrent users (v0.1 demonstration scale)

### Reliability

- Handle MBTA API outages gracefully (show error message)
- Handle missing predictions or cancelled trains
- Prevent race conditions in bet placement

### Security

- Basic input validation on all forms
- Prevent token balance manipulation
- Sanitize user email addresses
- Basic SQL injection prevention via Django ORM

### Usability

- Mobile-responsive design
- Clear error messages
- Accessible UI (basic WCAG 2.1 compliance)
- Works in Chrome, Firefox, Safari

## Out of Scope for v0.1

- Email verification
- Password-based authentication
- Account recovery
- Token refills (planned for v0.2 with humorous messaging)
- Multiple concurrent bets
- Social features, leaderboards, or user profiles
- Bus, commuter rail, or ferry predictions
- Advanced analytics or statistics
- Push notifications
- Payment or real money wagering
- Admin panel

## Dependencies

- MBTA v3 API availability and reliability
- MBTA API key registration
- AWS infrastructure availability

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| MBTA API rate limits exceeded | High | Implement caching, limit prediction refresh rate |
| MBTA doesn't provide historical arrival data | High | Build real-time tracking system, store arrival times ourselves |
| Train predictions frequently updated/cancelled | Medium | Handle prediction changes, cancel bets if train cancelled |
| Users run out of tokens | Low | Display clear message, prepare for v0.2 refill feature |
| Cookie-based auth is insufficient | Low | For v0.1 demo this is acceptable, can upgrade in v0.2 |
