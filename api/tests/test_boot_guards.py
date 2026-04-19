"""Boot-time safety guards — refuse to boot with unsafe production config."""

import pytest

from app.config import get_settings
from app.main import UnsafeBootConfig, _enforce_boot_guards


@pytest.fixture
def fresh(monkeypatch):
    """Isolate settings mutations from other tests."""
    s = get_settings()
    prior = {
        "environment": s.environment,
        "dev_mode": s.dev_mode,
        "windy_pro_jwks_url": s.windy_pro_jwks_url,
        "windy_pro_api_url": s.windy_pro_api_url,
        "eternitas_url": s.eternitas_url,
        "elevenlabs_api_key": s.elevenlabs_api_key,
    }
    yield s
    for k, v in prior.items():
        setattr(s, k, v)


def test_dev_mode_in_production_refuses_boot(fresh):
    fresh.environment = "production"
    fresh.dev_mode = True
    with pytest.raises(UnsafeBootConfig, match="DEV_MODE=true with ENVIRONMENT=production"):
        _enforce_boot_guards(fresh)


def test_unconfigured_urls_in_production_refuse_boot(fresh):
    fresh.environment = "production"
    fresh.dev_mode = False
    fresh.eternitas_url = "http://localhost:8500"
    with pytest.raises(UnsafeBootConfig, match="ETERNITAS_URL"):
        _enforce_boot_guards(fresh)


def test_placeholder_pro_urls_in_production_refuse_boot(fresh):
    fresh.environment = "production"
    fresh.dev_mode = False
    fresh.windy_pro_jwks_url = "https://windypro.thewindstorm.uk/.well-known/jwks.json"
    fresh.windy_pro_api_url = "https://api.windypro.com"
    fresh.eternitas_url = "https://eternitas.example.com"  # safe placeholder override
    with pytest.raises(UnsafeBootConfig) as exc:
        _enforce_boot_guards(fresh)
    msg = str(exc.value)
    assert "WINDY_PRO_JWKS_URL" in msg
    assert "WINDY_PRO_API_URL" in msg


def test_development_with_dev_mode_boots_with_warning(fresh, caplog):
    fresh.environment = "development"
    fresh.dev_mode = True
    with caplog.at_level("WARNING"):
        _enforce_boot_guards(fresh)
    assert any("DEV_MODE is ON" in r.message for r in caplog.records)


def test_production_with_safe_config_boots(fresh):
    fresh.environment = "production"
    fresh.dev_mode = False
    fresh.windy_pro_jwks_url = "https://auth.windy.example/.well-known/jwks.json"
    fresh.windy_pro_api_url = "https://pro.windy.example"
    fresh.eternitas_url = "https://eternitas.windy.example"
    fresh.elevenlabs_api_key = "sk-live-test"
    _enforce_boot_guards(fresh)  # does not raise


def test_production_without_wired_provider_key_refuses_boot(fresh):
    """Wave-12 M-1 companion guard: every wired provider (not coming_soon)
    must have its API key set in prod, or orders would accept and stall."""
    fresh.environment = "production"
    fresh.dev_mode = False
    fresh.windy_pro_jwks_url = "https://auth.windy.example/.well-known/jwks.json"
    fresh.windy_pro_api_url = "https://pro.windy.example"
    fresh.eternitas_url = "https://eternitas.windy.example"
    fresh.elevenlabs_api_key = ""  # the only wired provider today
    with pytest.raises(UnsafeBootConfig, match="elevenlabs"):
        _enforce_boot_guards(fresh)
