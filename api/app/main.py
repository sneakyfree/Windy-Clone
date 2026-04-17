"""FastAPI application factory — Windy Clone API."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.engine import init_db
from .routes import health, legacy, providers, orders, clones, preferences, webhooks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = get_settings()

    # Initialize database tables
    await init_db()

    if settings.eternitas_use_mock:
        logger.warning(
            "🚨 ETERNITAS_USE_MOCK=true — every agent is treated as TOP_SECRET. "
            "Useful in CI when Eternitas isn't reachable; catastrophic in prod."
        )

    # Log startup
    print(f"🌊 Windy Clone API starting on :{settings.port}")
    print(f"   JWKS URL: {settings.windy_pro_jwks_url}")
    print(f"   Pro API:  {settings.windy_pro_api_url}")
    print(f"   Dev mode: {settings.dev_mode}")
    print(f"   Eternitas mock: {settings.eternitas_use_mock}")

    yield

    print("🌊 Windy Clone API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Windy Clone API",
        description="Digital twin marketplace — turn your recordings into voice clones, avatars, and soul files.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ──
    app.include_router(health.router)
    app.include_router(legacy.router, prefix="/api/v1/legacy", tags=["Legacy"])
    app.include_router(providers.router, prefix="/api/v1/providers", tags=["Providers"])
    app.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders"])
    app.include_router(clones.router, prefix="/api/v1/clones", tags=["Clones"])
    app.include_router(preferences.router, prefix="/api/v1/preferences", tags=["Preferences"])
    app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])

    return app


app = create_app()
