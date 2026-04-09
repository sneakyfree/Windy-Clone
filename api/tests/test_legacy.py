"""Tests for Legacy endpoints."""

import pytest


@pytest.mark.anyio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "windy-clone-api"


@pytest.mark.anyio
async def test_legacy_stats(client):
    resp = await client.get("/api/v1/legacy/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert data["stats"]["total_words"] > 0
    assert data["stats"]["hours_audio"] > 0


@pytest.mark.anyio
async def test_legacy_readiness(client):
    resp = await client.get("/api/v1/legacy/readiness")
    assert resp.status_code == 200
    data = resp.json()
    readiness = data["readiness"]
    assert 0 <= readiness["voice_twin"]["percentage"] <= 100
    assert 0 <= readiness["digital_avatar"]["percentage"] <= 100
    assert 0 <= readiness["soul_file"]["percentage"] <= 100
    assert readiness["voice_twin"]["message"]  # non-empty


@pytest.mark.anyio
async def test_legacy_timeline(client):
    resp = await client.get("/api/v1/legacy/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    assert len(data["bundles"]) > 0
