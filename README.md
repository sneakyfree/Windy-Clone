# Windy Clone

**Your voice lives forever.**

Windy Clone turns your accumulated voice recordings, video captures, and transcribed text into a digital twin — a voice clone that sounds like you, a digital avatar that looks like you, and a soul file that captures who you are.

## What It Does

Every time you use Windy Word, you're building a treasure trove of voice data. Windy Clone is where that data becomes something immortal:

1. **Your Voice Legacy** — See how much data you've accumulated and how close you are to a studio-quality clone
2. **Clone Studio** — Browse and compare providers (ElevenLabs, HeyGen, PlayHT, Resemble AI, and more)
3. **One-Button Upload** — Pick a provider, hit send. We package and deliver your data automatically
4. **My Clones** — Track training progress and preview your finished clones

## Quick Start

### Prerequisites

- Node.js 20+ and npm (frontend)
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (backend)

### 1. Clone and install

```bash
git clone https://github.com/sneakyfree/Windy-Clone.git
cd Windy-Clone

# Frontend
cd web && npm install && cd ..

# Backend
cp .env.example .env
uv pip install -e ".[dev]"
mkdir -p data
```

### 2. Start both servers

```bash
# Option A: Use the dev script
./scripts/dev.sh

# Option B: Start separately
cd web && npm run dev &        # → http://localhost:5173
cd api && uv run uvicorn app.main:app --reload --port 8400 &  # → http://localhost:8400
```

### 3. Open the dashboard

Navigate to **http://localhost:5173** — the Legacy page will load with dev mock data.

### Run tests

```bash
.venv/bin/python -m pytest -v   # 17 tests
cd web && npm run build         # TypeScript check + production build
```

### Docker

```bash
docker compose up               # API on :8400, frontend built-in
docker compose --profile dev up # + Vite dev server on :5173
```

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Windy Pro   │────►│ Windy Clone  │────►│  Provider APIs   │
│  (recordings │     │  API + Web   │     │  (ElevenLabs,    │
│   & stats)   │     │  Dashboard   │     │   HeyGen, etc.)  │
└──────────────┘     └──────────────┘     └──────────────────┘
```

- **Frontend**: React 19 + Vite + Tailwind CSS v4
- **Backend**: Python FastAPI + SQLAlchemy (async SQLite)
- **Auth**: JWKS validation against Windy Pro (mock user in dev mode)
- **Providers**: Adapter pattern — one Python class per provider
- **Windy Clone does NOT store audio/video.** It reads from Windy Pro's account-server.

## Port

`8400` (in the Windy ecosystem port allocation)

## Project Structure

```
Windy-Clone/
├── web/                  # React frontend (Vite + Tailwind)
│   └── src/
│       ├── pages/        # Legacy, Discover, Studio, ProviderDetail, MyClones, Settings
│       ├── components/   # StatCard, ReadinessGauge, ProviderCard, CloneCard, etc.
│       ├── hooks/        # useApi, useLegacy, useProviders, useClones
│       └── utils/        # formatDate, formatNumber
├── api/                  # FastAPI backend
│   ├── app/
│   │   ├── auth/         # JWKS validation, CurrentUser dependency
│   │   ├── routes/       # legacy, providers, orders, clones, preferences
│   │   ├── providers/    # ElevenLabs, HeyGen, PlayHT, ResembleAI adapters
│   │   ├── services/     # data_fetcher, readiness, packager, job_tracker
│   │   └── db/           # SQLAlchemy models + engine
│   └── tests/            # pytest async tests
├── deploy/               # nginx.conf, SSL setup
├── scripts/              # dev.sh, seed-providers.py
├── docs/                 # PROVIDER_INTEGRATION.md, USER_JOURNEY.md
└── .github/workflows/    # CI + CD pipelines
```

## Documentation

- [`DNA_STRAND_MASTER_PLAN.md`](DNA_STRAND_MASTER_PLAN.md) — Full architecture, decisions, page designs
- [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) — How Clone connects to other Windy services
- [`docs/PROVIDER_INTEGRATION.md`](docs/PROVIDER_INTEGRATION.md) — How to add a new provider adapter
- [`docs/USER_JOURNEY.md`](docs/USER_JOURNEY.md) — End-to-end user flow documentation
- [`BRAND-ARCHITECTURE.md`](BRAND-ARCHITECTURE.md) — The Windy product family

## Part of the Windy Ecosystem

Windy Clone is one of 8 products in the Windy family. Learn more in `BRAND-ARCHITECTURE.md`.
