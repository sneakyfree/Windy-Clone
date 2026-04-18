"""FastAPI application factory — Windy Clone API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings, get_settings
from .db.engine import init_db
from .middleware.rate_limit import RateLimitMiddleware
from .routes import health, legacy, providers, orders, clones, preferences, webhooks
from .services.order_reaper import reap_orphaned_orders

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


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose declared Content-Length exceeds the configured cap.

    Wave-7 probe accepted a 10 MB JSON body on POST /api/v1/orders. Every
    endpoint on this service has a body that fits in a few KB; reject
    anything beyond the configured ceiling up front with 413.

    Clients that omit Content-Length (chunked) slip this check — uvicorn's
    own limits handle the truly unbounded case. This is the declared-size
    fast path, not the full defence.
    """

    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                size = int(cl)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
            if size > self._max_bytes:
                logger.warning(
                    "rejected oversized body on %s %s: %d bytes > %d max",
                    request.method, request.url.path, size, self._max_bytes,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body too large ({size} bytes). "
                                  f"Max is {self._max_bytes} bytes."
                    },
                )
        return await call_next(request)

logger = logging.getLogger(__name__)


# SQLite "database is locked" and "attempt to write a readonly database" both
# surface as OperationalError. On PostgreSQL, transient contention surfaces
# as OperationalError too (deadlock, serialization failure). In all cases we
# want the client to back off and retry, not to see an opaque 500.
_TRANSIENT_DB_MARKERS = (
    "database is locked",
    "attempt to write a readonly database",
    "deadlock detected",
    "could not serialize",
)


async def db_transient_handler(request: Request, exc: OperationalError) -> JSONResponse:
    msg = str(exc).lower()
    if any(marker in msg for marker in _TRANSIENT_DB_MARKERS):
        logger.warning(
            "transient DB error on %s %s — returning 503: %s",
            request.method, request.url.path, str(exc).splitlines()[0],
        )
        return JSONResponse(
            status_code=503,
            content={"detail": "Service temporarily busy. Please retry."},
            headers={"Retry-After": "1"},
        )
    # Re-raise anything we don't recognise so FastAPI's default 500 path runs.
    raise exc


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

    # Sweep orders orphaned by a previous task's shutdown. Runs before we
    # start accepting requests, so there's no concurrent writer on Order.status.
    try:
        reaped = await reap_orphaned_orders()
        if reaped:
            print(f"🧹 Reaped {len(reaped)} orphaned order(s) into PENDING")
    except Exception:
        # Reaper failure must not block startup — log and continue.
        logger.exception("reaper failed on startup")

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

    # Convert transient DB contention into 503 Retry-After instead of 500.
    app.add_exception_handler(OperationalError, db_transient_handler)

    # Middleware execution order: Starlette dispatches outermost-added first.
    # Rate-limit first (429 is cheap), then body-size (413 before body read),
    # then CORS. Both preempt CORS so rejected requests don't burn preflight.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)

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
