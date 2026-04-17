"""Minimal in-process rate limiter — per-IP sliding window.

Wave-7 gap analysis: no rate limits anywhere means any unauthenticated
attacker can force SHA-256 HMAC on /webhooks/* indefinitely, or spam
/orders. This middleware stops the obvious abuse at the edge.

Scope:
  - In-memory. Every ECS task has its own view — an attacker can get
    Nx the limit across N tasks. Acceptable for v1; migrate to Redis when
    task count > 2 or when Grant OKs the infra.
  - Per-IP only. Authenticated rate limiting needs CurrentUser which
    isn't available in a pre-routing middleware. Follow-up issue.
  - Sliding window with timestamp list — O(1) amortised per request.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rule:
    """A single rate-limit rule.

    `prefix` is matched against `request.url.path`; the first matching rule
    wins. Use `""` as a catch-all.
    """
    prefix: str
    requests: int
    window_seconds: int
    label: str  # Human-readable bucket name for logs / Retry-After decisions


# Ordered — first-match-wins. Specific prefixes before the catch-all.
_DEFAULT_RULES: tuple[Rule, ...] = (
    Rule(prefix="/health", requests=0, window_seconds=0, label="unlimited"),
    Rule(prefix="/api/v1/webhooks", requests=30, window_seconds=60, label="webhooks"),
    Rule(prefix="/api/v1/orders", requests=10, window_seconds=60, label="orders"),
    Rule(prefix="/api/v1/clones", requests=30, window_seconds=60, label="clones"),
    Rule(prefix="/api/v1/", requests=120, window_seconds=60, label="general"),
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter.

    Hits over the cap → 429 with Retry-After (seconds until the oldest
    in-window request expires). Logged at WARN.
    """

    def __init__(self, app, rules: tuple[Rule, ...] = _DEFAULT_RULES):
        super().__init__(app)
        self._rules = rules
        # (ip, label) → list[monotonic_timestamp], oldest first.
        self._buckets: dict[tuple[str, str], list[float]] = defaultdict(list)

    def _match_rule(self, path: str) -> Rule | None:
        for rule in self._rules:
            if path.startswith(rule.prefix):
                return rule
        return None

    def _client_ip(self, request: Request) -> str:
        # Starlette populates request.client.host with the peer IP. If we're
        # behind a trusted reverse proxy, prefer X-Forwarded-For's leftmost
        # entry. (Trust decision lives at the ALB config, not here.)
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        rule = self._match_rule(request.url.path)
        if rule is None or rule.requests == 0:
            return await call_next(request)

        now = time.monotonic()
        window_start = now - rule.window_seconds
        ip = self._client_ip(request)
        key = (ip, rule.label)

        # Drop timestamps that have fallen out of the window.
        stamps = self._buckets[key]
        while stamps and stamps[0] < window_start:
            stamps.pop(0)

        if len(stamps) >= rule.requests:
            retry_after = max(1, int(rule.window_seconds - (now - stamps[0])))
            logger.warning(
                "rate-limit: ip=%s bucket=%s over cap (%d in %ds) — 429 retry-after=%ds",
                ip, rule.label, rule.requests, rule.window_seconds, retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": f"Too many requests. Retry in {retry_after}s."},
                headers={"Retry-After": str(retry_after)},
            )

        stamps.append(now)
        return await call_next(request)

    # Test hook — tests pin state by wiping the buckets between runs.
    def _reset(self) -> None:
        self._buckets.clear()
