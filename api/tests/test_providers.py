"""Tests for Provider endpoints."""

import pytest


@pytest.mark.anyio
async def test_list_all_providers(client):
    resp = await client.get("/api/v1/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 8
    names = [p["name"] for p in data["providers"]]
    assert "ElevenLabs" in names
    assert "HeyGen" in names
    assert "Windy Clone Native" in names


@pytest.mark.anyio
async def test_list_voice_providers(client):
    resp = await client.get("/api/v1/providers?type=voice")
    assert resp.status_code == 200
    data = resp.json()
    for p in data["providers"]:
        assert p["provider_type"] == "voice"


@pytest.mark.anyio
async def test_list_avatar_providers(client):
    resp = await client.get("/api/v1/providers?type=avatar")
    assert resp.status_code == 200
    data = resp.json()
    for p in data["providers"]:
        assert p["provider_type"] == "avatar"


@pytest.mark.anyio
async def test_get_provider_detail(client):
    resp = await client.get("/api/v1/providers/elevenlabs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"]["name"] == "ElevenLabs"
    assert data["provider"]["provider_type"] == "voice"


@pytest.mark.anyio
async def test_get_unknown_provider(client):
    resp = await client.get("/api/v1/providers/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_compatibility_check(client):
    resp = await client.get("/api/v1/providers/elevenlabs/compat")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == "elevenlabs"
    assert isinstance(data["compatible"], bool)
    assert "data_summary" in data
