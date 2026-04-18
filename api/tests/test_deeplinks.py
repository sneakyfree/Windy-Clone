"""Tests for the windyclone:// deep-link resolver."""

import pytest


@pytest.mark.anyio
async def test_resolve_dashboard(client):
    resp = await client.get("/api/v1/deeplinks/resolve", params={"url": "windyclone://dashboard"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scheme"] == "windyclone"
    assert body["route"] == "/legacy"
    assert body["params"] == {}


@pytest.mark.anyio
async def test_resolve_discover(client):
    resp = await client.get("/api/v1/deeplinks/resolve", params={"url": "windyclone://discover"})
    assert resp.status_code == 200
    assert resp.json()["route"] == "/discover"


@pytest.mark.anyio
async def test_resolve_studio_with_clone_id(client):
    resp = await client.get(
        "/api/v1/deeplinks/resolve",
        params={"url": "windyclone://studio/abc-123_DEF"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] == "/studio/clone/abc-123_DEF"
    assert body["params"] == {"cloneId": "abc-123_DEF"}


@pytest.mark.anyio
async def test_resolve_order(client):
    resp = await client.get(
        "/api/v1/deeplinks/resolve",
        params={"url": "windyclone://order/ord_42"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] == "/order/ord_42"
    assert body["params"] == {"orderId": "ord_42"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "bad_url",
    [
        "",  # empty
        "windyclone://",  # no target
        "windyclone://unknown",  # unknown head
        "windypro://dashboard",  # wrong scheme
        "http://example.com/dashboard",  # non-windyclone scheme
        "windyclone://dashboard/extra",  # extra segments on a no-arg route
        "windyclone://studio",  # studio without id
        "windyclone://studio/../../etc/passwd",  # path traversal
        "windyclone://studio/a%2Fb",  # url-encoded slash — treated as literal, includes '/'
        "windyclone://order/a/b",  # multi-segment id
        "windyclone://order/bad id",  # space
        "windyclone://order/bad!id",  # disallowed char
        "windyclone://order/" + ("a" * 200),  # over length cap
    ],
)
async def test_resolve_rejects_malformed(client, bad_url):
    resp = await client.get("/api/v1/deeplinks/resolve", params={"url": bad_url})
    assert resp.status_code == 400, f"expected 400 for {bad_url!r}, got {resp.status_code}: {resp.text}"


@pytest.mark.anyio
async def test_resolve_case_insensitive_head(client):
    # Scheme and the head segment are normalised — but IDs are not.
    resp = await client.get(
        "/api/v1/deeplinks/resolve",
        params={"url": "WINDYCLONE://Dashboard"},
    )
    assert resp.status_code == 200
    assert resp.json()["route"] == "/legacy"


@pytest.mark.anyio
async def test_resolve_strips_query_like_frontend(client):
    # Both parsers strip ?/# before matching — agents that append tracking
    # params to a deep link still get a clean resolve instead of a 400.
    resp = await client.get(
        "/api/v1/deeplinks/resolve",
        params={"url": "windyclone://order/ok?ref=sms"},
    )
    assert resp.status_code == 200
    assert resp.json()["route"] == "/order/ok"
