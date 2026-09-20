import asyncio
import httpx
import pytest
from computer.api import create_app, ORIGIN


@pytest.fixture
async def client(tmp_path):
    app = create_app(tmp_path, "test-pairing-token")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=ORIGIN, headers={"Origin": ORIGIN}
    ) as c:
        yield c, app.state.runtime
    await app.state.runtime.close()


async def test_auth_origin_and_host(client):
    c, rt = client
    assert (await c.get("/api/state")).status_code == 401
    assert (await c.post("/api/login", json={"token": "wrong"})).status_code == 401
    assert (
        await c.post(
            "/api/login", json={"token": "test-pairing-token"}, headers={"Origin": "https://evil.test"}
        )
    ).status_code == 403
    assert (await c.get("/", headers={"Host": "evil.test"})).status_code == 403
    r = await c.post("/api/login", json={"token": "test-pairing-token"})
    assert r.status_code == 200 and "HttpOnly" in r.headers["set-cookie"]
    assert (await c.get("/api/state")).status_code == 200


async def test_stop_while_request_runs_and_provider_change(client):
    c, rt = client
    await c.post("/api/login", json={"token": "test-pairing-token"})
    out = await c.post("/api/message", json={"text": "/execute"})
    rid = out.json()["run"]
    for _ in range(100):
        state = (await c.get("/api/state")).json()
        if state["pending"]:
            break
        await asyncio.sleep(0.01)
    assert state["pending"]
    assert (
        await c.post("/api/provider", json={"kind": "local", "model": "qwen2.5:1.5b", "temperature": 0.2})
    ).status_code == 400
    assert (await c.post(f"/api/run/{rid}/stop", json={})).status_code == 200
    assert not (await c.get("/api/state")).json()["pending"]
    assert (
        await c.post("/api/provider", json={"kind": "local", "model": "qwen2.5:1.5b", "temperature": 0.2})
    ).status_code == 200
    assert (
        await c.post("/api/provider", json={"kind": "local", "base_url": "https://evil.test"})
    ).status_code == 422


async def test_bridge_token_cannot_approve_or_read_session(client):
    c, rt = client
    await c.post("/api/login", json={"token": "test-pairing-token"})
    token = (await c.post("/api/bridge/pair", json={})).json()["token"]
    c.cookies.clear()
    h = {"Authorization": "Bearer " + token}
    assert (await c.get("/api/state", headers=h)).status_code == 401
    assert (
        await c.post("/api/bridge/tab", json={"title": "Example", "url": "https://example.com"}, headers=h)
    ).status_code == 200
    assert (
        await c.post("/api/bridge/tab", json={"title": "Local", "url": "file:///tmp/foo"}, headers=h)
    ).status_code == 400


async def test_malformed_and_size(client):
    c, rt = client
    assert (
        await c.post("/api/login", content="{", headers={"Content-Type": "application/json"})
    ).status_code == 422
    assert (await c.post("/api/login", json={"token": "x" * 310000})).status_code == 413
