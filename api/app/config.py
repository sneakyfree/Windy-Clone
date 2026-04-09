"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """All settings loaded from env / .env file."""

    # ── Auth ──
    windy_pro_jwks_url: str = "https://windypro.thewindstorm.uk/.well-known/jwks.json"
    windy_pro_api_url: str = "https://api.windypro.com"

    # ── Provider API keys ──
    elevenlabs_api_key: str = ""
    heygen_api_key: str = ""
    playht_api_key: str = ""
    playht_user_id: str = ""
    resembleai_api_key: str = ""

    # ── Database ──
    database_url: str = "sqlite+aiosqlite:///data/windy_clone.db"

    # ── Server ──
    host: str = "0.0.0.0"
    port: int = 8400
    log_level: str = "info"
    cors_origins: str = "https://windyclone.com,http://localhost:5173"

    # ── Affiliate tracking ──
    elevenlabs_affiliate_id: str = "windy"
    heygen_affiliate_id: str = "windy"

    # ── Dev mode ──
    dev_mode: bool = True  # When True, auth is optional and mock data is available

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
