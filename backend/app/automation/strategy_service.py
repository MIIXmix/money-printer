"""사용자 전략 빌더 서비스 — UI 메타데이터, 백테스트, 저장/조회 오케스트레이션."""

from __future__ import annotations

from typing import Any

from ..services.market_data import historical_chart
from . import allocator, backtest, broker, config, risk, service, store
from . import strategy as strat_mod
from .strategy import INDICATOR_FIELDS, OPERATORS, StrategyDef

# UI 표시용 지표 라벨(한국어). 화이트리스트와 1:1.
FIELD_LABELS: dict[str, str] = {
    "close": "종가", "open": "시가", "high": "고가", "low": "저가", "volume": "거래량",
    "sma5": "SMA5", "sma20": "SMA20", "sma50": "SMA50", "sma60": "SMA60", "sma120": "SMA120",
    "ema20": "EMA20", "bbUpper": "볼린저 상단", "bbLower": "볼린저 하단",
    "rsi14": "RSI(14)", "macd": "MACD", "macdSignal": "MACD 시그널", "macdHist": "MACD 히스토그램",
    "stochK": "스토캐스틱 %K", "stochD": "스토캐스틱 %D", "atr14": "ATR(14)", "obv": "OBV",
    "vwap": "VWAP", "adx": "ADX", "plusDi": "+DI", "minusDi": "-DI", "psar": "Parabolic SAR",
    "pivot": "피벗", "pivotR1": "피벗 R1", "pivotS1": "피벗 S1", "pivotR2": "피벗 R2", "pivotS2": "피벗 S2",
    "ichimokuTenkan": "일목 전환선", "ichimokuKijun": "일목 기준선",
    "ichimokuSenkouA": "일목 선행스팬A", "ichimokuSenkouB": "일목 선행스팬B", "ichimokuChikou": "일목 후행스팬",
    "volRatio": "거래량/20봉평균",
}

OP_LABELS: dict[str, str] = {
    ">": "초과(>)", "<": "미만(<)", ">=": "이상(≥)", "<=": "이하(≤)",
    "cross_above": "상향 돌파", "cross_below": "하향 돌파",
}


def builder_meta() -> dict[str, Any]:
    """전략 빌더 UI가 쓸 메타: 지표 목록, 연산자, 기본 리스크 한도(읽기전용 가드)."""
    return {
        "fields": [{"value": f, "label": FIELD_LABELS.get(f, f)} for f in INDICATOR_FIELDS],
        "operators": [{"value": o, "label": OP_LABELS.get(o, o)} for o in OPERATORS],
        "timeframes": [
            {"value": "1d", "label": "일봉 (안전·백테스트)"},
            {"value": "5m", "label": "5분봉 (지연데이터)"},
            {"value": "1m", "label": "1분봉 (한국주 실시간·미국 지연)"},
        ],
        "guards": {
            "dailyLossHalt": config.DAILY_LOSS_HALT,
            "totalDrawdownHalt": config.TOTAL_DRAWDOWN_HALT,
            "minCashPct": config.MIN_CASH_PCT,
            "maxSinglePct": config.MAX_SINGLE_PCT,
            "maxPositions": config.MAX_POSITIONS,
            "longOnly": True,
            "leverageInverseBlocked": True,
        },
        "note": "조건은 AND 결합. 진입셋·청산셋·손절%/익절% 분리. 리스크 가드는 전략 위에 강제(기본 제공, 일부 유저 조절).",
    }


def _backtest_window(timeframe: str, requested_period: str) -> tuple[str, str]:
    """백테스트는 전략 타임프레임과 같은 봉으로. 분봉은 yfinance 가용 범위로 제한."""
    tf = (timeframe or "1d").lower()
    if tf == "1m":
        return "5D", "1m"        # 1분봉: 최근 5일
    if tf in ("5m", "15m", "30m", "60m"):
        return "1M", tf          # 분봉: 최근 1개월
    return requested_period, "1D"  # 일봉: 요청 기간


def backtest_definition(definition: dict, symbol: str, period: str = "2Y",
                        seed: float = 1_000_000.0) -> dict[str, Any]:
    """전략 정의를 한 종목 과거 데이터로 백테스트. 전략 타임프레임과 같은 봉 사용."""
    strat = StrategyDef.from_dict(definition)
    if not strat.has_entry():
        return {"ok": False, "reason": "진입 조건이 없습니다.", "symbol": symbol}
    bt_period, interval = _backtest_window(definition.get("timeframe", "1d"), period)
    chart = historical_chart(symbol, bt_period, interval)
    points = chart.get("points") or []
    if not points:
        return {"ok": False, "reason": "차트 데이터 없음", "symbol": symbol, "dataStatus": chart.get("status")}
    is_kr = symbol.strip().upper().endswith((".KS", ".KQ"))
    res = backtest.run(points, strat, seed=seed,
                       fee_pct=config.FEE_PCT, slippage_pct=config.SLIPPAGE_PCT,
                       sell_tax_pct=config.KR_SELL_TAX_PCT if is_kr else 0.0)
    res["symbol"] = symbol
    res["period"] = bt_period
    res["interval"] = interval
    res["sellTaxPct"] = config.KR_SELL_TAX_PCT if is_kr else 0.0
    res["dataStatus"] = chart.get("status")
    res["note"] = (res.get("note", "") + " 신호=확정봉, 체결=다음봉 시가(look-ahead 제거). "
                   + ("KR 매도세 0.18% 반영." if is_kr else "")).strip()
    return res


def backtest_and_save(user_id: int, strategy_id: int, symbol: str, period: str = "2Y") -> dict[str, Any]:
    s = store.get_strategy(user_id, strategy_id)
    if not s:
        return {"ok": False, "reason": "전략 없음"}
    res = backtest_definition(s["definition"], symbol, period)
    store.save_strategy_backtest(user_id, strategy_id, res)
    return res


def _timeframe_interval(tf: str) -> tuple[str, str]:
    """전략 타임프레임 → historical_chart(period, interval).

    분봉은 yfinance 지연(~15분). 한국주 실시간(KIS WS)은 Phase 5b.
    """
    tf = (tf or "1d").lower()
    if tf == "1m":
        return "1D", "1m"     # 당일 1분봉(~390봉)
    if tf == "5m":
        return "5D", "5m"     # 5일 5분봉
    if tf in ("15m", "30m", "60m"):
        return "1M", tf
    return "1Y", "1D"          # 기본 일봉


def run_strategies_once(user_id: int, trigger: str = "manual") -> dict[str, Any]:
    """활성(enabled) 사용자 전략을 1회 평가하고 내부 PaperBroker로 체결한다.

    리스크 가드(종목/데이터/일손실/낙폭/배분)는 전략 신호 위에 강제 적용된다.
    실거래 경로는 호출하지 않는다. 포지션은 전략 간 공유(automation_positions).
    """
    # 전략 빌더는 내부 sim 전용. KIS 모드에선 포트폴리오/장부가 KIS라 충돌 → 차단.
    if service.broker_mode(user_id) == "kis_mock":
        return {"ok": False, "ran": 0, "orders": 0, "blocked": 0,
                "reason": "KIS 모드에서는 전략 빌더 미지원 — 체결방식을 '내부 시뮬'로 바꾸거나 자동전략 탭을 사용하세요."}
    strats = store.enabled_strategies(user_id)
    if not strats:
        return {"ok": True, "ran": 0, "orders": 0, "blocked": 0, "note": "활성 전략 없음"}
    acct = store.ensure_account(user_id)
    if acct["halted"]:
        return {"ok": False, "halted": True, "reason": acct["halt_reason"]}

    fx = service.usd_to_krw()
    run_id = store.insert_run(user_id, trigger=f"strategy:{trigger}", regime="user", data_status="ok")
    cash = float(acct["cash_krw"])
    pos_val, _marks, _ = service._positions_value(user_id, fx)
    total_value = cash + pos_val
    prev_total = total_value
    snaps = store.all_snapshots(user_id)
    if snaps:
        prev_total = float(snaps[-1]["total_value_krw"])
    daily_return = (total_value - prev_total) / prev_total if prev_total else 0.0
    peak = max(float(acct["peak_value_krw"]), total_value)

    n_sig = n_ord = n_blk = 0
    held = {p["symbol"]: p for p in store.list_positions(user_id)}
    open_n = len(held)
    buy_gate = risk.new_buy_gate(halted=False, halt_reason="", daily_return=daily_return)

    for s in strats:
        sdef = StrategyDef.from_dict(s["definition"])
        sname = s["name"]
        universe = s["definition"].get("universe") or list(config.DEFAULT_UNIVERSE)
        period, interval = _timeframe_interval(s["definition"].get("timeframe", "1d"))
        for symbol in universe[: config.SCAN_HARD_CAP]:
            if not risk.instrument_gate(symbol).ok:
                continue
            market, currency = service._market_currency(symbol)
            if currency == "USD" and fx is None:
                continue
            try:
                ch = historical_chart(symbol, period, interval)
            except Exception:
                ch = {"points": [], "status": "error"}
            status = ch.get("status") or "not_available"
            pts = strat_mod.with_derived(ch.get("points") or [])
            if len(pts) < 2:
                continue
            cur, prev = pts[-1], pts[-2]

            # 청산(보유 종목)
            if symbol in held:
                pos = held[symbol]
                sell, reason = strat_mod.exit_signal(sdef, cur, prev, float(pos["avg_cost_native"]))
                if not sell:
                    continue
                price = service._last_price(pts)
                if price is None:
                    continue
                fill = broker.simulate_fill(side="sell", price_native=price, quantity=float(pos["quantity"]),
                                            currency=pos["currency"], fx_usdkrw=fx or 1.0)
                realized = fill.cash_delta_krw - float(pos["cost_krw"])
                cash += fill.cash_delta_krw
                store.delete_position(user_id, symbol)
                del held[symbol]; open_n -= 1
                store.insert_signal(user_id, run_id, symbol=symbol, action="SELL", reason=f"[{sname}] {reason}",
                                    data_status=status, risk_checks={}, est_amount_krw=None)
                store.insert_order(user_id, run_id, symbol=symbol, side="sell", quantity=fill.quantity,
                                   price_native=fill.exec_price_native, gross_krw=fill.gross_krw, fee_krw=fill.fee_krw,
                                   slippage_krw=fill.slippage_krw, realized_pnl_krw=realized, status="filled",
                                   block_reason="", data_status=("live" if status == "live" else "delayed-data paper simulation"))
                store.insert_audit(user_id, kind="order", message=f"[{sname}] 매도 {symbol} {fill.quantity}주 ({reason})",
                                   data={"realizedKrw": round(realized, 0)})
                n_sig += 1; n_ord += 1
                continue

            # 신규 매수
            if open_n >= config.MAX_POSITIONS:
                continue
            if not strat_mod.entry_signal(sdef, cur, prev):
                continue
            n_sig += 1
            store.insert_signal(user_id, run_id, symbol=symbol, action="BUY", reason=f"[{sname}] 진입 조건 충족",
                                data_status=status, risk_checks={}, est_amount_krw=None)
            if not buy_gate.ok:
                store.insert_risk_event(user_id, event="daily_loss_block", detail=buy_gate.reason, symbol=symbol)
                n_blk += 1
                continue
            dgate = risk.data_status_gate(status)
            if not dgate.ok:
                store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=None,
                                   gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                   status="blocked", block_reason=dgate.reason, data_status=status)
                n_blk += 1
                continue
            price = service._last_price(pts)
            price_krw = service._to_krw(price, currency, fx) if price is not None else None
            if not price_krw:
                n_blk += 1
                continue
            alloc = allocator.size_buy(total_value_krw=total_value, cash_krw=cash, open_positions=open_n,
                                       already_holds=False, price_krw_per_share=price_krw)
            if not alloc.ok:
                store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=price,
                                   gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                   status="blocked", block_reason=alloc.reason, data_status=status)
                n_blk += 1
                continue
            fill = broker.simulate_fill(side="buy", price_native=price, quantity=alloc.quantity,
                                        currency=currency, fx_usdkrw=fx or 1.0)
            if -fill.cash_delta_krw > cash:
                n_blk += 1
                continue
            cash += fill.cash_delta_krw
            store.upsert_position(user_id, symbol=symbol, market=market, currency=currency,
                                  quantity=float(alloc.quantity), avg_cost_native=fill.exec_price_native,
                                  cost_krw=abs(fill.cash_delta_krw))
            store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=fill.quantity,
                               price_native=fill.exec_price_native, gross_krw=fill.gross_krw, fee_krw=fill.fee_krw,
                               slippage_krw=fill.slippage_krw, realized_pnl_krw=None, status="filled",
                               block_reason="", data_status=("live" if status == "live" else "delayed-data paper simulation"))
            store.insert_audit(user_id, kind="order", message=f"[{sname}] 매수 {symbol} {alloc.quantity}주",
                               data={"orderKrw": round(alloc.order_krw, 0)})
            held[symbol] = {"symbol": symbol, "quantity": alloc.quantity, "avg_cost_native": fill.exec_price_native,
                            "cost_krw": abs(fill.cash_delta_krw), "currency": currency}
            n_ord += 1; open_n += 1

    # 스냅샷 + 낙폭 정지
    pos_val2, marks2, worst = service._positions_value(user_id, fx)
    total2 = cash + pos_val2
    peak2 = max(peak, total2)
    seed = float(acct["seed_krw"])
    drawdown = (total2 - peak2) / peak2 if peak2 else 0.0
    store.upsert_snapshot(user_id, snap_date=store.kst_date(), total_value_krw=total2, cash_krw=cash,
                          positions_value_krw=pos_val2, cum_return=(total2 - seed) / seed if seed else None,
                          daily_return=(total2 - prev_total) / prev_total if prev_total else 0.0,
                          drawdown=drawdown, positions=marks2, data_status=worst)
    fields: dict[str, Any] = {"cash_krw": cash, "peak_value_krw": peak2}
    halt = risk.drawdown_halt(drawdown)
    if not halt.ok:
        fields.update(status="blocked", halted=1, halt_reason=halt.reason)
        store.insert_risk_event(user_id, event="drawdown_halt", detail=halt.reason)
    store.update_account(user_id, **fields)
    store.finalize_run(run_id, signals=n_sig, orders=n_ord, blocked=n_blk,
                       note=f"strategies={len(strats)}, mdd={drawdown:.4f}")
    return {
        "ok": True, "runId": run_id, "ran": len(strats),
        "signals": n_sig, "orders": n_ord, "blocked": n_blk,
        "totalValueKrw": round(total2, 0), "cashKrw": round(cash, 0),
        "drawdown": round(drawdown, 4), "halted": not halt.ok,
        "note": "내부 PaperBroker 체결. 일봉 평가(분봉/실시간은 Phase 5).",
    }
