# Inbox Page V0

## Overview
Swipe-style inbox that scores catalog offers against the user's profile and lets them shortlist or dismiss each one.

## Endpoints
- **POST /inbox** — Returns scored, undecided offers for a profile
- **POST /offers/{offer_id}/decision** — Records SHORTLISTED or DISMISSED (upsert)

## Frontend
- `/inbox` route with card list, score badges, reason bullets
- Optimistic remove on shortlist/dismiss
- Generate modal (placeholder) with copy buttons

## Data
- Decisions stored in `offer_decisions` table (SQLite, same DB as offers)
- Decided offers excluded from subsequent inbox loads
