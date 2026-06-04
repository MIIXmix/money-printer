"""자동전략 오케스트레이터. run_once가 엔진→리스크→배분→페이퍼브로커를 순서대로
통과시킨다. 실제 브로커/실전 주문은 절대 호출하지 않는다."""

from __future__ import annotations

import asyncio
from typing import Any

from ..auth import get_api_key
from ..services import kis
from ..services.market_data import historical_chart, usd_to_krw
from . import allocator, broker, config, engine, performance, risk, store, universe


def broker_mode(user_id: int) -> str:
    """'paper_internal'(기본, 내부 sim) | 'kis_mock'(KIS 모의계좌 백엔드)."""
    m = store.get_settings_raw(user_id).get("broker_mode")
    return m if m in ("paper_internal", "kis_mock") else "paper_internal"


def active_engine(user_id: int) -> str:
    """동시에 한 엔진만 계좌 장부를 움직인다(레이스 방지).

    'builder' = 사용자 전략 빌더 (run_strategies_once) — 내부 sim·KIS 모두 지원. 기본.
    'legacy'  = 고정 모멘텀+랭킹 자동전략 (run_once).
    broker_mode(internal/kis)는 두 엔진 모두 따른다.
    """
    e = store.get_settings_raw(user_id).get("engine")
    return e if e in ("legacy", "builder") else "builder"


def _kis_balances() -> tuple[dict, dict] | None:
    """KIS 국내+해외 모의 잔고를 함께 읽는다(읽기전용). 키 없거나 실패 시 None."""
    cred = get_api_key("kis")
    if not cred:
        return None

    async def _gather() -> tuple[dict, dict]:
        dom = await kis.inquire_balance(cred)
        try:
            ovs = await kis.inquire_overseas_balance(cred, exchange="NASD")
        except kis.KisError:
            ovs = {"holdings": [], "totalEvalPnl": 0.0, "buyAmountUsd": 0.0}
        return dom, ovs

    try:
        return asyncio.run(_gather())
    except Exception:
        return None


def _kis_status(user_id: int) -> dict[str, Any]:
    """KIS 모의 잔고(국내 KRW + 해외 USD)를 합쳐 status 형식으로 반환.

    손익은 KIS가 보고한 값을 그대로 쓴다(임의 baseline 불필요). 해외는 fx로 환산.
    """
    acct = store.ensure_account(user_id)
    fx = usd_to_krw()
    res = _kis_balances()
    if res is None:
        # KIS 미연결 — 내부 모드로 폴백 표시
        out = status_internal(user_id)
        out["brokerMode"] = "kis_mock"
        out["kisError"] = "KIS 잔고 조회 실패 — 자격증명/네트워크 확인"
        return out
    dom, ovs = res
    dom_cash = float(dom.get("cash") or 0.0)
    dom_total = float(dom.get("netAsset") or (dom_cash))
    dom_pnl = float(dom.get("totalPnl") or 0.0)

    positions: list[dict] = []
    pos_val = 0.0
    for h in dom.get("holdings", []):
        v = float(h.get("evalAmount") or 0.0)
        pos_val += v
        positions.append({
            "symbol": h.get("symbol"), "quantity": h.get("quantity"), "currency": "KRW",
            "price": h.get("currentPrice"), "valueKrw": round(v, 0),
            "avgCostNative": h.get("avgPrice"), "dataStatus": "live",
        })
    ovs_pnl_usd = 0.0
    for h in ovs.get("holdings", []):
        ev_usd = float(h.get("evalAmount") or 0.0)
        v_krw = ev_usd * (fx or 0.0)
        pos_val += v_krw
        ovs_pnl_usd += float(h.get("pnl") or 0.0)
        positions.append({
            "symbol": h.get("symbol"), "quantity": h.get("quantity"), "currency": "USD",
            "price": h.get("currentPrice"), "valueKrw": round(v_krw, 0),
            "avgCostNative": h.get("avgPrice"), "dataStatus": "live",
        })
    ovs_pnl_krw = (float(ovs.get("totalEvalPnl") or ovs_pnl_usd)) * (fx or 0.0)
    # dom_total(netAsset)은 국내 현금+보유 포함. 해외 보유 KRW만 더한다.
    dom_val_krw = sum(p["valueKrw"] for p in positions if p["currency"] == "KRW")
    ovs_val_krw = sum(p["valueKrw"] for p in positions if p["currency"] == "USD")
    total = dom_total + ovs_val_krw
    pnl = dom_pnl + ovs_pnl_krw
    cost_basis = total - pnl
    cum = (pnl / cost_basis) if cost_basis else None
    return {
        "status": acct["status"],
        "halted": bool(acct["halted"]),
        "haltReason": acct["halt_reason"],
        "brokerMode": "kis_mock",
        "seedKrw": round(cost_basis, 0),       # KIS 보고 손익 기준 원가
        "cashKrw": round(dom_cash, 0),         # 국내 KRW 예수금(해외 USD 예수금 별도)
        "positionsValueKrw": round(dom_val_krw + ovs_val_krw, 0),
        "totalValueKrw": round(total, 0),
        "cumReturn": round(cum, 4) if cum is not None else None,
        "dailyReturn": None,
        "drawdown": None,
        "positions": positions,
        "fxUsdKrw": round(fx, 2) if fx else None,
        "limits": risk.limits_snapshot(),
        "paperOnly": True,
        "liveTradingImplemented": False,
        "promotionEligible": False,
        "kisNote": "KIS 모의계좌 잔고(국내 KRW + 해외 USD 환산). 해외 USD 예수금 별도. "
                   "⚠ KIS 모드 매매는 공식 30일 검증(promotion)에 집계되지 않습니다 — 내부 sim 장부만 대상.",
        "recentSignals": store.recent_signals(user_id, 12),
        "recentOrders": store.recent_orders(user_id, 12),
        "riskEvents": store.recent_risk_events(user_id, 10),
    }


def _market_currency(symbol: str) -> tuple[str, str]:
    s = symbol.upper()
    if s.endswith((".KS", ".KQ")):
        return "KR", "KRW"
    return "US", "USD"


def _to_krw(amount_native: float, currency: str, fx: float | None) -> float | None:
    if currency == "KRW":
        return amount_native
    if fx is None:
        return None
    return amount_native * fx


def _chart(symbol: str) -> dict[str, Any]:
    # 1Y/1D: SMA120까지 계산 가능한 충분한 봉 + 차트 캐시(60초) 재사용.
    try:
        return historical_chart(symbol, "1Y", "1D")
    except Exception as exc:
        return {"points": [], "status": "error", "message": type(exc).__name__}


def _last_price(points: list[dict]) -> float | None:
    p = engine.last_real_point(points)
    return p.get("close") if p else None


def _positions_value(user_id: int, fx: float | None) -> tuple[float, list[dict], str]:
    """보유 평가액(KRW) + 마크 정보 + 최악 데이터상태."""
    positions = store.list_positions(user_id)
    total = 0.0
    marks: list[dict] = []
    worst = "live"
    for pos in positions:
        ch = _chart(pos["symbol"])
        status = ch.get("status") or "not_available"
        price = _last_price(ch.get("points") or [])
        val_krw = None
        if price is not None:
            val_krw = _to_krw(price * float(pos["quantity"]), pos["currency"], fx)
        if val_krw is not None:
            total += val_krw
        else:
            worst = "not_available"
        if risk.is_delayed(status) and worst != "not_available":
            worst = "delayed"
        marks.append({
            "symbol": pos["symbol"], "quantity": pos["quantity"], "currency": pos["currency"],
            "price": price, "valueKrw": round(val_krw, 0) if val_krw is not None else None,
            "avgCostNative": pos["avg_cost_native"], "dataStatus": status,
        })
    return total, marks, worst


def status(user_id: int) -> dict[str, Any]:
    """broker_mode에 따라 내부 sim 또는 KIS 모의 잔고 기반 상태를 반환."""
    if broker_mode(user_id) == "kis_mock":
        return _kis_status(user_id)
    out = status_internal(user_id)
    out["brokerMode"] = "paper_internal"
    return out


def status_internal(user_id: int) -> dict[str, Any]:
    acct = store.ensure_account(user_id)
    fx = usd_to_krw()
    pos_val, marks, _ = _positions_value(user_id, fx)
    cash = float(acct["cash_krw"])
    total = cash + pos_val
    seed = float(acct["seed_krw"])
    peak = max(float(acct["peak_value_krw"]), total)
    snaps = store.all_snapshots(user_id)
    prev_total = float(snaps[-1]["total_value_krw"]) if snaps else seed
    daily_return = (total - prev_total) / prev_total if prev_total else None
    return {
        "status": acct["status"],
        "halted": bool(acct["halted"]),
        "haltReason": acct["halt_reason"],
        "seedKrw": seed,
        "cashKrw": round(cash, 0),
        "positionsValueKrw": round(pos_val, 0),
        "totalValueKrw": round(total, 0),
        "cumReturn": round((total - seed) / seed, 4) if seed else None,
        "dailyReturn": round(daily_return, 4) if daily_return is not None else None,
        "drawdown": round((total - peak) / peak, 4) if peak else None,
        "positions": marks,
        "fxUsdKrw": round(fx, 2) if fx else None,
        "limits": risk.limits_snapshot(),
        "paperOnly": True,
        "liveTradingImplemented": False,
        "recentSignals": store.recent_signals(user_id, 12),
        "recentOrders": store.recent_orders(user_id, 12),
        "riskEvents": store.recent_risk_events(user_id, 10),
    }


_EDITABLE_KEYS = (
    "stop_loss_pct", "rsi_buy_min", "rsi_buy_max", "rsi_overheat",
    "volume_factor", "min_order_krw", "universe",
    "universe_mode", "scan_kospi_top", "scan_nasdaq_top",
    "broker_mode", "engine",
)


def get_settings(user_id: int) -> dict[str, Any]:
    """UI용 현재 설정 + 기본값 + (읽기전용)리스크 한도."""
    p = store.get_params(user_id)
    raw = store.get_settings_raw(user_id)
    mode = raw.get("universe_mode", "auto")
    return {
        "seedKrw": store.effective_seed(user_id),
        "params": {
            "stop_loss_pct": p.stop_loss_pct,
            "rsi_buy_min": p.rsi_buy_min,
            "rsi_buy_max": p.rsi_buy_max,
            "rsi_overheat": p.rsi_overheat,
            "volume_factor": p.volume_factor,
            "min_order_krw": p.min_order_krw,
            "universe": p.universe,
        },
        "scan": {
            "universe_mode": mode if mode in ("auto", "custom") else "auto",
            "scan_kospi_top": int(raw.get("scan_kospi_top", config.SCAN_KOSPI_TOP)),
            "scan_nasdaq_top": int(raw.get("scan_nasdaq_top", config.SCAN_NASDAQ_TOP)),
        },
        "brokerMode": broker_mode(user_id),
        "engine": raw.get("engine") if raw.get("engine") in ("legacy", "builder") else "builder",
        "activeEngine": active_engine(user_id),
        "kisConfigured": get_api_key("kis") is not None,
        "defaults": {
            "stop_loss_pct": config.STOP_LOSS_PCT,
            "rsi_buy_min": config.RSI_BUY_MIN,
            "rsi_buy_max": config.RSI_BUY_MAX,
            "rsi_overheat": config.RSI_OVERHEAT,
            "volume_factor": config.VOLUME_FACTOR,
            "min_order_krw": config.MIN_ORDER_KRW,
            "universe": list(config.DEFAULT_UNIVERSE),
            "universe_mode": "auto",
            "scan_kospi_top": config.SCAN_KOSPI_TOP,
            "scan_nasdaq_top": config.SCAN_NASDAQ_TOP,
        },
        "scanCaps": {"kospiMax": 829, "nasdaqMax": 100, "hardCap": config.SCAN_HARD_CAP},
        "limits": risk.limits_snapshot(),  # 전략이 변경 불가(읽기전용)
        "paperOnly": True,
        "liveTradingImplemented": False,
    }


def save_settings(user_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    """허용 파라미터만 병합 저장. 시드와 리스크 한도는 이 경로로 못 바꾼다."""
    raw = store.get_settings_raw(user_id)
    changed = []
    for key in _EDITABLE_KEYS:
        if key in patch and patch[key] is not None:
            raw[key] = patch[key]
            changed.append(key)
    store.save_settings(user_id, raw)
    store.insert_audit(user_id, kind="settings",
                       message=f"전략 파라미터 업데이트: {', '.join(changed) or '변경 없음'}")
    return get_settings(user_id)


def set_seed(user_id: int, seed_krw: float) -> dict[str, Any]:
    """B안: 시드를 settings에 주입하고 paper 시뮬을 새 시드로 초기화한다.

    실거래 아님. 시드 변경은 누적 손익/낙폭/30일 카운터의 기준점이 바뀌므로
    기존 시뮬 이력을 초기화한다.
    """
    seed = max(config.MIN_ORDER_KRW, float(seed_krw))
    raw = store.get_settings_raw(user_id)
    raw["seed_krw"] = seed
    store.save_settings(user_id, raw)
    store.reset_account(user_id, seed)
    store.insert_audit(user_id, kind="lifecycle",
                       message=f"시드 설정 + 시뮬 초기화: {seed:,.0f} KRW (paper only)")
    return {"seedKrw": seed, "status": "reset", "paperOnly": True}


def start(user_id: int) -> dict[str, Any]:
    acct = store.ensure_account(user_id)
    if acct["halted"]:
        store.insert_audit(user_id, kind="lifecycle", message="시작 거부: 전체 낙폭 한도로 정지 상태")
        return {"status": acct["status"], "message": "전체 낙폭 한도 도달로 정지됨 — 시작 불가", "halted": True}
    fields: dict[str, Any] = {"status": "running"}
    if not acct.get("started_at"):
        fields["started_at"] = store.kst_now().isoformat()
    store.update_account(user_id, **fields)
    store.insert_audit(user_id, kind="lifecycle", message="자동전략 시작(running)")
    return {"status": "running"}


def stop(user_id: int) -> dict[str, Any]:
    store.update_account(user_id, status="stopped")
    store.insert_audit(user_id, kind="lifecycle", message="자동전략 정지(stopped)")
    return {"status": "stopped"}


def _record_blocked(user_id: int, run_id: int, symbol: str, reason: str, data_status: str, est: float | None = None) -> None:
    store.insert_signal(user_id, run_id, symbol=symbol, action="BLOCKED", reason=reason,
                        data_status=data_status, risk_checks={}, est_amount_krw=est)
    store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=None,
                       gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                       status="blocked", block_reason=reason, data_status=data_status)


def run_once(user_id: int, trigger: str = "manual") -> dict[str, Any]:
    """broker_mode 분기. kis_mock이면 KIS 모의계좌로 주문 전송."""
    if broker_mode(user_id) == "kis_mock":
        return run_once_kis(user_id, trigger)
    return run_once_internal(user_id, trigger)


def run_once_internal(user_id: int, trigger: str = "manual") -> dict[str, Any]:
    params = store.get_params(user_id)
    acct = store.ensure_account(user_id)
    fx = usd_to_krw()

    # 전체 정지 상태면 어떤 신규 판단도 하지 않는다.
    if acct["halted"]:
        rid = store.insert_run(user_id, trigger=trigger, regime="halted", data_status="n/a")
        store.finalize_run(rid, signals=0, orders=0, blocked=0, note="전체 낙폭 한도로 정지됨")
        return {"status": "blocked", "reason": acct["halt_reason"], "runId": rid}

    # 1) 시장 레짐
    index_points = {}
    for sym in config.REGIME_SYMBOLS_US + config.REGIME_SYMBOLS_KR:
        index_points[sym] = _chart(sym).get("points") or []
    regime, regime_detail = engine.evaluate_regime(index_points)

    run_id = store.insert_run(user_id, trigger=trigger, regime=regime, data_status="ok")
    store.insert_audit(user_id, kind="decision", message=f"레짐={regime}: {regime_detail}")

    n_sig = n_ord = n_blk = 0
    cash = float(acct["cash_krw"])

    # 현재 총자산(마크) — 배분/리스크 기준
    pos_val, _marks, _ws = _positions_value(user_id, fx)
    total_value = cash + pos_val
    peak = max(float(acct["peak_value_krw"]), total_value)
    snaps = store.all_snapshots(user_id)
    prev_total = float(snaps[-1]["total_value_krw"]) if snaps else float(acct["seed_krw"])
    daily_return = (total_value - prev_total) / prev_total if prev_total else 0.0

    # 2) 청산(보유 종목) — 정지 여부와 무관하게 위험 관리 차원에서 점검
    for pos in store.list_positions(user_id):
        symbol = pos["symbol"]
        ch = _chart(symbol)
        status = ch.get("status") or "not_available"
        pts = ch.get("points") or []
        dgate = risk.data_status_gate(status)
        ev = engine.exit_eval(symbol, pts, float(pos["avg_cost_native"]), params)
        n_sig += 1
        store.insert_signal(user_id, run_id, symbol=symbol, action=ev.action, reason=ev.reason,
                            data_status=status, risk_checks=ev.checks, est_amount_krw=None)
        if ev.action != "SELL":
            continue
        if not dgate.ok:
            n_blk += 1
            store.insert_order(user_id, run_id, symbol=symbol, side="sell", quantity=0, price_native=None,
                               gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                               status="blocked", block_reason=dgate.reason, data_status=status)
            continue
        price = _last_price(pts)
        if price is None:
            n_blk += 1
            store.insert_order(user_id, run_id, symbol=symbol, side="sell", quantity=0, price_native=None,
                               gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                               status="blocked", block_reason="현재가 없음", data_status=status)
            continue
        fill = broker.simulate_fill(side="sell", price_native=price, quantity=float(pos["quantity"]),
                                    currency=pos["currency"], fx_usdkrw=fx or 1.0)
        cost_krw = float(pos["cost_krw"])
        realized = fill.cash_delta_krw - cost_krw  # 매도대금(수수료 후) - 매입원가
        cash += fill.cash_delta_krw
        store.delete_position(user_id, symbol)
        store.insert_order(user_id, run_id, symbol=symbol, side="sell", quantity=fill.quantity,
                           price_native=fill.exec_price_native, gross_krw=fill.gross_krw, fee_krw=fill.fee_krw,
                           slippage_krw=fill.slippage_krw, realized_pnl_krw=realized, status="filled",
                           block_reason="", data_status=("live" if status == "live" else "delayed-data paper simulation"))
        store.insert_audit(user_id, kind="order", message=f"매도 {symbol} {fill.quantity}주 ({ev.reason})",
                           data={"realizedKrw": round(realized, 0)})
        n_ord += 1

    # 3) 신규 매수 — risk-on + 신규매수 게이트 통과 시에만
    buy_gate = risk.new_buy_gate(halted=False, halt_reason="", daily_return=daily_return)
    if regime != "risk-on":
        store.insert_audit(user_id, kind="risk", message=f"신규 매수 보류: 레짐 {regime}")
    elif not buy_gate.ok:
        store.insert_risk_event(user_id, event="daily_loss_block", detail=buy_gate.reason)
        store.insert_audit(user_id, kind="risk", message=f"신규 매수 차단: {buy_gate.reason}")
    else:
        held = {p["symbol"] for p in store.list_positions(user_id)}
        open_n = len(held)

        # 후보풀 결정: universe_mode='auto'(광역 스캔) vs 'custom'(사용자 유니버스)
        rawset = store.get_settings_raw(user_id)
        mode = rawset.get("universe_mode", "auto")
        if mode == "custom" and params.universe:
            candidates = list(params.universe)
        else:
            candidates = universe.build_pool(
                kospi_top=int(rawset.get("scan_kospi_top", config.SCAN_KOSPI_TOP)),
                nasdaq_top=int(rawset.get("scan_nasdaq_top", config.SCAN_NASDAQ_TOP)),
            )

        # 1) 스캔 + 엔진 평가 + 모멘텀 점수 → BUY 후보 랭킹
        ranked: list[dict] = []
        scanned = 0
        for symbol in candidates:
            if symbol in held:
                continue  # 보유 종목은 청산 단계에서만 다룬다(추가매수는 별도 정책)
            if not risk.instrument_gate(symbol).ok:
                continue  # 레버리지/인버스/파생 — 조용히 제외(로그 폭주 방지)
            market, currency = _market_currency(symbol)
            if currency == "USD" and fx is None:
                continue
            scanned += 1
            ch = _chart(symbol)
            status = ch.get("status") or "not_available"
            pts = ch.get("points") or []
            ev = engine.entry_eval(symbol, pts, params)
            if ev.action != "BUY":
                ev = engine.pullback_eval(symbol, pts, params)
            if ev.action != "BUY":
                continue
            ms = engine.momentum_score(pts)
            ranked.append({
                "symbol": symbol, "market": market, "currency": currency,
                "status": status, "pts": pts, "ev": ev, "score": ms if ms is not None else -1e9,
            })
        ranked.sort(key=lambda r: r["score"], reverse=True)
        store.insert_audit(user_id, kind="decision",
                           message=f"광역 스캔: 후보 {len(candidates)} / 평가 {scanned} / BUY후보 {len(ranked)} (mode={mode})")

        # 2) 모멘텀 상위부터 리스크/배분 게이트 통과 시 매수 (MAX_POSITIONS까지)
        for cand in ranked:
            if open_n >= config.MAX_POSITIONS:
                break
            symbol = cand["symbol"]; market = cand["market"]; currency = cand["currency"]
            status = cand["status"]; pts = cand["pts"]; ev = cand["ev"]
            n_sig += 1
            store.insert_signal(user_id, run_id, symbol=symbol, action="BUY",
                                reason=f"{ev.reason} · 모멘텀점수 {cand['score']:.3f}",
                                data_status=status, risk_checks=ev.checks, est_amount_krw=None)
            dgate = risk.data_status_gate(status)
            if not dgate.ok:
                store.insert_risk_event(user_id, event="data_block", detail=dgate.reason, symbol=symbol)
                store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=None,
                                   gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                   status="blocked", block_reason=dgate.reason, data_status=status)
                n_blk += 1
                continue
            price = _last_price(pts)
            price_krw = _to_krw(price, currency, fx) if price is not None else None
            if not price_krw:
                store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=None,
                                   gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                   status="blocked", block_reason="현재가 없음", data_status=status)
                n_blk += 1
                continue
            alloc = allocator.size_buy(total_value_krw=total_value, cash_krw=cash, open_positions=open_n,
                                       already_holds=False, price_krw_per_share=price_krw,
                                       min_order_krw=params.min_order_krw)
            if not alloc.ok:
                store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=price,
                                   gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                   status="blocked", block_reason=alloc.reason, data_status=status)
                n_blk += 1
                continue
            fill = broker.simulate_fill(side="buy", price_native=price, quantity=alloc.quantity,
                                        currency=currency, fx_usdkrw=fx or 1.0)
            if -fill.cash_delta_krw > cash:
                store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=price,
                                   gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                   status="blocked", block_reason="현금 부족", data_status=status)
                n_blk += 1
                continue
            cash += fill.cash_delta_krw
            cost_krw = abs(fill.cash_delta_krw)
            store.upsert_position(user_id, symbol=symbol, market=market, currency=currency,
                                  quantity=float(alloc.quantity), avg_cost_native=fill.exec_price_native, cost_krw=cost_krw)
            store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=fill.quantity,
                               price_native=fill.exec_price_native, gross_krw=fill.gross_krw, fee_krw=fill.fee_krw,
                               slippage_krw=fill.slippage_krw, realized_pnl_krw=None, status="filled",
                               block_reason="", data_status=("live" if status == "live" else "delayed-data paper simulation"))
            store.insert_audit(user_id, kind="order", message=f"매수 {symbol} {alloc.quantity}주 ({ev.reason})",
                               data={"orderKrw": round(alloc.order_krw, 0), "score": round(cand["score"], 4)})
            n_ord += 1
            held.add(symbol); open_n += 1

    # 4) 스냅샷 + 리스크 정지 점검
    pos_val2, marks2, worst = _positions_value(user_id, fx)
    total2 = cash + pos_val2
    peak2 = max(peak, total2)
    seed = float(acct["seed_krw"])
    drawdown = (total2 - peak2) / peak2 if peak2 else 0.0
    daily_return2 = (total2 - prev_total) / prev_total if prev_total else 0.0
    store.upsert_snapshot(user_id, snap_date=store.kst_date(), total_value_krw=total2, cash_krw=cash,
                          positions_value_krw=pos_val2, cum_return=(total2 - seed) / seed if seed else None,
                          daily_return=daily_return2, drawdown=drawdown, positions=marks2,
                          data_status=worst)
    update_fields: dict[str, Any] = {"cash_krw": cash, "peak_value_krw": peak2}
    halt = risk.drawdown_halt(drawdown)
    if not halt.ok:
        update_fields.update(status="blocked", halted=1, halt_reason=halt.reason)
        store.insert_risk_event(user_id, event="drawdown_halt", detail=halt.reason)
        store.insert_audit(user_id, kind="risk", message=f"전체 낙폭 한도 — 자동전략 정지: {halt.reason}")
    store.update_account(user_id, **update_fields)
    store.finalize_run(run_id, signals=n_sig, orders=n_ord, blocked=n_blk,
                       note=f"regime={regime}, daily={daily_return2:.4f}, mdd={drawdown:.4f}")

    # 전환 스냅샷 기록
    pc = performance.promotion_check(user_id)
    store.insert_promotion(user_id, passed=pc["passed"], checks=pc["checks"])

    return {
        "status": "blocked" if not halt.ok else "ok",
        "runId": run_id, "regime": regime, "regimeDetail": regime_detail,
        "signals": n_sig, "orders": n_ord, "blocked": n_blk,
        "totalValueKrw": round(total2, 0), "cashKrw": round(cash, 0),
        "drawdown": round(drawdown, 4), "dailyReturn": round(daily_return2, 4),
    }


# ── KIS 모의계좌 백엔드 실행 ──────────────────────────────────────────────────

def _kis_chart_symbol(pdno: str) -> str:
    """KIS 국내 보유 종목코드(6자리)를 차트 조회용 .KS 심볼로."""
    code = "".join(c for c in str(pdno) if c.isdigit())[:6]
    return f"{code}.KS" if code else str(pdno)


def _kis_submit(coro_factory) -> dict[str, Any]:
    """KIS async 주문을 스레드풀 컨텍스트에서 동기 실행. 실패 시 {'error':..}."""
    try:
        return asyncio.run(coro_factory())
    except kis.KisError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def run_once_kis(user_id: int, trigger: str = "manual") -> dict[str, Any]:
    """KIS 모의계좌로 실제 주문을 전송한다. 포지션/현금은 KIS 잔고가 진실.

    제약: 비동기 체결(접수≠체결), 장중에만 체결, 해외는 지정가만(마지막가 기준).
    리스크/배분 게이트는 주문 전 동일 적용. 실거래 도메인은 절대 호출하지 않음.
    """
    params = store.get_params(user_id)
    fx = usd_to_krw()
    cred = get_api_key("kis")
    if not cred:
        rid = store.insert_run(user_id, trigger=trigger, regime="n/a", data_status="n/a")
        store.finalize_run(rid, signals=0, orders=0, blocked=0, note="KIS 자격증명 없음")
        return {"status": "blocked", "reason": "KIS 자격증명 없음 — 설정에서 입력", "runId": rid}

    bal = _kis_balances()
    if bal is None:
        rid = store.insert_run(user_id, trigger=trigger, regime="n/a", data_status="n/a")
        store.finalize_run(rid, signals=0, orders=0, blocked=0, note="KIS 잔고 조회 실패")
        return {"status": "blocked", "reason": "KIS 잔고 조회 실패", "runId": rid}
    dom, ovs = bal
    dom_cash = float(dom.get("cash") or 0.0)
    dom_holdings = {str(h.get("symbol")): h for h in dom.get("holdings", [])}
    ovs_holdings = {str(h.get("symbol")): h for h in ovs.get("holdings", [])}
    dom_val = sum(float(h.get("evalAmount") or 0.0) for h in dom.get("holdings", []))
    ovs_val_krw = sum(float(h.get("evalAmount") or 0.0) * (fx or 0.0) for h in ovs.get("holdings", []))
    total_value = float(dom.get("netAsset") or dom_cash) + ovs_val_krw

    # ── KIS 별도 리스크 장부(설정에 보관) — 일손실 -5%/전체낙폭 -20%를 KIS 잔고 기준으로 ──
    rawset = store.get_settings_raw(user_id)
    today = store.kst_date()
    kis_risk = dict(rawset.get("kis_risk") or {})
    if kis_risk.get("day") != today:
        kis_risk["day"] = today
        kis_risk["dayOpen"] = total_value
    day_open = float(kis_risk.get("dayOpen") or total_value)
    peak = max(float(kis_risk.get("peak") or total_value), total_value)
    kis_risk["peak"] = peak
    kis_daily_return = (total_value - day_open) / day_open if day_open else 0.0
    kis_drawdown = (total_value - peak) / peak if peak else 0.0
    # 정지: 기존 halted 플래그 OR 낙폭 한도 도달
    if bool(kis_risk.get("halted")) or not risk.drawdown_halt(kis_drawdown).ok:
        kis_risk["halted"] = True
        rawset["kis_risk"] = kis_risk
        store.save_settings(user_id, rawset)
        rid = store.insert_run(user_id, trigger=trigger, regime="halted", data_status="kis_mock")
        store.insert_risk_event(user_id, event="drawdown_halt",
                                detail=f"[KIS] 전체 낙폭 {kis_drawdown * 100:.1f}% — 자동전략 정지")
        store.finalize_run(rid, signals=0, orders=0, blocked=0, note="[KIS] 전체 낙폭 한도로 정지")
        return {"status": "blocked", "brokerMode": "kis_mock",
                "reason": f"KIS 전체 낙폭 한도 도달({kis_drawdown * 100:.1f}%) — 정지", "runId": rid}

    # 레짐
    index_points = {}
    for sym in config.REGIME_SYMBOLS_US + config.REGIME_SYMBOLS_KR:
        index_points[sym] = _chart(sym).get("points") or []
    regime, regime_detail = engine.evaluate_regime(index_points)
    run_id = store.insert_run(user_id, trigger=trigger, regime=regime, data_status="kis_mock")
    store.insert_audit(user_id, kind="decision", message=f"[KIS] 레짐={regime}: {regime_detail}")

    n_sig = n_ord = n_blk = 0

    # 1) 청산 — KIS 보유 종목 점검
    held_syms: set[str] = set()
    for kis_sym, h in {**{f"{k}.KS": v for k, v in dom_holdings.items()}, **ovs_holdings}.items():
        is_us = not kis_sym.endswith(".KS")
        chart_sym = kis_sym if not is_us else kis_sym
        held_syms.add(chart_sym)
        pts = _chart(chart_sym if not is_us else kis_sym).get("points") or []
        ev = engine.exit_eval(chart_sym, pts, float(h.get("avgPrice") or 0.0), params)
        n_sig += 1
        store.insert_signal(user_id, run_id, symbol=chart_sym, action=ev.action, reason=f"[KIS] {ev.reason}",
                            data_status="kis_mock", risk_checks=ev.checks, est_amount_krw=None)
        if ev.action != "SELL":
            continue
        qty = int(float(h.get("quantity") or 0))
        last = _last_price(pts)
        if qty <= 0 or last is None:
            n_blk += 1
            continue
        if store.has_recent_kis_order(user_id, chart_sym):
            store.insert_audit(user_id, kind="order", message=f"[KIS] 매도 보류 {chart_sym} — 최근 미체결 주문 존재(중복 방지)")
            continue
        if is_us:
            res = _kis_submit(lambda: kis.submit_overseas_order(cred, symbol=kis_sym, side="sell",
                                                                quantity=qty, limit_price=last))
        else:
            res = _kis_submit(lambda: kis.submit_order(cred, symbol=kis_sym, side="sell",
                                                       quantity=qty, order_type="market"))
        ok = "error" not in res
        store.insert_order(user_id, run_id, symbol=chart_sym, side="sell", quantity=qty if ok else 0,
                           price_native=last, gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                           status="submitted_kis" if ok else "rejected",
                           block_reason="" if ok else res.get("error", "주문 실패"), data_status="kis_mock")
        store.insert_audit(user_id, kind="order",
                           message=f"[KIS] 매도 전송 {chart_sym} {qty}주 — {'접수 ' + str(res.get('orderNo')) if ok else '거부: ' + res.get('error','')}")
        n_ord += 1 if ok else 0
        n_blk += 0 if ok else 1

    # 2) 신규 매수 — risk-on + 신규매수 게이트(KIS 잔고 기준 일손실 반영)
    buy_gate = risk.new_buy_gate(halted=False, halt_reason="", daily_return=kis_daily_return)
    if regime != "risk-on":
        store.insert_audit(user_id, kind="risk", message=f"[KIS] 신규 매수 보류: 레짐 {regime}")
    elif not buy_gate.ok:
        store.insert_risk_event(user_id, event="daily_loss_block", detail=f"[KIS] {buy_gate.reason}")
        store.insert_audit(user_id, kind="risk", message=f"[KIS] 신규 매수 차단: {buy_gate.reason}")
    else:
        umode = rawset.get("universe_mode", "auto")
        if umode == "custom" and params.universe:
            candidates = list(params.universe)
        else:
            candidates = universe.build_pool(
                kospi_top=int(rawset.get("scan_kospi_top", config.SCAN_KOSPI_TOP)),
                nasdaq_top=int(rawset.get("scan_nasdaq_top", config.SCAN_NASDAQ_TOP)),
            )
        ranked: list[dict] = []
        for symbol in candidates:
            if symbol in held_syms:
                continue
            if not risk.instrument_gate(symbol).ok:
                continue
            market, currency = _market_currency(symbol)
            if currency == "USD" and fx is None:
                continue
            pts = _chart(symbol).get("points") or []
            ev = engine.entry_eval(symbol, pts, params)
            if ev.action != "BUY":
                ev = engine.pullback_eval(symbol, pts, params)
            if ev.action != "BUY":
                continue
            ms = engine.momentum_score(pts)
            ranked.append({"symbol": symbol, "market": market, "currency": currency,
                           "pts": pts, "ev": ev, "score": ms if ms is not None else -1e9})
        ranked.sort(key=lambda r: r["score"], reverse=True)
        store.insert_audit(user_id, kind="decision",
                           message=f"[KIS] 광역 스캔: BUY후보 {len(ranked)} (mode={umode})")

        open_n = len(held_syms)
        for cand in ranked:
            if open_n >= config.MAX_POSITIONS:
                break
            symbol = cand["symbol"]; currency = cand["currency"]; pts = cand["pts"]; ev = cand["ev"]
            last = _last_price(pts)
            if last is None:
                continue
            if store.has_recent_kis_order(user_id, symbol):
                store.insert_audit(user_id, kind="order", message=f"[KIS] 매수 보류 {symbol} — 최근 미체결 주문 존재(중복 방지)")
                continue
            n_sig += 1
            store.insert_signal(user_id, run_id, symbol=symbol, action="BUY",
                                reason=f"[KIS] {ev.reason} · 점수 {cand['score']:.3f}",
                                data_status="kis_mock", risk_checks=ev.checks, est_amount_krw=None)
            target_krw = total_value * config.MAX_SINGLE_PCT
            if currency == "KRW":
                price_krw = last
                alloc = allocator.size_buy(total_value_krw=total_value, cash_krw=dom_cash, open_positions=open_n,
                                           already_holds=False, price_krw_per_share=price_krw,
                                           min_order_krw=params.min_order_krw)
                if not alloc.ok:
                    store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=last,
                                       gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                       status="blocked", block_reason=alloc.reason, data_status="kis_mock")
                    n_blk += 1
                    continue
                qty = int(alloc.quantity)
                res = _kis_submit(lambda: kis.submit_order(cred, symbol=symbol, side="buy",
                                                           quantity=qty, order_type="market"))
            else:  # USD — 해외 지정가(마지막가). KIS가 매수가능금액 검증(부족 시 거부).
                qty = int((target_krw / (fx or 1.0)) // last) if last else 0
                if qty < 1:
                    store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=last,
                                       gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                       status="blocked", block_reason="단일 한도 내 1주 미만", data_status="kis_mock")
                    n_blk += 1
                    continue
                res = _kis_submit(lambda: kis.submit_overseas_order(cred, symbol=symbol, side="buy",
                                                                    quantity=qty, limit_price=last))
            ok = "error" not in res
            store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=qty if ok else 0,
                               price_native=last, gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                               status="submitted_kis" if ok else "rejected",
                               block_reason="" if ok else res.get("error", "주문 실패"), data_status="kis_mock")
            store.insert_audit(user_id, kind="order",
                               message=f"[KIS] 매수 전송 {symbol} {qty}주 — {'접수 ' + str(res.get('orderNo')) if ok else '거부: ' + res.get('error','')}")
            if ok:
                n_ord += 1
                open_n += 1
            else:
                n_blk += 1

    # KIS 리스크 장부 저장(일중 시가/피크 누적)
    rawset["kis_risk"] = kis_risk
    store.save_settings(user_id, rawset)
    store.finalize_run(run_id, signals=n_sig, orders=n_ord, blocked=n_blk,
                       note=f"[KIS] regime={regime}, daily={kis_daily_return:.4f}, mdd={kis_drawdown:.4f}, 전송 {n_ord}")
    return {
        "status": "ok", "brokerMode": "kis_mock", "runId": run_id,
        "regime": regime, "regimeDetail": regime_detail,
        "signals": n_sig, "orders": n_ord, "blocked": n_blk,
        "dailyReturn": round(kis_daily_return, 4), "drawdown": round(kis_drawdown, 4),
        "promotionEligible": False,
        "note": "KIS 모의 주문 전송됨(체결은 장중·지정가 교차 시). KIS 모드는 공식 30일 검증(promotion)에 포함되지 않음 — 내부 sim 장부만 집계.",
    }
