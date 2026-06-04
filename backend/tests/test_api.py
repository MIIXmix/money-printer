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


def test_strategy_crud_and_meta():
    headers = _headers()
    # 메타(지표·연산자 목록)
    meta = client.get("/api/strategies/meta", headers=headers)
    assert meta.status_code == 200
    assert len(meta.json()["fields"]) > 10
    assert any(o["value"] == "cross_above" for o in meta.json()["operators"])
    # literal 경로가 /{strategy_id}에 셰도잉되지 않아야 함 (200, not 422)
    assert client.get("/api/strategies/autorun", headers=headers).status_code == 200
    assert client.get("/api/strategies/runs", headers=headers).status_code == 200
    # 생성
    body = {"name": "RSI 반등", "definition": {
        "entry": [{"left": "rsi14", "op": "<", "right": 30}, {"left": "close", "op": ">", "right": "sma60"}],
        "exit": [{"left": "close", "op": "<", "right": "sma20"}],
        "stop_loss_pct": -0.05, "take_profit_pct": 0.1,
    }}
    created = client.post("/api/strategies", json=body, headers=headers)
    assert created.status_code == 200
    sid = created.json()["id"]
    assert created.json()["enabled"] is False
    # 목록
    lst = client.get("/api/strategies", headers=headers)
    assert any(s["id"] == sid for s in lst.json()["strategies"])
    # on/off
    en = client.post(f"/api/strategies/{sid}/enable", json={"enabled": True}, headers=headers)
    assert en.json()["enabled"] is True
    # 수정
    up = client.put(f"/api/strategies/{sid}", json={"name": "RSI 반등 v2"}, headers=headers)
    assert up.json()["name"] == "RSI 반등 v2"
    # 삭제
    assert client.delete(f"/api/strategies/{sid}", headers=headers).status_code == 200
    assert client.get(f"/api/strategies/{sid}", headers=headers).status_code == 404


def test_guest_token_reads_market_but_not_sensitive():
    g = client.post("/api/auth/guest")
    assert g.status_code == 200
    token = g.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    # 읽기전용 시장 데이터 허용
    assert client.get("/api/market/fx", headers=headers).status_code == 200
    assert client.get("/api/market/chart?symbol=AAPL", headers=headers).status_code == 200
    # config-status는 게스트도 200이지만 통합은 전부 미설정(정보 누출 0)
    cfg = client.get("/api/config-status", headers=headers)
    assert cfg.status_code == 200
    assert cfg.json().get("guest") is True
    assert cfg.json().get("geminiConfigured") is False
    # 민감 라우트 거부 (마스터 전용)
    assert client.get("/api/automation/status", headers=headers).status_code == 401
    assert client.get("/api/portfolio/summary", headers=headers).status_code == 401
    assert client.get("/api/api-keys", headers=headers).status_code == 401
    assert client.post("/api/automation/run-once", headers=headers).status_code == 401
