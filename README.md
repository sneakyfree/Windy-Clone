# Windy Clone

**Your voice lives forever.**

Windy Clone turns your accumulated voice recordings, video captures, and transcribed text into a digital twin — a voice clone that sounds like you, a digital avatar that looks like you, and a soul file that captures who you are.

## What It Does

Every time you use Windy Word, you're building a treasure trove of voice data. Windy Clone is where that data becomes something immortal:

1. **Your Voice Legacy** — See how much data you've accumulated and how close you are to a studio-quality clone
2. **Clone Studio** — Browse and compare providers (ElevenLabs, HeyGen, PlayHT, and more)
3. **One-Button Upload** — Pick a provider, hit send. We package and deliver your data automatically
4. **My Clones** — Track training progress and preview your finished clones

## Quick Start

### Prerequisites

- Node.js 20+ and npm (frontend)
- Python 3.11+ and uv (backend)
- A Windy Pro account (for authentication)

### Frontend (Dashboard)

```bash
cd web
npm install
npm run dev
# → http://localhost:5173
```

### Backend (API)

```bash
cd api
cp ../.env.example .env  # Edit with your keys
uv sync
uv run uvicorn app.main:app --reload --port 8400
# → http://localhost:8400/docs
```

### Both (Docker)

```bash
docker compose up
# Frontend → http://localhost:3000
# API → http://localhost:8400
```

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Windy Pro   │────►│ Windy Clone  │────►│  Provider APIs   │
│  (recordings │     │  API + Web   │     │  (ElevenLabs,    │
│   & stats)   │     │  Dashboard   │     │   HeyGen, etc.)  │
└──────────────┘     └──────────────┘     └──────────────────┘
```

- **Windy Clone does NOT store audio/video.** It reads from Windy Pro's account-server.
- **Auth is via Windy Pro JWKS.** No separate login.
- **Providers are swappable.** One adapter class per provider.

## Port

`8400` (in the Windy ecosystem port allocation)

## Documentation

- `DNA_STRAND_MASTER_PLAN.md` — Full architecture, decisions, page designs
- `CLAUDE.md` — Claude Code quick-start
- `BRAND-ARCHITECTURE.md` — The Windy product family
- `INTEGRATION_GUIDE.md` — How Clone connects to other Windy services

## Part of the Windy Ecosystem

Windy Clone is one of 8 products in the Windy family. Learn more in `BRAND-ARCHITECTURE.md`.
