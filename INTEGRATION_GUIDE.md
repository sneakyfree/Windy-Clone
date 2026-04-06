# Windy Clone — Integration Guide

How Windy Clone connects to other products in the Windy ecosystem.

---

## Windy Pro (Account Server) — Data Source

Windy Clone reads ALL recording data from Windy Pro's account-server. It does not have its own recording or storage infrastructure.

### Endpoints Used

| Endpoint | What Clone Gets |
|----------|----------------|
| `GET /api/v1/clone/training-data` | List of training-ready bundles (audio, video, transcript, quality) |
| `GET /api/v1/recordings/stats` | Total hours, word count, quality distribution, session count |
| `POST /api/v1/clone/start-training` | Submit training job (used for Windy Clone Native future) |
| `GET /api/v1/clone/training-status/:jobId` | Poll training status |

### Auth

```
Authorization: Bearer <jwt>
```

JWT issued by Windy Pro login. Clone validates via Windy Pro's JWKS endpoint:
```
GET https://windypro.thewindstorm.uk/.well-known/jwks.json
```

### Data Flow

```
User logs into Windy Pro → JWT issued
    │
    ▼
Windy Clone API receives JWT
    │
    ▼
Validates via JWKS (no separate user DB)
    │
    ▼
Fetches recording stats from Pro's account-server
    │
    ▼
Calculates readiness scores
    │
    ▼
Displays in Legacy Dashboard
```

---

## Windy Cloud — Future Training Backend

When Windy Clone Native launches, training will run on Windy Cloud's GPU compute:

| Endpoint (Future) | What It Does |
|-------------------|-------------|
| `POST /api/v1/compute/clone-training` | Submit audio + video for model training |
| `GET /api/v1/compute/clone-training/{job_id}` | Poll training status |
| `GET /api/v1/storage/files/{model_id}` | Download trained model |

For now, training goes through third-party providers (ElevenLabs, HeyGen, etc.) via their APIs.

---

## Windy Fly (Agent) — Clone Status Queries

Windy Fly agents can check a user's clone status via their existing tool:

```python
# In windy-agent: src/windyfly/tools/windy_api.py
get_clone_status()  # Calls GET /api/v1/clone/training-data
```

Future: Agents will also be able to:
- Recommend providers based on user's data and budget
- Initiate one-button upload on the user's behalf
- Notify the user when their clone is ready

---

## Windy Pro Desktop (Electron) — Embedded Tab

The Windy Clone dashboard is accessible from the Electron app's ecosystem navigation bar (the "Clone" tab, if added). It loads as an embedded webview pointing to `windyclone.com` or `localhost:5173` in development.

The desktop app also has its own clone features (voice-clone-manager.js, clone-data-archive.js) which are the data COLLECTION side. Windy Clone dashboard is the PRESENTATION and MARKETPLACE side.

---

## Windy Pro Mobile — Clone Progress

The mobile app has its own clone tracking (progress ring, milestones, quality scoring). These are the lightweight mobile versions. The full Windy Clone dashboard is accessible via the mobile app's web browser or an embedded webview.

---

## Database Overlap

Windy Clone has its OWN database for:
- Provider orders (which provider, what bundles, status)
- Completed clones (model IDs, provider references)
- User preferences (default provider, notification settings)

Windy Clone does NOT duplicate:
- Recording data (lives in Pro's account-server)
- Audio/video files (live in Pro's local storage or Windy Cloud)
- User accounts (managed by Pro)
- Clone training jobs (the Pro-side ones remain for Windy Clone Native future)
