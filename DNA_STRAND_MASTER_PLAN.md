# DNA_STRAND_MASTER_PLAN.md — Windy Clone

**Version:** 0.1.0
**Created:** 2026-04-06
**Last Updated:** 2026-04-06
**Authors:** Grant Whitmer + Claude Opus 4.6
**Philosophy:** Your voice lives forever. One dashboard to turn your recordings into a digital twin — voice clone, avatar, soul file — through the best providers in the world, or eventually through us.

---

## TERMINOLOGY STANDARD

| Internal Term | User-Facing Term | Meaning |
|---------------|-----------------|---------|
| `windy_identity_id` | Windy Account | Cross-product UUID from Windy Pro account-server |
| Provider | Clone Studio | Third-party service that trains voice/avatar models |
| Bundle | Recording Session | A collection of audio/video/transcript from one capture |
| Training job | Clone Training | The process of creating a voice/avatar model |
| Soul file | Soul File | The complete digital identity archive |
| Voice clone | Voice Twin | A synthesized voice that sounds like the user |
| Avatar | Digital Avatar | A video likeness that looks and moves like the user |
| Clone readiness | Legacy Score | 0-100% progress toward having enough data for a quality clone |
| Provider marketplace | Clone Studio | The shopping experience for clone providers |
| Export bundle | Data Package | ZIP of audio + video + text for a provider |

---

## VISION

Windy Clone is the **bridge between "I've been recording" and "I have a digital twin."**

Every Windy Word user is silently building a treasure trove of voice data, video data, and text. Most don't know it. Windy Clone is the moment they realize what they've built — and the one-button path to turning it into something immortal.

### The Three-Part Experience

1. **Your Voice Legacy** (Education + Progress)
   - Show users what they've accumulated — hours of voice, minutes of video, thousands of words
   - Explain what a voice clone and digital avatar ARE, in plain human language
   - Track readiness: "You're 73% of the way to a studio-quality voice clone"
   - Educate through emotion, not jargon: "Your grandchildren will hear YOUR voice read them a bedtime story"

2. **Clone Studio** (Provider Marketplace)
   - Side-by-side comparison of voice clone and avatar providers
   - ElevenLabs, HeyGen, PlayHT, Synthesia, D-ID, Resemble.AI, Tavus, Coqui
   - Transparent pricing, quality ratings, turnaround times, sample demos
   - Featured spot for "Windy Clone Native" (coming — our own training pipeline)
   - Run specials, promotions, seasonal deals

3. **One-Button Upload** (Seamless Data Transfer)
   - User picks a provider, hits ONE button
   - We package their audio/video/text into the provider's required format
   - Upload directly via provider API — no ZIP files, no manual steps
   - Track training progress in real time
   - Preview and test the finished clone right in the dashboard

### The Grandma Test

When a 70-year-old non-technical user opens Windy Clone for the first time:
- She should understand what this is within 10 seconds
- She should feel EXCITED, not confused
- She should see her own data and feel the weight of what she's built
- She should be able to get a voice clone created with zero technical knowledge
- The word "API" should never appear. The word "bundle" should never appear.

### The Business Model

- **Affiliate/referral fees** from providers (10-30% per transaction)
- **API markup** if we proxy through our backend (provider costs $5, we charge $8)
- **Windy Clone Native** (future) — our own training pipeline, highest margin
- **Premium features** — priority training, extended storage, multi-provider comparison

---

## ECOSYSTEM CONTEXT

Windy Clone sits at the END of the user journey — it's the payoff for everything else:

```
Windy Word (captures voice + text)
    ↓
Windy Pro Mobile (captures on the go)
    ↓
Windy Cloud (stores everything long-term)
    ↓
    ↓ ← ALL of this data flows here
    ↓
╔══════════════════════════════════════╗
║          WINDY CLONE                  ║
║  "Your recordings become immortal"   ║
║                                      ║
║  ┌────────┐  ┌────────┐  ┌────────┐ ║
║  │ Voice  │  │Digital │  │ Soul   │ ║
║  │ Twin   │  │Avatar  │  │ File   │ ║
║  └────────┘  └────────┘  └────────┘ ║
║         ↓         ↓         ↓        ║
║  ┌──────────────────────────────┐    ║
║  │    Provider Marketplace      │    ║
║  │  ElevenLabs │ HeyGen │ ...  │    ║
║  └──────────────────────────────┘    ║
╚══════════════════════════════════════╝
```

### What Already Exists (Built in Other Repos)

| Component | Location | What It Does | Status |
|-----------|----------|-------------|--------|
| Voice recording | windy-pro desktop | Records voice samples, Clone Capture mode | Complete |
| Video recording | windy-pro desktop | Video + phone camera bridge (WebRTC) | Complete |
| Quality scoring | windy-pro-mobile | SNR, clipping, noise detection, 4-tier grading | Complete |
| Progress tracking | windy-pro-mobile | 10-hour weighted threshold, milestones, haptics | Complete |
| Bundle creation | windy-pro-mobile | Standardized bundles (audio+video+transcript+metadata) | Complete |
| Clone Data Archive | windy-pro desktop | Browse, filter, bulk export bundles | Complete |
| ZIP export | windy-pro main.js | Audio + CSV manifest + README (ElevenLabs-compatible) | Complete |
| Soul File page | windy-pro web | Archive viewer for clone capture sessions | Complete |
| ClonePanel widget | windy-pro web | Dashboard widget (hours, quality, readiness) | Complete |
| Training API | windy-pro account-server | POST start-training, GET status (graceful fallback) | Scaffolded |
| DB schema | windy-pro account-server | clone_training_jobs table, recording clone fields | Complete |
| Agent integration | windy-agent | get_clone_status() tool | Complete |

### What This Repo Builds (NEW)

| Component | What It Does |
|-----------|-------------|
| **Legacy Dashboard** | Shows user their data, readiness, emotional education |
| **Provider Marketplace** | Compare, shop, select clone providers |
| **One-Button Upload** | Package + send data to provider APIs |
| **Training Tracker** | Poll provider APIs, show real-time progress |
| **Clone Preview** | Test finished clones (play audio, view avatar) |
| **Provider API adapters** | ElevenLabs, HeyGen, PlayHT, etc. integrations |

### Auth Flow

```
User → Windy Pro (login) → JWT with windy_identity_id
                                    │
                                    ▼
                            Windy Clone API
                            validates via JWKS
                            at Pro's /.well-known/jwks.json
                                    │
                                    ▼
                            Fetches user's recording data
                            from Pro's account-server
                            GET /api/v1/clone/training-data
                            GET /api/v1/recordings/stats
```

---

## CRITICAL PATH TO MVP

```
Phase 0 (Now)              Phase 1 (Week 1-2)         Phase 2 (Week 3-4)
──────────────────         ──────────────────         ──────────────────
Repo skeleton        ───►  Legacy Dashboard     ───►  Provider Marketplace
DNA Strand                 Data visualization          Provider cards
CLAUDE.md                  Readiness scoring           Pricing comparison
React + Vite setup         Educational content         Sample demos
API skeleton               Pull data from Pro          Provider detail pages

Phase 3 (Month 2)          Phase 4 (Month 2-3)        Phase 5 (Month 3+)
──────────────────         ──────────────────         ──────────────────
Provider Adapters    ───►  One-Button Upload     ───►  Windy Clone Native
ElevenLabs adapter         Format conversion           Own training pipeline
HeyGen adapter             Direct API upload           GPU compute on Cloud
PlayHT adapter             Progress tracking           In-house voice synth
                           Clone preview/test          In-house avatar gen
```

**What blocks what:**
1. Auth middleware (JWKS validation) blocks everything
2. Account-server data fetch blocks Legacy Dashboard
3. Legacy Dashboard blocks Provider Marketplace (need to show readiness first)
4. Provider API adapters block One-Button Upload
5. Windy Cloud compute blocks Windy Clone Native

---

## CONFIRMED TECHNICAL DECISIONS

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Frontend | **React 19 + TypeScript + Vite** | Matches windy-chat and windy-cloud dashboards |
| 2 | Styling | **Tailwind CSS** | Matches ecosystem, fast iteration |
| 3 | Backend | **Python / FastAPI** | Python-first ecosystem, matches Cloud/Agent |
| 4 | Auth | **JWKS from Windy Pro** | No separate login |
| 5 | Data source | **Windy Pro account-server API** | Don't duplicate — fetch from existing endpoints |
| 6 | Provider adapters | **Python adapter classes (Protocol pattern)** | Swappable, testable, one per provider |
| 7 | Database | **SQLite (dev) / PostgreSQL (prod)** | Track orders, provider jobs, preferences |
| 8 | Container | **Docker + docker-compose** | Consistent with ecosystem |
| 9 | Port | **8400** | Fits ecosystem port allocation |
| 10 | Domain | **windyclone.com** | Per BRAND-ARCHITECTURE.md |

---

## TECH STACK

| Component | Technology | Why |
|-----------|-----------|-----|
| Frontend | React 19 + TypeScript + Vite | Ecosystem consistency |
| Styling | Tailwind CSS | Fast, utility-first |
| Router | React Router 7 | Client-side routing |
| Icons | Lucide React | Clean, consistent |
| Backend | FastAPI + Uvicorn | Async, auto-docs |
| HTTP client | httpx | Async HTTP for provider APIs |
| Auth | PyJWT + cryptography | JWKS validation |
| Database | SQLAlchemy + aiosqlite | Metadata, orders, jobs |
| Testing | pytest + Vitest | Backend + frontend |
| Container | Docker | Deployment |

---

## CRITICAL INVARIANTS

1. **Windy Clone never stores raw audio/video.** It fetches from Windy Pro's account-server or Windy Cloud. Clone is a dashboard, not a storage service.
2. **Auth is always via Windy Pro JWKS.** No separate login.
3. **Providers are swappable.** Adding a new provider = one new adapter class. No route changes.
4. **One-button means ONE button.** The user should never see a file picker, a format dropdown, or an upload progress bar for individual files. They pick a provider and hit go.
5. **Education before sales.** The Legacy Dashboard (free, informative) always comes before the Marketplace (transactional).
6. **No jargon in the UI.** "Recording Session" not "bundle." "Legacy Score" not "clone readiness percentage." "Voice Twin" not "voice clone model."
7. **Provider data stays fresh.** Pricing, features, and availability are fetched from providers or a config file — never hardcoded in UI components.
8. **The grandma test applies to EVERY screen.** If a non-technical person can't understand the screen in 5 seconds, redesign it.
9. **Clone data belongs to the user.** They can export, download, or delete at any time. We never lock them into a provider.
10. **Agent-friendly.** Windy Fly should be able to check clone status, recommend providers, and initiate training on behalf of the user.

---

## DASHBOARD PAGES

### Page 1: Your Voice Legacy (Home)

The emotional entry point. What the user sees first.

**Top section — The Story:**
> "Every time you spoke into Windy Word, you were building something extraordinary."

**Data visualization:**
- Total words spoken (large number, animated count-up)
- Hours of audio recorded
- Minutes of video captured
- Number of recording sessions

**Readiness gauges (warm, organic feel — not loading bars):**
```
Voice Twin Readiness
████████████░░░  82%
"A few more sessions and your voice can live forever"

Digital Avatar Readiness
████░░░░░░░░░░░  28%
"Record more video — your avatar needs to see more of you"

Soul File Completeness
██████████░░░░░  67%
"Your digital identity is taking shape"
```

**Quality indicator:**
- "Your recordings are crystal clear" (if quality is high)
- "Try recording in a quieter room for better results" (if quality is mixed)

**CTA:** "See What's Possible" → scrolls to Discover section or navigates to page 2

### Page 2: Discover (Education)

What CAN your data become? Three immersive cards:

**Voice Twin**
- Explanation in plain language
- Audio demo (play a sample clone)
- "Your grandchildren hear a bedtime story in YOUR voice"
- Use cases: audiobooks, voicemails, messages from beyond

**Digital Avatar**
- Explanation in plain language
- Video demo (play a sample avatar)
- "A video of you, saying things you never recorded"
- Use cases: holiday greetings, birthday messages, presentations

**Soul File**
- Explanation in plain language
- Visual of the archive
- "Your complete digital identity — voice, face, vocabulary, personality"
- Use cases: future AI companions, digital memorial, family legacy

### Page 3: Clone Studio (Provider Marketplace)

**Filter bar:** Voice Clones | Avatars | All-in-One

**Provider cards (sortable by price, quality, speed):**

Each card shows:
- Provider logo + name
- What they do (voice / avatar / both)
- Quality rating (stars)
- Starting price
- Turnaround time
- "View Details" → expands to full comparison
- **"Send My Data"** button (primary CTA)

**Featured provider (top of page):**
> "Windy Clone Native — Coming Soon. Zero data leaves the ecosystem. Built by us."

**Provider detail page (on click):**
- Full feature list
- Pricing tiers
- Sample gallery (listen/watch demos)
- User reviews (future)
- Compatibility check ("You have enough data for this provider's standard plan")
- **"Send My Data to [Provider]"** → one button

### Page 4: My Clones (Status + Preview)

**Active training jobs:**
- Provider name + type (voice/avatar)
- Progress bar with status text
- Estimated completion time
- Cancel button

**Completed clones:**
- Play button (voice) / Watch button (avatar)
- Text input to test voice clone ("Type anything and hear it in your voice")
- Download button
- Share button (future)
- "Retrain" option

**Export section:**
- "Download All My Data" (full archive as ZIP)
- "Delete All My Data" (with confirmation)

### Page 5: Settings

- Default provider preference
- Notification preferences (email when clone is ready)
- Data privacy settings
- Connected accounts (which Windy products are feeding data)
- Provider API keys (for users who want to use their own accounts)

---

## PROVIDER ADAPTER DESIGN

```python
class CloneProvider(Protocol):
    """Interface for voice clone / avatar providers."""

    name: str
    provider_type: str  # "voice" | "avatar" | "both"

    async def get_pricing(self) -> list[PricingTier]: ...

    async def check_compatibility(self, data_stats: DataStats) -> CompatibilityResult:
        """Check if the user has enough data for this provider."""
        ...

    async def prepare_upload(self, bundles: list[Bundle]) -> PreparedPackage:
        """Convert bundles to the provider's required format."""
        ...

    async def upload(self, package: PreparedPackage) -> UploadResult:
        """Send data to the provider. Returns job ID."""
        ...

    async def get_training_status(self, job_id: str) -> TrainingStatus: ...

    async def get_result(self, job_id: str) -> CloneResult:
        """Fetch the finished clone (audio model / avatar)."""
        ...

    async def preview(self, model_id: str, text: str) -> bytes:
        """Generate a preview (TTS audio or avatar video)."""
        ...
```

### Initial Providers

| Provider | Type | API | Priority |
|----------|------|-----|----------|
| **ElevenLabs** | Voice | REST API (well-documented) | P0 — first adapter |
| **HeyGen** | Avatar | REST API | P0 — first avatar adapter |
| **PlayHT** | Voice | REST API | P1 |
| **Resemble.AI** | Voice | REST API | P1 |
| **Synthesia** | Avatar | REST API | P2 |
| **D-ID** | Avatar | REST API | P2 |
| **Tavus** | Avatar + Voice | REST API | P2 |
| **Coqui** | Voice (open source) | Local / API | P3 |
| **Windy Clone Native** | Both | Internal | Future |

---

## API DESIGN

### Clone Dashboard Endpoints

```
GET    /api/v1/legacy/stats           User's recording stats (proxied from Pro)
GET    /api/v1/legacy/readiness       Voice/avatar/soul readiness scores
GET    /api/v1/legacy/timeline        Recording history timeline
```

### Provider Marketplace Endpoints

```
GET    /api/v1/providers              List all providers with pricing
GET    /api/v1/providers/{id}         Provider detail (features, demos, pricing)
GET    /api/v1/providers/{id}/compat  Check user's data compatibility
```

### Upload & Training Endpoints

```
POST   /api/v1/orders                 Create order (provider + bundles)
GET    /api/v1/orders                 List user's orders
GET    /api/v1/orders/{id}            Order detail + training status
POST   /api/v1/orders/{id}/cancel     Cancel order
```

### Clone Preview Endpoints

```
GET    /api/v1/clones                 List user's completed clones
POST   /api/v1/clones/{id}/preview    Generate preview (TTS text → audio)
GET    /api/v1/clones/{id}/download   Download clone model/assets
DELETE /api/v1/clones/{id}            Delete clone
```

### Health

```
GET    /health                        Health check
```

---

## FILE INDEX (Target State)

```
windy-clone/
├── DNA_STRAND_MASTER_PLAN.md       # This file — the blueprint
├── CLAUDE.md                        # Claude Code quick-start
├── BRAND-ARCHITECTURE.md            # Windy family (shared doc)
├── README.md                        # What is this? Quick start.
├── INTEGRATION_GUIDE.md             # How Clone connects to Pro, Cloud, Agent
├── pyproject.toml                   # Python project config
├── Dockerfile                       # Production container
├── docker-compose.yml               # Local dev stack
├── .env.example                     # Required env vars
├── .github/
│   └── workflows/
│       ├── ci.yml                   # Lint + test on PR
│       └── deploy.yml               # Build + push container
├── api/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── config.py                # Settings from env
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── jwks.py              # JWKS fetcher + JWT validator
│   │   │   └── dependencies.py      # FastAPI auth dependencies
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # CloneProvider protocol
│   │   │   ├── elevenlabs.py        # ElevenLabs voice clone adapter
│   │   │   ├── heygen.py            # HeyGen avatar adapter
│   │   │   ├── playht.py            # PlayHT voice clone adapter
│   │   │   ├── resembleai.py        # Resemble.AI adapter
│   │   │   └── registry.py          # Provider registry (lookup by ID)
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── legacy.py            # /api/v1/legacy/* — stats, readiness
│   │   │   ├── providers.py         # /api/v1/providers/* — marketplace
│   │   │   ├── orders.py            # /api/v1/orders/* — upload + training
│   │   │   ├── clones.py            # /api/v1/clones/* — preview + download
│   │   │   └── health.py            # /health
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── data_fetcher.py      # Fetch recording data from Pro
│   │   │   ├── readiness.py         # Calculate voice/avatar/soul readiness
│   │   │   ├── packager.py          # Convert bundles to provider format
│   │   │   └── job_tracker.py       # Poll provider APIs for status
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── engine.py            # SQLAlchemy async engine
│   │       └── models.py            # Orders, clones, preferences
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_legacy.py
│       ├── test_providers.py
│       └── test_orders.py
├── web/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── public/
│   │   └── favicon.ico
│   └── src/
│       ├── App.tsx                   # Router + layout
│       ├── main.tsx                  # Entry point
│       ├── index.css                 # Tailwind imports
│       ├── pages/
│       │   ├── Legacy.tsx            # Your Voice Legacy (home)
│       │   ├── Discover.tsx          # What can your clone do?
│       │   ├── Studio.tsx            # Provider marketplace
│       │   ├── ProviderDetail.tsx    # Single provider detail
│       │   ├── MyClones.tsx          # Status + preview
│       │   └── Settings.tsx          # Preferences
│       ├── components/
│       │   ├── Layout.tsx            # Nav sidebar + header
│       │   ├── ReadinessGauge.tsx    # Animated progress gauge
│       │   ├── StatCard.tsx          # Big number stat display
│       │   ├── ProviderCard.tsx      # Marketplace provider card
│       │   ├── CloneCard.tsx         # Completed clone card
│       │   ├── TrainingProgress.tsx  # Active training job
│       │   └── AudioDemo.tsx         # Playable audio sample
│       ├── hooks/
│       │   ├── useApi.ts             # API client
│       │   ├── useLegacy.ts          # Fetch legacy stats
│       │   └── useProviders.ts       # Fetch provider data
│       └── assets/
│           └── ...                   # Images, icons
├── deploy/
│   ├── nginx.conf
│   └── scripts/
│       └── setup-ssl.sh
├── docs/
│   ├── PROVIDER_INTEGRATION.md      # How to add a new provider
│   └── USER_JOURNEY.md              # UX flow documentation
└── scripts/
    ├── dev.sh                       # Start dev servers
    └── seed-providers.py            # Seed provider data
```

---

## ENVIRONMENT VARIABLES

```bash
# === Required ===
# Auth
WINDY_PRO_JWKS_URL=https://windypro.thewindstorm.uk/.well-known/jwks.json
WINDY_PRO_API_URL=https://api.windypro.com

# === Provider API Keys ===
ELEVENLABS_API_KEY=your-elevenlabs-key
HEYGEN_API_KEY=your-heygen-key
PLAYHT_API_KEY=your-playht-key
PLAYHT_USER_ID=your-playht-user-id
RESEMBLEAI_API_KEY=your-resembleai-key

# === Optional ===
# Database (defaults to SQLite for dev)
DATABASE_URL=sqlite+aiosqlite:///data/windy_clone.db

# Server
HOST=0.0.0.0
PORT=8400
LOG_LEVEL=info
CORS_ORIGINS=https://windyclone.com,https://windypro.thewindstorm.uk

# Affiliate tracking
ELEVENLABS_AFFILIATE_ID=windy
HEYGEN_AFFILIATE_ID=windy
```

---

## DEPLOYMENT

### Target Infrastructure

- **VPS:** Hostinger at `72.60.118.54` (shared with other services)
- **Port:** 8400
- **Domain:** `windyclone.com`
- **Reverse proxy:** Nginx
- **SSL:** Let's Encrypt via certbot

### Port Allocation (Ecosystem)

| Service | Port |
|---------|------|
| Windy Pro Account Server | 3456 |
| Windy Chat | 8100-8108 |
| Windy Mail | 8025/8080 |
| Windy Cloud | 8200 |
| Eternitas | 8300 |
| **Windy Clone** | **8400** |

---

## WHAT THE FRESH TERMINAL SHOULD BUILD FIRST

Priority order for implementation:

1. **`web/`** — React + Vite + Tailwind scaffold with routing
2. **`web/src/pages/Legacy.tsx`** — The emotional home page with data visualization
3. **`web/src/pages/Discover.tsx`** — Education cards (voice twin, avatar, soul file)
4. **`web/src/pages/Studio.tsx`** — Provider marketplace with cards
5. **`api/app/main.py`** — FastAPI app with CORS, lifespan
6. **`api/app/auth/`** — JWKS validation from Windy Pro
7. **`api/app/services/data_fetcher.py`** — Pull recording stats from Pro
8. **`api/app/services/readiness.py`** — Calculate readiness scores
9. **`api/app/routes/legacy.py`** — Stats + readiness endpoints
10. **`api/app/routes/providers.py`** — Provider listing + detail
11. **`api/app/providers/elevenlabs.py`** — First real provider adapter
12. **`api/app/providers/heygen.py`** — First avatar provider adapter
13. **`api/app/routes/orders.py`** — Upload + training flow
14. **`web/src/pages/MyClones.tsx`** — Training status + preview
15. **Docker + deploy** — Containerization and production deployment

Build the frontend FIRST. The dashboard should look and feel right before wiring up backends. Use mock data for providers and stats during frontend development.

---

## RELATIONSHIP TO EXISTING CLONE CODE

Windy Clone does NOT replace the clone features in Windy Pro. Here's how they relate:

| Concern | Windy Pro | Windy Clone |
|---------|-----------|-------------|
| **Recording** | Captures voice/video/text | Does NOT record — reads Pro's data |
| **Storage** | Stores bundles locally + account-server | Does NOT store media — fetches from Pro |
| **Quality scoring** | Scores recordings, tracks readiness | Displays readiness in a pretty dashboard |
| **Export** | ZIP export for manual upload | Replaced by one-button upload to providers |
| **Training API** | Scaffolded (graceful fallback) | Owns the training flow via provider adapters |
| **UI (desktop)** | Voice Clone Manager, Clone Data Archive | Links to Windy Clone dashboard |
| **UI (mobile)** | Clone progress ring, milestones | Links to Windy Clone dashboard |

**The handoff:** Windy Pro collects and stores data. Windy Clone presents it beautifully and connects it to providers. The Electron app's Clone tab and the mobile app's clone screen should link to the Windy Clone dashboard (embedded webview or browser).

---

## THE WINDY CLONE NATIVE FUTURE

Eventually, Windy Clone will have its own training pipeline:

1. User's data stays in the Windy ecosystem (Windy Cloud storage)
2. Training runs on Windy Cloud GPU compute
3. Voice synthesis served from Windy Cloud
4. Avatar generation on Windy Cloud
5. Zero data leaves the ecosystem
6. Featured at the top of the marketplace as the recommended option
7. Highest margin (no third-party costs)

This is Phase 5+. Build the marketplace first, prove demand, then build the native pipeline.
