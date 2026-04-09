"""Tests for Order endpoints."""

import pytest


@pytest.mark.anyio
async def test_create_order(client):
    resp = await client.post(
        "/api/v1/orders",
        json={"provider_id": "elevenlabs", "clone_type": "voice"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_id"] == "elevenlabs"
    assert data["clone_type"] == "voice"
    assert data["status"] == "pending"
    assert "order_id" in data


@pytest.mark.anyio
async def test_create_order_invalid_provider(client):
    resp = await client.post(
        "/api/v1/orders",
        json={"provider_id": "nonexistent", "clone_type": "voice"},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_create_order_coming_soon_provider(client):
    resp = await client.post(
        "/api/v1/orders",
        json={"provider_id": "windy-native", "clone_type": "both"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_list_orders(client):
    # Create an order first
    await client.post(
        "/api/v1/orders",
        json={"provider_id": "elevenlabs", "clone_type": "voice"},
    )

    resp = await client.get("/api/v1/orders")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["orders"], list)
    assert data["total"] >= 1


@pytest.mark.anyio
async def test_get_order_detail(client):
    # Create an order
    create_resp = await client.post(
        "/api/v1/orders",
        json={"provider_id": "heygen", "clone_type": "avatar"},
    )
    order_id = create_resp.json()["order_id"]

    # Get detail
    resp = await client.get(f"/api/v1/orders/{order_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == order_id
    assert data["provider_id"] == "heygen"


@pytest.mark.anyio
async def test_cancel_order(client):
    # Create then cancel
    create_resp = await client.post(
        "/api/v1/orders",
        json={"provider_id": "elevenlabs", "clone_type": "voice"},
    )
    order_id = create_resp.json()["order_id"]

    cancel_resp = await client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_cancel_nonexistent_order(client):
    resp = await client.post("/api/v1/orders/nonexistent-id/cancel")
    assert resp.status_code == 404
