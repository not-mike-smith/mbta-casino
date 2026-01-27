# MBTA Casino - Specifications

This directory contains the technical and product specifications for the MBTA Casino application - a demonstration project for betting on MBTA subway arrival predictions.

## Document Index

### Product & Requirements

- [Product Requirements](product-requirements.md) - Features, user stories, and success criteria for v0.1

### Technical Documentation

- [Technical Architecture](technical-architecture.md) - System design, tech stack, and MBTA API integration strategy
- [Data Models](data-models.md) - Database schema and data structures
- [API Specification](api-spec.md) - Backend API endpoints _(coming soon)_
- [User Flows](user-flows.md) - Step-by-step user journeys _(coming soon)_

## Project Overview

**Purpose**: A toy application to gain experience with modern web development tooling and demonstrate full-stack development skills.

**Core Concept**: Users bet tokens on whether MBTA subway trains will arrive before or after their predicted arrival time.

## Version 0.1 Scope

- Email-only user accounts (no password, cookie-based sessions)
- 1,000 starting tokens per user
- Subway-only predictions (Red, Orange, Blue, Green lines)
- One active bet at a time per user
- Win condition: Bet on "before" or "after" predicted time (exact match = push)
- Betting history display
- Real-time prediction tracking and bet resolution

## Technology Stack

- **Backend**: Python/Django on AWS (deployed via CDK)
- **Frontend**: React + Vite + TypeScript
- **Database**: PostgreSQL on AWS RDS
- **External API**: MBTA v3 API

## Out of Scope for v0.1

- Email verification
- User account recovery
- Multiple concurrent bets
- Token refills (planned for v0.2)
- Bus, commuter rail, or ferry predictions
- Social features or leaderboards
- Payment integration
