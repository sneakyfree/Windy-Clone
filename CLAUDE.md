# Windy Clone — Claude Code Instructions

## What This Is

Windy Clone is the digital twin marketplace for the Windy ecosystem. It turns users' accumulated voice, video, and text data into voice clones, digital avatars, and soul files — through third-party providers (ElevenLabs, HeyGen, etc.) or eventually through Windy's own training pipeline.

## Read First

1. `DNA_STRAND_MASTER_PLAN.md` — Complete architecture, decisions, page designs, provider adapter pattern, file index
2. `BRAND-ARCHITECTURE.md` — The Windy product family and how Clone fits
3. `INTEGRATION_GUIDE.md` — How Clone connects to Windy Pro, Cloud, and Agent
4. `README.md` — Quick overview and dev setup

## Tech Stack

- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS + React Router 7
- **Backend:** Python 3.11+ / FastAPI / Uvicorn
- **Auth:** PyJWT for RS256 JWKS validation (from Windy Pro)
- **Database:** SQLAlchemy async (SQLite dev, PostgreSQL prod) — orders, clones, preferences only
- **Provider adapters:** Python Protocol pattern — one class per provider
- **Container:** Docker + docker-compose

## Build Priority

Follow the "What the Fresh Terminal Should Build First" section in DNA_STRAND_MASTER_PLAN.md. Build frontend first with mock data, then wire up backends.

## Key Conventions

- Port **8400**
- Auth via Windy Pro JWKS (no separate user DB, no separate login)
- Clone does NOT store audio/video — it fetches from Windy Pro's account-server
- Providers are swappable (Protocol pattern in `api/app/providers/base.py`)
- **No jargon in the UI.** "Recording Session" not "bundle." "Legacy Score" not "clone readiness." "Voice Twin" not "voice clone model."
- **Grandma test on every screen.** If a non-technical person can't understand it in 5 seconds, redesign it.
- Education before sales — Legacy Dashboard comes before Marketplace
- One-button upload — user picks provider, hits send, we handle everything

## Data Flow

```
Windy Pro account-server ──► Windy Clone API ──► Windy Clone Dashboard
  (recordings, bundles,       (readiness calc,     (Legacy, Discover,
   stats, quality scores)      provider adapters)    Studio, My Clones)
                                      │
                                      ▼
                              Provider APIs
                              (ElevenLabs, HeyGen, etc.)
```

## Part of the Windy Ecosystem

- **Windy Pro** (account-server): identity authority, JWKS, recording data source
- **Windy Cloud**: future home of Windy Clone Native training pipeline
- **Windy Fly** (agent): can query clone status, recommend providers, initiate training
- **Eternitas**: bot identity registry
- All repos: github.com/sneakyfree/
- VPS: 72.60.118.54 (Hostinger, Ubuntu 24.04, Docker)

## Owner

Grant Whitmer — founder of the Windy ecosystem. Prefers Python-first, normie-friendly UX, agent-first design. The Clone dashboard must pass the grandma test — emotional, educational, zero jargon.
