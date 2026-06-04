"""자동전략 오케스트레이터. run_once가 엔진→리스크→배분→페이퍼브로커를 순서대로
통과시킨다. 실제 브로커/실전 주문은 절대 호출하지 않는다."""

from __future__ import annotations

from typing import Any

from ..services.market_data import historical_chart, usd_to_krw
from . import allocator, broker, config, engine, performance, risk, store


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
        for symbol in params.universe:
            if open_n >= config.MAX_POSITIONS and symbol not in held:
                break
            igate = risk.instrument_gate(symbol)
            if not igate.ok:
                store.insert_risk_event(user_id, event="instrument_block", detail=igate.reason, symbol=symbol)
                _record_blocked(user_id, run_id, symbol, igate.reason, "n/a")
                n_sig += 1; n_blk += 1
                continue
            market, currency = _market_currency(symbol)
            if currency == "USD" and fx is None:
                _record_blocked(user_id, run_id, symbol, "USD/KRW 환율 없음 — 매수 차단", "not_available")
                n_sig += 1; n_blk += 1
                continue
            ch = _chart(symbol)
            status = ch.get("status") or "not_available"
            pts = ch.get("points") or []
            dgate = risk.data_status_gate(status)
            ev = engine.entry_eval(symbol, pts, params)
            if ev.action != "BUY":
                ev = engine.pullback_eval(symbol, pts, params)
            n_sig += 1
            store.insert_signal(user_id, run_id, symbol=symbol, action=ev.action, reason=ev.reason,
                                data_status=status, risk_checks=ev.checks, est_amount_krw=None)
            if ev.action != "BUY":
                continue
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
                                       already_holds=(symbol in held), price_krw_per_share=price_krw,
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
                                  quantity=alloc.quantity, avg_cost_native=fill.exec_price_native, cost_krw=cost_krw)
            store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=fill.quantity,
                               price_native=fill.exec_price_native, gross_krw=fill.gross_krw, fee_krw=fill.fee_krw,
                               slippage_krw=fill.slippage_krw, realized_pnl_krw=None, status="filled",
                               block_reason="", data_status=("live" if status == "live" else "delayed-data paper simulation"))
            store.insert_audit(user_id, kind="order", message=f"매수 {symbol} {alloc.quantity}주 ({ev.reason})",
                               data={"orderKrw": round(alloc.order_krw, 0)})
            n_ord += 1
            if symbol not in held:
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
