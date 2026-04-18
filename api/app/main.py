"""FastAPI application factory — Windy Clone API."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .db.engine import init_db
from .routes import health, legacy, providers, orders, clones, preferences, webhooks

logger = logging.getLogger(__name__)


# URL prefixes that indicate an unconfigured default. If any of these match
# while ENVIRONMENT=production + DEV_MODE=false, we refuse to boot — the
# alternative is silently running with auth/trust pointing at dead endpoints.
_UNSAFE_URL_MARKERS = (
    "localhost",
    "127.0.0.1",
    "windypro.thewindstorm.uk",  # known 404 placeholder
    "eternitas.thewindstorm.uk",  # known unreachable placeholder
    "api.windypro.com",  # known non-resolving placeholder
)


class UnsafeBootConfig(RuntimeError):
    """Raised when the current Settings would produce an insecure prod deploy."""


def _enforce_boot_guards(settings: Settings) -> None:
    """Abort or warn on config that's unsafe for the current environment.

    Rules:
      - ENVIRONMENT=production AND DEV_MODE=true → abort (auth bypass).
      - ENVIRONMENT=production AND a critical URL is still a known placeholder
        → abort (auth / trust gating will silently fail).
      - DEV_MODE=true in any environment → WARN loudly.
    """
    env = (settings.environment or "development").lower()

    if env == "production" and settings.dev_mode:
        raise UnsafeBootConfig(
            "DEV_MODE=true with ENVIRONMENT=production — authentication would be "
            "silently bypassed. Set DEV_MODE=false before deploying."
        )

    if env == "production":
        critical = {
            "WINDY_PRO_JWKS_URL": settings.windy_pro_jwks_url,
            "WINDY_PRO_API_URL": settings.windy_pro_api_url,
            "ETERNITAS_URL": settings.eternitas_url,
        }
        unsafe = {
            name: url
            for name, url in critical.items()
            if any(marker in url for marker in _UNSAFE_URL_MARKERS)
        }
        if unsafe:
            lines = "\n".join(f"  - {n}={u}" for n, u in unsafe.items())
            raise UnsafeBootConfig(
                f"ENVIRONMENT=production but these URLs are still unconfigured "
                f"defaults:\n{lines}\n"
                f"Override them in the environment before deploying."
            )

    if settings.dev_mode:
        logger.warning(
            "🚨 DEV_MODE is ON — JWT validation failures fall through to a mock "
            "user. NEVER run this way in production (env=%s).",
            env,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = get_settings()

    _enforce_boot_guards(settings)

    # Initialize database tables
    await init_db()

    if settings.eternitas_use_mock:
        logger.warning(
            "🚨 ETERNITAS_USE_MOCK=true — every agent is treated as TOP_SECRET. "
            "Useful in CI when Eternitas isn't reachable; catastrophic in prod."
        )

    # Log startup
    print(f"🌊 Windy Clone API starting on :{settings.port}")
    print(f"   Environment: {settings.environment}")
    print(f"   JWKS URL: {settings.windy_pro_jwks_url}")
    print(f"   Pro API:  {settings.windy_pro_api_url}")
    print(f"   Dev mode: {settings.dev_mode}")
    print(f"   Eternitas mock: {settings.eternitas_use_mock}")

    yield

    print("🌊 Windy Clone API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    # Only expose OpenAPI / Swagger / Redoc in dev. In prod, the schema
    # leak is minor on its own but pointless surface area.
    doc_urls = {
        "docs_url": "/docs" if settings.dev_mode else None,
        "redoc_url": "/redoc" if settings.dev_mode else None,
        "openapi_url": "/openapi.json" if settings.dev_mode else None,
    }

    app = FastAPI(
        title="Windy Clone API",
        description="Digital twin marketplace — turn your recordings into voice clones, avatars, and soul files.",
        version="0.1.0",
        lifespan=lifespan,
        **doc_urls,
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
