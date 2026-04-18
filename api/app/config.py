"""Application configuration from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Project root = two levels up from this file (api/app/config.py → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DB = f"sqlite+aiosqlite:///{_PROJECT_ROOT / 'data' / 'windy_clone.db'}"


class Settings(BaseSettings):
    """All settings loaded from env / .env file."""

    # ── Auth ──
    windy_pro_jwks_url: str = "https://windypro.thewindstorm.uk/.well-known/jwks.json"
    windy_pro_api_url: str = "https://api.windypro.com"
    windy_pro_webhook_secret: str = ""  # HMAC-SHA256 secret for /webhooks/identity/created

    # Optional JWT audience / issuer validation. Leave blank to skip the check
    # (current behavior — Pro has not yet committed to an aud claim for Clone).
    # When set, every inbound JWT must include a matching `aud` / `iss`.
    # Once Pro mints audience-specific tokens, set JWT_AUDIENCE=windy-clone.
    jwt_audience: str = ""
    jwt_issuer: str = ""

    # ── Dashboard ──
    dashboard_url: str = "https://windyclone.com"

    # ── Eternitas (auto-hatch after training completes) ──
    eternitas_url: str = "http://localhost:8500"  # dev default; prod override via env
    eternitas_api_key: str = ""
    eternitas_webhook_secret: str = ""  # HMAC secret for trust.changed webhook
    eternitas_trust_cache_ttl: int = 300  # Fallback TTL when the API omits cache_ttl_seconds
    eternitas_use_mock: bool = False  # True → skip HTTP, treat every agent as top_secret

    # ── Soul file export ──
    soul_signing_key_path: str = str(_PROJECT_ROOT / "data" / "soul_signing_key.pem")
    windy_service_token: str = ""  # Bearer for cross-service soul-file export

    # ── Provider API keys ──
    elevenlabs_api_key: str = ""
    heygen_api_key: str = ""
    playht_api_key: str = ""
    playht_user_id: str = ""
    resembleai_api_key: str = ""

    # ── Database ──
    database_url: str = _DEFAULT_DB

    # ── Server ──
    host: str = "0.0.0.0"
    port: int = 8400
    log_level: str = "info"
    # Prod default carries the public dashboard origin only. Developers
    # extend via CORS_ORIGINS env for their local Vite server.
    cors_origins: str = "https://windyclone.com"
    # Hard ceiling on inbound request bodies. Orders/preferences/webhooks all
    # fit in < 4 KB; 64 KB leaves headroom for future multipart bodies but
    # still rejects obvious abuse (Wave-7 probe accepted a 10 MB body).
    max_request_body_bytes: int = 65_536

    # ── Affiliate tracking ──
    elevenlabs_affiliate_id: str = "windy"
    heygen_affiliate_id: str = "windy"

    # ── Environment + dev mode ──
    # environment drives boot-time safety guards; "development" | "staging" | "production".
    environment: str = "development"
    # dev_mode defaults to False so a prod deploy that forgets to set it gets real auth.
    # Local dev must set DEV_MODE=true explicitly (see .env.example).
    dev_mode: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
