"""Regression tests for P1 #3: non-JSON upstream responses must not crash.

Wave-7 chaos probe fed each upstream client an HTML body and all three raised
an uncaught json.JSONDecodeError. Every request on the dependent route then
500'd. Broadening the `except` to include ValueError (the base class of
JSONDecodeError) makes them degrade gracefully.
"""

import httpx
import pytest

from app.config import get_settings
from app.services import data_fetcher, eternitas, trust_client
from app.services.eternitas import EternitasHatchError
from app.services.trust_client import TrustLevel


def _patch_httpx(module, monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real = module.httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return real(*a, **kw)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


@pytest.fixture
def live_settings(monkeypatch):
    """Force every client out of its dev-mode / mock short-circuit."""
    s = get_settings()
    monkeypatch.setattr(s, "dev_mode", False)
    monkeypatch.setattr(s, "eternitas_use_mock", False)
    trust_client.reset_cache()
    return s


def _html_handler(request):
    return httpx.Response(200, content=b"<html>not json</html>", headers={"content-type": "text/html"})


@pytest.mark.anyio
async def test_data_fetcher_stats_tolerates_non_json(monkeypatch, live_settings):
    _patch_httpx(data_fetcher, monkeypatch, _html_handler)
    result = await data_fetcher.fetch_recording_stats("id-a", jwt_token="t", db=None)
    # No cache + malformed upstream → unavailable (not a 500).
    assert result.unavailable is True
    assert result.stats.total_words == 0


@pytest.mark.anyio
async def test_data_fetcher_bundles_tolerates_non_json(monkeypatch, live_settings):
    _patch_httpx(data_fetcher, monkeypatch, _html_handler)
    result = await data_fetcher.fetch_training_bundles("id-b", jwt_token="t", db=None)
    assert result.unavailable is True
    assert result.bundles == []


@pytest.mark.anyio
async def test_trust_client_tolerates_non_json(monkeypatch, live_settings):
    _patch_httpx(trust_client, monkeypatch, _html_handler)
    level = await trust_client.get_agent_trust("ET26-HTML")
    # Fail-closed on parse error (same as network error).
    assert level is TrustLevel.UNVERIFIED


@pytest.mark.anyio
async def test_eternitas_auto_hatch_raises_clean_error_on_non_json(monkeypatch, live_settings):
    _patch_httpx(eternitas, monkeypatch, _html_handler)
    with pytest.raises(EternitasHatchError):
        await eternitas.auto_hatch(
            identity_id="x",
            provider_id="elevenlabs",
            provider_model_id="v",
            clone_type="voice",
            display_name="X",
        )
