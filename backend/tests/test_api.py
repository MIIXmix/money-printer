from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

_PASSWORD = "master-pass-123"  # set up by conftest.py


def _token() -> str:
    status = client.get("/api/auth/status").json()
    if not status["initialized"]:
        resp = client.post("/api/auth/setup", json={"password": _PASSWORD})
        assert resp.status_code == 200
        return resp.json()["token"]
    resp = client.post("/api/auth/login", json={"password": _PASSWORD})
    assert resp.status_code == 200
    return resp.json()["token"]


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


def test_health_minimal():
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    # Must NOT leak security/config recon to unauthenticated callers.
    assert "securityWarnings" not in body
    assert "geminiConfigured" not in body


def test_gated_route_requires_auth():
    # Entire app behind login: a data route must reject anonymous access.
    resp = client.get("/api/market/fx")
    assert resp.status_code == 401


def test_setup_then_gated_access():
    headers = _headers()
    universe = client.get(
        "/api/market/korea/universe?market=KOSPI&limit=5&source=snapshot", headers=headers
    )
    assert universe.status_code == 200
    data = universe.json()
    assert data["status"] in {"delayed", "not_available"}


def test_settings_roundtrip_allowlisted():
    headers = _headers()
    payload = {"value": {"panels": {"left": 280, "right": 360}}}
    saved = client.put("/api/settings/layout", json=payload, headers=headers)
    assert saved.status_code == 200
    loaded = client.get("/api/settings/layout", headers=headers)
    assert loaded.status_code == 200
    assert loaded.json()["value"]["panels"]["left"] == 280


def test_settings_unknown_key_rejected():
    headers = _headers()
    resp = client.put("/api/settings/evil", json={"value": {"x": 1}}, headers=headers)
    assert resp.status_code == 404


def test_dart_requires_auth_and_reports_status():
    # Without a token → 401 (gated).
    assert client.get("/api/filings/dart").status_code == 401
    # With a token but no DART key configured → api_required (not a crash).
    resp = client.get("/api/filings/dart", headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] in {"api_required", "delayed", "not_available", "error"}


def test_dart_corp_code_validation():
    headers = _headers()
    resp = client.get("/api/filings/dart?corp_code=not8digits", headers=headers)
    assert resp.status_code == 422
