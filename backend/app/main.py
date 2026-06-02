from __future__ import annotations

import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    change_master,
    create_token,
    encrypt_secret,
    get_api_key,
    is_initialized,
    mask_secret,
    require_auth,
    setup_master,
    verify_master,
)
from .config import settings
from .db import get_db, init_db, json_dumps, json_loads, row_to_dict
from .services.ai import analyze
from .services.brokers import providers
from .services.filings import dart_filings, sec_filings
from .services.market_data import (
    equity_calendar,
    fx_rates,
    historical_chart,
    korea_universe,
    market_heatmap,
    market_overview,
    options_chain,
    quotes,
    search_symbols,
)
from .services.kis import KisError, inquire_balance, submit_order
from .services.news import get_news
from .services.portfolio import list_holdings, portfolio_summary


def _warm_caches() -> None:
    """Pre-load slow caches in the background so first use is instant:
    - KOSPI/KOSDAQ universe (Korean company-name search; cold ~20s)
    - Sector heatmaps (KOSPI/NASDAQ100; cold ~10-15s each)
    Refreshes every 25 min, before the 30-min caches expire."""
    import time as _time

    from .services.market_data import korea_universe, market_heatmap

    while True:
        for market in ("KOSPI", "KOSDAQ"):
            try:
                korea_universe(market, limit=1)
            except Exception:
                pass
        for hm in ("KOSPI", "NASDAQ100"):
            try:
                market_heatmap(hm)
            except Exception:
                pass
        _time.sleep(25 * 60)  # refresh before the 30-min caches expire


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    import threading

    threading.Thread(target=_warm_caches, daemon=True).start()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# Bearer tokens are sent in the Authorization header, not cookies, so credentials
# are not needed. Methods are restricted to the verbs actually used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'",
    )
    return response


# ── Request models ─────────────────────────────────────────────────────────


class SetupIn(BaseModel):
    password: str = Field(min_length=8, max_length=256)


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


_ALLOWED_SETTING_KEYS = {"layout", "prefs", "onboarding"}
_MAX_SETTING_BYTES = 64 * 1024


class SettingIn(BaseModel):
    value: dict[str, Any]


class ApiKeyIn(BaseModel):
    provider: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    label: str = Field(default="default", max_length=64)
    value: str = Field(min_length=4, max_length=512)


class HoldingIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    name: str = Field(default="", max_length=128)
    quantity: float = Field(gt=0)
    average_cost: float = Field(ge=0)
    currency: str = Field(default="USD", max_length=8)
    market: str = Field(default="US", max_length=8)
    sector: str = Field(default="", max_length=64)
    country: str = Field(default="", max_length=64)
    target_weight: float | None = Field(default=None, ge=0, le=100)


class PaperOrderIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    limit_price: float | None = Field(default=None, ge=0)


class AiAnalyzeIn(BaseModel):
    payload: dict[str, Any]


class KisCredentialIn(BaseModel):
    appkey: str = Field(min_length=8, max_length=128)
    appsecret: str = Field(min_length=8, max_length=256)
    account_no: str = Field(min_length=8, max_length=24)


class KisOrderIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    limit_price: float | None = Field(default=None, ge=0)


# ── Login throttle (defense-in-depth against local brute force) ─────────────

_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW = 300.0  # seconds
_LOGIN_MAX = 8


def _throttle_login(client: str) -> None:
    now = time.time()
    # Evict fully-expired buckets so the dict can't grow without bound.
    for key in [k for k, v in _LOGIN_ATTEMPTS.items() if all(now - t >= _LOGIN_WINDOW for t in v)]:
        _LOGIN_ATTEMPTS.pop(key, None)
    hits = [t for t in _LOGIN_ATTEMPTS.get(client, []) if now - t < _LOGIN_WINDOW]
    if len(hits) >= _LOGIN_MAX:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too_many_attempts")
    hits.append(now)
    _LOGIN_ATTEMPTS[client] = hits


def _clear_login(client: str) -> None:
    _LOGIN_ATTEMPTS.pop(client, None)


# ── Health & auth ──────────────────────────────────────────────────────────


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/auth/status")
def auth_status() -> dict[str, Any]:
    return {"initialized": is_initialized()}


@app.get("/api/config-status")
def config_status(_user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    # Authenticated-only: tells the UI which optional integrations are active.
    return {
        "geminiConfigured": get_api_key("gemini") is not None,
        "dartConfigured": get_api_key("dart") is not None,
        "liveTradingEnabled": settings.live_trading_enabled,
    }


@app.post("/api/auth/setup")
def auth_setup(payload: SetupIn) -> dict[str, Any]:
    user = setup_master(payload.password)
    return {"token": create_token(user), "status": "initialized"}


@app.post("/api/auth/login")
def auth_login(payload: LoginIn, request: Request) -> dict[str, Any]:
    client = request.client.host if request.client else "local"
    _throttle_login(client)
    user = verify_master(payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    _clear_login(client)
    return {"token": create_token(user), "status": "ok"}


@app.post("/api/auth/change-password")
def auth_change_password(payload: ChangePasswordIn, _user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    user = change_master(payload.current_password, payload.new_password)
    # New token reflects the bumped version; old tokens are now invalid.
    return {"token": create_token(user), "status": "changed"}


# ── Market data (gated) ────────────────────────────────────────────────────


@app.get("/api/market/overview")
def api_market_overview(_user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return market_overview()


@app.get("/api/market/quotes")
def api_quotes(
    symbols: str = Query(default="AAPL,MSFT,NVDA,005930.KS,SPY,QQQ", max_length=512),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return {"quotes": quotes(symbols.split(","))}


@app.get("/api/market/korea/universe")
def api_korea_universe(
    market: str = Query(default="KOSPI", pattern="^(KOSPI|KOSDAQ|ALL|kospi|kosdaq|all)$"),
    query: str = Query(default="", max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    source: str = Query(default="auto", pattern="^(auto|naver|snapshot)$"),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return korea_universe(market=market, query=query, limit=limit, source=source)


@app.get("/api/market/chart")
def api_chart(
    symbol: str = Query(default="AAPL", max_length=24),
    period: str = Query(default="1Y", max_length=8),
    interval: str = Query(default="1D", max_length=8),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return historical_chart(symbol, period, interval)


@app.get("/api/market/heatmap")
def api_heatmap(
    market: str = Query(default="NASDAQ100", pattern="^(NASDAQ100|KOSPI|nasdaq100|kospi)$"),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return market_heatmap(market)


@app.get("/api/market/search")
def api_search(
    q: str = Query(default="", max_length=64),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return search_symbols(q)


@app.get("/api/market/fx")
def api_fx(_user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return fx_rates()


@app.get("/api/market/calendar")
def api_calendar(
    symbol: str = Query(default="AAPL", max_length=24),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return equity_calendar(symbol)


@app.get("/api/options")
def api_options(
    symbol: str = Query(default="AAPL", max_length=24),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return options_chain(symbol)


@app.get("/api/news")
async def api_news(
    symbol: str = Query(default="AAPL", max_length=24),
    query: str = Query(default="", max_length=64),
    limit: int = Query(default=12, ge=1, le=30),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return await get_news(symbol, query, limit)


@app.get("/api/filings/sec")
async def api_sec(
    symbol: str = Query(default="AAPL", max_length=24),
    limit: int = Query(default=12, ge=1, le=30),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    return await sec_filings(symbol, limit)


@app.get("/api/filings/dart")
async def api_dart(
    corp_code: str | None = Query(default=None, max_length=8),
    symbol: str | None = Query(default=None, max_length=24),
    limit: int = Query(default=12, ge=1, le=30),
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    if corp_code is not None and not re.fullmatch(r"\d{8}", corp_code):
        raise HTTPException(status_code=422, detail="corp_code must be 8 digits")
    return await dart_filings(corp_code=corp_code, symbol=symbol, limit=limit)


# ── User settings (gated, allowlisted) ─────────────────────────────────────


@app.get("/api/settings/{key}")
def get_setting(key: str, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    if key not in _ALLOWED_SETTING_KEYS:
        raise HTTPException(status_code=404, detail="unknown_setting")
    with get_db() as con:
        row = con.execute("SELECT value_json FROM user_settings WHERE user_id = ? AND key = ?", (user["id"], key)).fetchone()
    return {"key": key, "value": json_loads(row["value_json"], {}) if row else {}}


@app.put("/api/settings/{key}")
def put_setting(key: str, payload: SettingIn, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    if key not in _ALLOWED_SETTING_KEYS:
        raise HTTPException(status_code=404, detail="unknown_setting")
    blob = json_dumps(payload.value)
    if len(blob.encode("utf-8")) > _MAX_SETTING_BYTES:
        raise HTTPException(status_code=413, detail="setting_too_large")
    with get_db() as con:
        con.execute(
            """
            INSERT INTO user_settings(user_id, key, value_json, updated_at)
            VALUES(?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP
            """,
            (user["id"], key, blob),
        )
    return {"key": key, "value": payload.value, "status": "saved"}


# ── API keys (gated) ───────────────────────────────────────────────────────


@app.get("/api/api-keys")
def list_api_keys(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    with get_db() as con:
        rows = con.execute(
            "SELECT id, provider, label, masked_value, created_at, updated_at FROM api_keys WHERE user_id = ? ORDER BY provider",
            (user["id"],),
        ).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}


@app.post("/api/api-keys")
def save_api_key(payload: ApiKeyIn, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    encrypted = encrypt_secret(payload.value)
    provider = payload.provider.lower()
    with get_db() as con:
        # One key per provider: replace any existing so the latest takes effect.
        con.execute("DELETE FROM api_keys WHERE user_id = ? AND lower(provider) = ?", (user["id"], provider))
        cursor = con.execute(
            """
            INSERT INTO api_keys(user_id, provider, label, encrypted_value, masked_value)
            VALUES(?, ?, ?, ?, ?)
            """,
            (user["id"], provider, payload.label, encrypted, mask_secret(payload.value)),
        )
    return {"id": cursor.lastrowid, "provider": provider, "label": payload.label, "masked": mask_secret(payload.value)}


@app.delete("/api/api-keys/{key_id}")
def delete_api_key(key_id: int, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    with get_db() as con:
        con.execute("DELETE FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user["id"]))
    return {"status": "deleted", "id": key_id}


# ── Portfolio (gated) ──────────────────────────────────────────────────────


@app.get("/api/portfolio/holdings")
def holdings(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return {"items": list_holdings(user["id"])}


@app.post("/api/portfolio/holdings")
def create_holding(payload: HoldingIn, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    symbol = payload.symbol.upper()
    market = payload.market.upper()
    with get_db() as con:
        existing = con.execute(
            "SELECT id, quantity, average_cost FROM holdings WHERE user_id = ? AND symbol = ? AND market = ?",
            (user["id"], symbol, market),
        ).fetchone()
        if existing:
            # 같은 종목 재매수 → 수량 합산 + 가중평균 평단
            old_qty = float(existing["quantity"])
            old_avg = float(existing["average_cost"])
            add_qty = float(payload.quantity)
            total_qty = old_qty + add_qty
            new_avg = (
                (old_qty * old_avg + add_qty * float(payload.average_cost)) / total_qty
                if total_qty
                else float(payload.average_cost)
            )
            con.execute(
                """
                UPDATE holdings
                SET quantity = ?, average_cost = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                (total_qty, new_avg, existing["id"], user["id"]),
            )
            return {"status": "merged", "id": existing["id"]}
        cursor = con.execute(
            """
            INSERT INTO holdings(user_id, symbol, name, quantity, average_cost, currency, market, sector, country, target_weight)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                symbol,
                payload.name,
                payload.quantity,
                payload.average_cost,
                payload.currency.upper(),
                market,
                payload.sector,
                payload.country,
                payload.target_weight,
            ),
        )
    return {"status": "created", "id": cursor.lastrowid}


@app.put("/api/portfolio/holdings/{holding_id}")
def update_holding(holding_id: int, payload: HoldingIn, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    with get_db() as con:
        con.execute(
            """
            UPDATE holdings
            SET symbol = ?, name = ?, quantity = ?, average_cost = ?, currency = ?, market = ?,
                sector = ?, country = ?, target_weight = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (
                payload.symbol.upper(),
                payload.name,
                payload.quantity,
                payload.average_cost,
                payload.currency.upper(),
                payload.market.upper(),
                payload.sector,
                payload.country,
                payload.target_weight,
                holding_id,
                user["id"],
            ),
        )
    return {"status": "updated", "id": holding_id}


@app.delete("/api/portfolio/holdings/{holding_id}")
def delete_holding(holding_id: int, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    with get_db() as con:
        con.execute("DELETE FROM holdings WHERE id = ? AND user_id = ?", (holding_id, user["id"]))
    return {"status": "deleted", "id": holding_id}


@app.get("/api/portfolio/summary")
def summary(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return portfolio_summary(user["id"])


# ── Brokers / orders (gated) ───────────────────────────────────────────────


@app.get("/api/brokers")
def broker_providers(_user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return {
        "liveTradingEnabled": settings.live_trading_enabled,
        "safety": "기본은 Paper Trading입니다. 실거래는 LIVE_TRADING_ENABLED=true 및 사용자별 명시 설정 없이는 실행하지 않습니다.",
        "providers": providers(),
    }


@app.post("/api/orders/paper")
def create_paper_order(payload: PaperOrderIn, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    with get_db() as con:
        cursor = con.execute(
            """
            INSERT INTO paper_orders(user_id, symbol, side, quantity, order_type, limit_price, mode, status, note)
            VALUES(?, ?, ?, ?, ?, ?, 'paper', 'accepted_paper', ?)
            """,
            (
                user["id"],
                payload.symbol.upper(),
                payload.side,
                payload.quantity,
                payload.order_type,
                payload.limit_price,
                "모의 주문입니다. 실제 브로커로 전송되지 않았습니다.",
            ),
        )
    return {"status": "accepted_paper", "id": cursor.lastrowid, "mode": "paper"}


@app.post("/api/orders/live")
def create_live_order(_: PaperOrderIn, _user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    if not settings.live_trading_enabled:
        raise HTTPException(status_code=403, detail="live_trading_disabled")
    raise HTTPException(status_code=501, detail="broker_live_adapter_not_configured")


# ── AI (gated; uses the user's own key) ────────────────────────────────────


@app.post("/api/ai/analyze")
async def api_ai(payload: AiAnalyzeIn, _user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return await analyze(payload.payload)


# ── KIS 모의투자 (한국투자증권 OpenAPI, paper only) ─────────────────────────


@app.get("/api/kis/status")
def kis_status(_user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return {"configured": get_api_key("kis") is not None, "mode": "mock"}


@app.post("/api/kis/credential")
def kis_save_credential(payload: KisCredentialIn, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    blob = json_dumps({"appkey": payload.appkey, "appsecret": payload.appsecret, "account_no": payload.account_no})
    encrypted = encrypt_secret(blob)
    with get_db() as con:
        con.execute("DELETE FROM api_keys WHERE user_id = ? AND lower(provider) = 'kis'", (user["id"],))
        con.execute(
            "INSERT INTO api_keys(user_id, provider, label, encrypted_value, masked_value) VALUES(?, 'kis', ?, ?, ?)",
            (user["id"], "KIS 모의투자", encrypted, mask_secret(payload.appkey)),
        )
    return {"status": "saved", "provider": "kis"}


@app.delete("/api/kis/credential")
def kis_delete_credential(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    with get_db() as con:
        con.execute("DELETE FROM api_keys WHERE user_id = ? AND lower(provider) = 'kis'", (user["id"],))
    return {"status": "deleted"}


@app.post("/api/orders/kis")
async def kis_order(payload: KisOrderIn, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    cred = get_api_key("kis")
    if not cred:
        raise HTTPException(status_code=424, detail="kis_credential_required")
    try:
        result = await submit_order(
            cred,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            order_type=payload.order_type,
            limit_price=payload.limit_price,
        )
    except KisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # 모의 주문 이력 기록
    with get_db() as con:
        con.execute(
            """
            INSERT INTO paper_orders(user_id, symbol, side, quantity, order_type, limit_price, mode, status, note)
            VALUES(?, ?, ?, ?, ?, ?, 'kis_mock', 'accepted_kis_mock', ?)
            """,
            (
                user["id"],
                payload.symbol.upper(),
                payload.side,
                payload.quantity,
                payload.order_type,
                payload.limit_price,
                f"KIS 모의 주문번호 {result.get('orderNo') or '-'}",
            ),
        )
    return result


@app.get("/api/kis/balance")
async def kis_balance(_user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    cred = get_api_key("kis")
    if not cred:
        raise HTTPException(status_code=424, detail="kis_credential_required")
    try:
        return await inquire_balance(cred)
    except KisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Static frontend ────────────────────────────────────────────────────────


def _static_index() -> Path:
    return settings.static_dir / "index.html"


if settings.static_dir.exists():
    app.mount("/assets", StaticFiles(directory=settings.static_dir / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str) -> FileResponse:
    if full_path:
        root = settings.static_dir.resolve()
        try:
            target = (settings.static_dir / full_path).resolve()
        except Exception:
            target = root
        # Containment guard: never serve files outside the static dir.
        if target != root and root in target.parents and target.is_file():
            return FileResponse(target)
    index = _static_index()
    if index.exists():
        # index.html points to hash-named bundles; never cache it so the browser
        # always picks up the latest build (hashed assets stay long-cacheable).
        return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(status_code=404, detail="frontend_not_built")
