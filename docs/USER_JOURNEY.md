# User Journey — Windy Clone

End-to-end user flow from first visit to completed clone.

## Overview

```
Windy Pro (records voice) → Windy Clone (dashboard) → Provider (creates clone)
```

The user never touches raw files, APIs, or technical settings.

## Journey Stages

### 1. Arrival — Legacy Dashboard (`/legacy`)

**What the user sees:**
- Warm greeting: "Every time you spoke, you were building something extraordinary"
- Stats: words spoken, hours of audio, video captured, sessions
- Readiness gauges: how close they are to a Voice Twin, Digital Avatar, Soul File
- Quality indicator: recording quality rating

**What happens behind the scenes:**
- Frontend calls `GET /api/v1/legacy/stats` → API proxies to Windy Pro account-server
- Readiness scores calculated from `services/readiness.py` with quality-weighted thresholds

---

### 2. Education — Discover Page (`/discover`)

**What the user sees:**
- Card-based explanation of what Voice Twins and Digital Avatars are
- Audio demos of what a voice clone sounds like
- Visual, jargon-free descriptions
- CTA: "Explore Voice Twins" → leads to Clone Studio

**Design philosophy:** Education before sales. The user should understand *why* this matters before seeing pricing.

---

### 3. Marketplace — Clone Studio (`/studio`)

**What the user sees:**
- Provider cards with ratings, prices, turnaround times
- Filter by type (voice/avatar/both)
- Search and sort
- "View Details" on each card

**What happens behind the scenes:**
- Frontend calls `GET /api/v1/providers` → returns provider catalog from registry

---

### 4. Provider Detail (`/studio/:providerId`)

**What the user sees:**
- Full provider info: features, pricing stats, turnaround
- Compatibility check: "You have enough data!" or "More data needed"
- One-button CTA: "Send My Data — Voice Twin"

**What happens behind the scenes:**
- `GET /api/v1/providers/{id}` for provider info
- `GET /api/v1/providers/{id}/compat` checks user's data against provider requirements

---

### 5. One-Button Send

**What the user clicks:** "Send My Data — Voice Twin"

**What happens behind the scenes:**
1. `POST /api/v1/orders` creates an order in the database
2. `services/packager.py` prepares data in provider-specific format
3. Provider adapter's `upload()` method sends data to provider API
4. User is redirected to My Clones page to watch progress

---

### 6. Training Progress (`/my-clones`)

**What the user sees:**
- Active training: provider name, progress bar, estimated time
- Completed clones: preview, download, retrain buttons

**What happens behind the scenes:**
- `services/job_tracker.py` polls provider APIs every 30 seconds
- Updates order status and progress in the database
- On completion: creates a `Clone` record and shows in "Completed"

---

### 7. Preview & Use

**What the user does:**
- Types text → hears their Voice Twin speak it back
- Downloads the clone model for use in other apps
- Can retrain with more data for better quality

---

## Error States

| Scenario | What user sees |
|----------|----------------|
| API down | "Couldn't load your stats. The server may be starting up." |
| No recordings | "Start recording to build your Voice Twin" |
| Insufficient data | "You need more data before you can send to this provider" |
| Training failed | Status changes to "Failed" with provider error message |
| Network error | Non-blocking toast: "Couldn't reach the server. Check your connection." |

## The Grandma Test

Every screen must pass: "Would my grandma understand this?"

- No: "API," "bundle," "WAV," "SSML," "endpoint"
- Yes: "recordings," "voice twin," "digital avatar," "provider," "quality"
