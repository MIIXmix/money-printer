"""사용자 전략 빌더 서비스 — UI 메타데이터, 백테스트, 저장/조회 오케스트레이션."""

from __future__ import annotations

from typing import Any

from ..auth import get_api_key
from ..services import kis
from ..services.market_data import historical_chart
from . import allocator, backtest, broker, config, risk, rotation, service, store
from . import strategy as strat_mod
from .strategy import INDICATOR_FIELDS, OPERATORS, StrategyDef

# GTAA 글로벌 멀티에셋 기본 유니버스(전부 USD ETF, 환-랭킹 일관). 검증: -14% MDD/Sharpe0.91.
ROTATION_DEFAULT_UNIVERSE = [
    "SPY", "QQQ", "EFA", "EEM", "EWY", "EWJ",
    "TLT", "IEF", "LQD", "GLD", "DBC", "VNQ",
]
ROTATION_MAX_HOLDINGS = 12   # 로테이션 전용 종목수 상한(분산형 → 집중형 MAX_POSITIONS=4 미적용)


def _rotation_params(definition: dict) -> rotation.RotationParams:
    """전략 정의 → RotationParams. 검증된 GTAA 기본값, 안전 클램프."""
    d = definition or {}
    p = rotation.RotationParams(
        top_n=int(d.get("topN", 7)),
        lookback_m=int(d.get("lookbackM", 12)),
        skip_m=int(d.get("skipM", 1)),
        regime_ma_m=int(d.get("regimeMaM", 10)),
        regime_mode=str(d.get("regimeMode", "none")),
        cash_for_empty=bool(d.get("cashForEmpty", True)),
        weight=str(d.get("weight", "equal")),
        max_weight=float(d.get("maxWeight", 0.25)),
    )
    p.top_n = max(1, min(ROTATION_MAX_HOLDINGS, p.top_n))
    p.max_weight = min(0.5, max(0.05, p.max_weight))
    if p.weight not in ("equal", "invvol"):
        p.weight = "equal"
    if p.regime_mode not in ("none", "index"):
        p.regime_mode = "none"
    return p

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
        "rotationPreset": {
            "kind": "rotation",
            "name": "GTAA 글로벌 멀티에셋",
            "universe": list(ROTATION_DEFAULT_UNIVERSE),
            "topN": 7, "weight": "equal", "regimeMode": "none", "cashForEmpty": True,
            "lookbackM": 12, "skipM": 1, "maxWeight": 0.25, "indexSymbol": "SPY",
            "rebalance": "monthly",
            "labels": {
                "SPY": "미국 S&P500", "QQQ": "미국 나스닥100", "EFA": "선진국 주식", "EEM": "신흥국 주식",
                "EWY": "한국 주식", "EWJ": "일본 주식", "TLT": "미국 장기국채", "IEF": "미국 중기국채",
                "LQD": "미국 회사채", "GLD": "금", "DBC": "원자재", "VNQ": "미국 리츠",
            },
            "backtest": {"cagr": 0.10, "maxDrawdown": -0.14, "sharpe": 0.91, "window": "약 9년(2022 폭락 포함)"},
            "desc": "주식·채권·금·리츠·원자재 12자산을 월간 모멘텀으로 로테이션. 음수모멘텀·빈슬롯은 현금. "
                    "검증: CAGR ~10%, 최대낙폭 -14%, Sharpe 0.91. 롱온리·결정적·AI 미관여. "
                    "기대치는 과거보다 보수적으로(생존편향 적은 ETF지만 미래 보장 아님).",
        },
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
    """전략 정의를 과거 데이터로 백테스트. 조건형=종목별, 로테이션=유니버스 GTAA."""
    if (definition or {}).get("kind") == "rotation":
        params = _rotation_params(definition or {})
        universe = (definition or {}).get("universe") or list(ROTATION_DEFAULT_UNIVERSE)
        universe = [str(s).upper() for s in universe]
        index_symbol = str((definition or {}).get("indexSymbol", "SPY"))
        bt_period = period if period and period[-1] in "YyMmDd" else "10Y"
        res = rotation.backtest(universe, index_symbol, params, period=bt_period, seed=seed)
        res["kind"] = "rotation"
        res["period"] = bt_period
        res["dataStatus"] = "ok" if res.get("ok") else "insufficient"
        return res
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
    """활성(enabled) 사용자 전략을 1회 평가·체결. broker_mode에 따라 라우팅한다.

    paper_internal → 내부 PaperBroker, kis_mock → KIS 모의계좌 주문 전송.
    리스크 가드(종목/데이터/일손실/낙폭/배분)는 전략 신호 위에 강제 적용된다.
    """
    strats = store.enabled_strategies(user_id)
    if not strats:
        return {"ok": True, "ran": 0, "orders": 0, "blocked": 0, "note": "활성 전략 없음"}
    rot = [s for s in strats if (s["definition"] or {}).get("kind") == "rotation"]
    cond = [s for s in strats if (s["definition"] or {}).get("kind") != "rotation"]
    out: dict[str, Any] = {"ok": True}
    if cond:
        if service.broker_mode(user_id) == "kis_mock":
            out["condition"] = _run_strategies_kis(user_id, cond, trigger)
        else:
            out["condition"] = _run_strategies_internal(user_id, cond, trigger)
    if rot:
        # 로테이션(GTAA)은 v1에서 내부 sim 장부로만 월간 리밸런싱(KIS 미지원).
        out["rotation"] = _run_rotation_internal(user_id, rot, trigger)
    if not cond and not rot:
        return {"ok": True, "ran": 0, "orders": 0, "blocked": 0, "note": "실행할 전략 없음"}
    # 평탄화: 단일 종류면 그 결과를 그대로(상위호환), 혼합이면 묶음 반환
    if "condition" in out and "rotation" not in out:
        return out["condition"]
    if "rotation" in out and "condition" not in out:
        return out["rotation"]
    return out


def _run_strategies_internal(user_id: int, strats: list, trigger: str = "manual") -> dict[str, Any]:
    """전략을 내부 PaperBroker로 체결(automation_account 장부)."""
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


def _run_strategies_kis(user_id: int, strats: list, trigger: str = "manual") -> dict[str, Any]:
    """전략(사용자 조건)을 KIS 모의계좌로 주문 전송. 포지션/현금은 KIS 잔고가 진실.

    KR=국내 시장가, US=해외 지정가(마지막가). 미체결 dedup + KIS 리스크 장부(일손실/낙폭).
    공식 30일 promotion에는 미포함(내부 sim 장부만 집계).
    """
    cred = get_api_key("kis")
    if not cred:
        return {"ok": False, "ran": 0, "orders": 0, "blocked": 0, "reason": "KIS 자격증명 없음 — 설정에서 입력"}
    bal = service._kis_balances()
    if bal is None:
        return {"ok": False, "ran": 0, "orders": 0, "blocked": 0, "reason": "KIS 잔고 조회 실패"}
    dom, ovs = bal
    fx = service.usd_to_krw()
    dom_cash = float(dom.get("cash") or 0.0)
    held: dict[str, dict] = {}
    for h in dom.get("holdings", []):
        held[f"{h.get('symbol')}.KS"] = h
    for h in ovs.get("holdings", []):
        held[str(h.get("symbol"))] = h
    ovs_val_krw = sum(float(h.get("evalAmount") or 0.0) * (fx or 0.0) for h in ovs.get("holdings", []))
    total_value = float(dom.get("netAsset") or dom_cash) + ovs_val_krw

    # KIS 리스크 장부(settings)
    rawset = store.get_settings_raw(user_id)
    today = store.kst_date()
    kis_risk = dict(rawset.get("kis_risk") or {})
    if kis_risk.get("day") != today:
        kis_risk["day"] = today
        kis_risk["dayOpen"] = total_value
    day_open = float(kis_risk.get("dayOpen") or total_value)
    peak = max(float(kis_risk.get("peak") or total_value), total_value)
    kis_risk["peak"] = peak
    daily_return = (total_value - day_open) / day_open if day_open else 0.0
    drawdown = (total_value - peak) / peak if peak else 0.0

    run_id = store.insert_run(user_id, trigger=f"strategy:{trigger}", regime="user", data_status="kis_mock")
    if bool(kis_risk.get("halted")) or not risk.drawdown_halt(drawdown).ok:
        kis_risk["halted"] = True
        rawset["kis_risk"] = kis_risk
        store.save_settings(user_id, rawset)
        store.insert_risk_event(user_id, event="drawdown_halt", detail=f"[KIS] 전체 낙폭 {drawdown * 100:.1f}% — 정지")
        store.finalize_run(run_id, signals=0, orders=0, blocked=0, note="[KIS] 낙폭 한도 정지")
        return {"ok": False, "ran": len(strats), "halted": True, "runId": run_id,
                "reason": f"KIS 전체 낙폭 한도({drawdown * 100:.1f}%)"}

    buy_gate = risk.new_buy_gate(halted=False, halt_reason="", daily_return=daily_return)
    n_sig = n_ord = n_blk = 0
    held_syms = set(held.keys())
    open_n = len(held_syms)

    for s in strats:
        sdef = StrategyDef.from_dict(s["definition"])
        sname = s["name"]
        universe = s["definition"].get("universe") or list(config.DEFAULT_UNIVERSE)
        period, interval = _timeframe_interval(s["definition"].get("timeframe", "1d"))
        for symbol in universe[: config.SCAN_HARD_CAP]:
            if not risk.instrument_gate(symbol).ok:
                continue
            _market, currency = service._market_currency(symbol)
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
            last = service._last_price(pts)
            if last is None:
                continue

            # 청산
            if symbol in held_syms:
                pos = held[symbol]
                sell, reason = strat_mod.exit_signal(sdef, cur, prev, float(pos.get("avgPrice") or 0.0))
                if not sell:
                    continue
                if store.has_recent_kis_order(user_id, symbol):
                    continue
                qty = int(float(pos.get("quantity") or 0))
                if qty <= 0:
                    continue
                if currency == "USD":
                    res = service._kis_submit(lambda: kis.submit_overseas_order(cred, symbol=symbol, side="sell", quantity=qty, limit_price=last))
                else:
                    res = service._kis_submit(lambda: kis.submit_order(cred, symbol=symbol, side="sell", quantity=qty, order_type="market"))
                ok = "error" not in res
                n_sig += 1
                store.insert_signal(user_id, run_id, symbol=symbol, action="SELL", reason=f"[{sname}] {reason}",
                                    data_status="kis_mock", risk_checks={}, est_amount_krw=None)
                store.insert_order(user_id, run_id, symbol=symbol, side="sell", quantity=qty if ok else 0,
                                   price_native=last, gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                   status="submitted_kis" if ok else "rejected",
                                   block_reason="" if ok else res.get("error", "주문 실패"), data_status="kis_mock")
                store.insert_audit(user_id, kind="order",
                                   message=f"[{sname}/KIS] 매도 전송 {symbol} {qty}주 — {'접수' if ok else '거부: ' + res.get('error','')}")
                if ok:
                    n_ord += 1; held_syms.discard(symbol); open_n -= 1
                else:
                    n_blk += 1
                continue

            # 신규 매수
            if open_n >= config.MAX_POSITIONS:
                continue
            if not strat_mod.entry_signal(sdef, cur, prev):
                continue
            n_sig += 1
            store.insert_signal(user_id, run_id, symbol=symbol, action="BUY", reason=f"[{sname}] 진입 조건 충족",
                                data_status="kis_mock", risk_checks={}, est_amount_krw=None)
            if not buy_gate.ok:
                store.insert_risk_event(user_id, event="daily_loss_block", detail=f"[KIS] {buy_gate.reason}", symbol=symbol)
                n_blk += 1
                continue
            if not risk.data_status_gate(status).ok:
                n_blk += 1
                continue
            if store.has_recent_kis_order(user_id, symbol):
                continue
            target_krw = total_value * config.MAX_SINGLE_PCT
            if currency == "KRW":
                alloc = allocator.size_buy(total_value_krw=total_value, cash_krw=dom_cash, open_positions=open_n,
                                           already_holds=False, price_krw_per_share=last)
                if not alloc.ok:
                    store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=last,
                                       gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                       status="blocked", block_reason=alloc.reason, data_status="kis_mock")
                    n_blk += 1
                    continue
                qty = int(alloc.quantity)
                res = service._kis_submit(lambda: kis.submit_order(cred, symbol=symbol, side="buy", quantity=qty, order_type="market"))
            else:
                qty = int((target_krw / (fx or 1.0)) // last) if last else 0
                if qty < 1:
                    store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=0, price_native=last,
                                       gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                                       status="blocked", block_reason="단일 한도 내 1주 미만", data_status="kis_mock")
                    n_blk += 1
                    continue
                res = service._kis_submit(lambda: kis.submit_overseas_order(cred, symbol=symbol, side="buy", quantity=qty, limit_price=last))
            ok = "error" not in res
            store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=qty if ok else 0,
                               price_native=last, gross_krw=None, fee_krw=0, slippage_krw=0, realized_pnl_krw=None,
                               status="submitted_kis" if ok else "rejected",
                               block_reason="" if ok else res.get("error", "주문 실패"), data_status="kis_mock")
            store.insert_audit(user_id, kind="order",
                               message=f"[{sname}/KIS] 매수 전송 {symbol} {qty}주 — {'접수' if ok else '거부: ' + res.get('error','')}")
            if ok:
                n_ord += 1; open_n += 1; held_syms.add(symbol)
            else:
                n_blk += 1

    rawset["kis_risk"] = kis_risk
    store.save_settings(user_id, rawset)
    store.finalize_run(run_id, signals=n_sig, orders=n_ord, blocked=n_blk,
                       note=f"[KIS] strategies={len(strats)}, daily={daily_return:.4f}, mdd={drawdown:.4f}")
    return {
        "ok": True, "runId": run_id, "ran": len(strats), "brokerMode": "kis_mock",
        "signals": n_sig, "orders": n_ord, "blocked": n_blk,
        "dailyReturn": round(daily_return, 4), "drawdown": round(drawdown, 4),
        "promotionEligible": False,
        "note": "전략 → KIS 모의 주문 전송(체결은 장중·지정가 교차 시). 공식 30일 검증엔 미포함.",
    }


def _rot_price(symbol: str) -> tuple[float | None, str, str, str]:
    """심볼 → (최근가 native, 통화, 시장, 데이터상태). 차트 1회 조회."""
    market, currency = service._market_currency(symbol)
    ch = service._chart(symbol)
    status = ch.get("status") or "not_available"
    price = service._last_price(ch.get("points") or [])
    return price, currency, market, status


def _run_rotation_internal(user_id: int, rot_strats: list, trigger: str = "manual") -> dict[str, Any]:
    """GTAA 멀티에셋 모멘텀 로테이션 — 내부 PaperBroker 월간 리밸런싱.

    목표비중(rotation.target_weights)으로 계좌를 재조정한다. 월(asof)이 바뀌면 자동 실행,
    수동 트리거는 강제 실행. 리스크 안전망(-20% 낙폭정지·일손실 매수금지·데이터게이트) 강제.
    로테이션은 분산형이라 종목수 상한은 top_n(≤12), 단일비중은 max_weight를 따른다.
    """
    acct = store.ensure_account(user_id)
    if acct["halted"]:
        return {"ok": False, "halted": True, "reason": acct["halt_reason"]}

    # v1: 로테이션 전략은 1개만 계좌를 움직인다(다중이면 첫 활성만, 나머지 스킵 — 장부 경합 방지).
    strat = rot_strats[0]
    skipped = [s["name"] for s in rot_strats[1:]]
    sdef = strat["definition"] or {}
    sname = strat["name"]
    params = _rotation_params(sdef)
    universe = sdef.get("universe") or list(ROTATION_DEFAULT_UNIVERSE)
    universe = [str(s).upper() for s in universe][:ROTATION_MAX_HOLDINGS * 3]
    index_symbol = str(sdef.get("indexSymbol", "SPY"))

    forced = trigger.startswith("manual")
    rawset = store.get_settings_raw(user_id)
    rstate = dict(rawset.get("rotation_state") or {})
    last_asof = (rstate.get(str(strat["id"])) or {}).get("asof")

    # 목표비중 산출(결정적·AI 미관여)
    target = rotation.target_weights(universe, params, index_symbol=index_symbol, period="5Y")
    if not target.get("ok"):
        run_id = store.insert_run(user_id, trigger=f"rotation:{trigger}", regime="rotation", data_status="error")
        store.finalize_run(run_id, signals=0, orders=0, blocked=0, note=f"[{sname}] {target.get('reason')}")
        return {"ok": False, "reason": target.get("reason"), "runId": run_id}

    asof = target["asof"]
    weights: dict[str, float] = target["weights"]
    if not forced and last_asof == asof and store.list_positions(user_id):
        return {"ok": True, "ran": 0, "rebalanced": False, "asof": asof,
                "note": f"[{sname}] 동일월({asof}) — 리밸런싱 스킵(다음 달 자동)", "skipped": skipped}

    fx = service.usd_to_krw()
    run_id = store.insert_run(user_id, trigger=f"rotation:{trigger}", regime="rotation", data_status="ok")

    # 현재 자산 평가
    cash = float(acct["cash_krw"])
    pos_val, _marks, _ = service._positions_value(user_id, fx)
    total_value = cash + pos_val
    snaps = store.all_snapshots(user_id)
    prev_total = float(snaps[-1]["total_value_krw"]) if snaps else total_value
    daily_return = (total_value - prev_total) / prev_total if prev_total else 0.0
    peak = max(float(acct["peak_value_krw"]), total_value)
    buy_gate = risk.new_buy_gate(halted=False, halt_reason="", daily_return=daily_return)

    held = {p["symbol"]: p for p in store.list_positions(user_id)}
    # 가격·통화 캐시(목표 ∪ 보유)
    syms = set(weights) | set(held)
    info: dict[str, tuple[float | None, str, str, str]] = {s: _rot_price(s) for s in syms}

    n_sig = n_ord = n_blk = 0
    thresh = max(config.MIN_ORDER_KRW, total_value * 0.01)

    def _do_sell(symbol: str, qty: float, reason: str) -> bool:
        nonlocal cash, n_sig, n_ord
        price, currency, _m, status = info[symbol]
        if price is None or qty <= 0:
            return False
        pos = held.get(symbol)
        fill = broker.simulate_fill(side="sell", price_native=price, quantity=qty,
                                    currency=currency, fx_usdkrw=fx or 1.0)
        cost_part = float(pos["cost_krw"]) * (qty / float(pos["quantity"])) if pos and float(pos["quantity"]) else 0.0
        realized = fill.cash_delta_krw - cost_part
        cash += fill.cash_delta_krw
        new_qty = (float(pos["quantity"]) - qty) if pos else 0.0
        if pos and new_qty > 1e-9:
            store.upsert_position(user_id, symbol=symbol, market=pos["market"], currency=currency,
                                  quantity=new_qty, avg_cost_native=float(pos["avg_cost_native"]),
                                  cost_krw=max(0.0, float(pos["cost_krw"]) - cost_part))
            held[symbol]["quantity"] = new_qty
        else:
            store.delete_position(user_id, symbol); held.pop(symbol, None)
        store.insert_signal(user_id, run_id, symbol=symbol, action="SELL", reason=f"[{sname}] {reason}",
                            data_status=status, risk_checks={}, est_amount_krw=None)
        store.insert_order(user_id, run_id, symbol=symbol, side="sell", quantity=fill.quantity,
                           price_native=fill.exec_price_native, gross_krw=fill.gross_krw, fee_krw=fill.fee_krw,
                           slippage_krw=fill.slippage_krw, realized_pnl_krw=realized, status="filled",
                           block_reason="", data_status=("live" if status == "live" else "delayed-data paper simulation"))
        store.insert_audit(user_id, kind="order", message=f"[{sname}] 리밸런싱 매도 {symbol} {round(qty,4)}주 ({reason})",
                           data={"realizedKrw": round(realized, 0)})
        n_sig += 1; n_ord += 1
        return True

    def _do_buy(symbol: str, krw_amount: float) -> bool:
        nonlocal cash, n_sig, n_ord, n_blk
        price, currency, market, status = info[symbol]
        if price is None:
            return False
        if not risk.data_status_gate(status).ok:
            n_blk += 1
            return False
        price_krw = service._to_krw(price, currency, fx)
        if not price_krw or price_krw <= 0:
            n_blk += 1
            return False
        # 내부 sim은 소수주 허용 — 백테스트 연속비중과 일치(작은 시드에서도 분산 가능).
        qty = round(krw_amount / price_krw, 6)
        if qty <= 0:
            return False
        fill = broker.simulate_fill(side="buy", price_native=price, quantity=qty,
                                    currency=currency, fx_usdkrw=fx or 1.0)
        if -fill.cash_delta_krw > cash:
            qty = round(cash / (price_krw * (1 + config.FEE_PCT + config.SLIPPAGE_PCT)), 6)
            if qty <= 0:
                n_blk += 1
                return False
            fill = broker.simulate_fill(side="buy", price_native=price, quantity=qty,
                                        currency=currency, fx_usdkrw=fx or 1.0)
        cash += fill.cash_delta_krw
        pos = held.get(symbol)
        old_qty = float(pos["quantity"]) if pos else 0.0
        old_cost = float(pos["cost_krw"]) if pos else 0.0
        store.upsert_position(user_id, symbol=symbol, market=market, currency=currency,
                              quantity=old_qty + qty, avg_cost_native=fill.exec_price_native,
                              cost_krw=old_cost + abs(fill.cash_delta_krw))
        held[symbol] = {"symbol": symbol, "market": market, "currency": currency, "quantity": old_qty + qty,
                        "avg_cost_native": fill.exec_price_native, "cost_krw": old_cost + abs(fill.cash_delta_krw)}
        store.insert_signal(user_id, run_id, symbol=symbol, action="BUY", reason=f"[{sname}] 목표비중 매수",
                            data_status=status, risk_checks={}, est_amount_krw=round(krw_amount, 0))
        store.insert_order(user_id, run_id, symbol=symbol, side="buy", quantity=fill.quantity,
                           price_native=fill.exec_price_native, gross_krw=fill.gross_krw, fee_krw=fill.fee_krw,
                           slippage_krw=fill.slippage_krw, realized_pnl_krw=None, status="filled",
                           block_reason="", data_status=("live" if status == "live" else "delayed-data paper simulation"))
        store.insert_audit(user_id, kind="order", message=f"[{sname}] 리밸런싱 매수 {symbol} {round(qty,4)}주",
                           data={"orderKrw": round(abs(fill.cash_delta_krw), 0)})
        n_sig += 1; n_ord += 1
        return True

    # 1) 매도 패스: 목표에 없는 보유 전량 청산 + 목표초과분 축소(현금 확보 먼저)
    for symbol in list(held.keys()):
        price, currency, _m, _s = info.get(symbol, (None, "", "", ""))
        if price is None:
            continue
        cur_val = (service._to_krw(price * float(held[symbol]["quantity"]), currency, fx)) or 0.0
        tgt_val = total_value * weights.get(symbol, 0.0)
        if symbol not in weights:
            _do_sell(symbol, float(held[symbol]["quantity"]), "목표 제외")
        elif cur_val - tgt_val > thresh:
            sell_qty = round((cur_val - tgt_val) / ((service._to_krw(price, currency, fx)) or 1.0), 6)
            sell_qty = min(sell_qty, float(held[symbol]["quantity"]))
            if sell_qty > 0:
                _do_sell(symbol, sell_qty, "비중 축소")

    # 2) 매수 패스: 목표 미달분 매수(일손실 게이트 적용)
    if buy_gate.ok:
        for symbol, w in sorted(weights.items(), key=lambda kv: -kv[1]):
            price, currency, _m, _s = info.get(symbol, (None, "", "", ""))
            if price is None:
                continue
            held_qty = float(held[symbol]["quantity"]) if symbol in held else 0.0
            cur_val = (service._to_krw(price * held_qty, currency, fx)) or 0.0
            tgt_val = total_value * w
            if tgt_val - cur_val > thresh:
                _do_buy(symbol, min(tgt_val - cur_val, cash))
    else:
        store.insert_risk_event(user_id, event="daily_loss_block", detail=buy_gate.reason)

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

    # 리밸런싱 월 기록
    rstate[str(strat["id"])] = {"asof": asof, "ranAt": store.kst_now().isoformat()}
    rawset["rotation_state"] = rstate
    store.save_settings(user_id, rawset)

    store.finalize_run(run_id, signals=n_sig, orders=n_ord, blocked=n_blk,
                       note=f"[{sname}] GTAA 리밸런싱 asof={asof} 보유={len(weights)} mdd={drawdown:.4f}")
    return {
        "ok": True, "runId": run_id, "ran": 1, "rebalanced": True, "asof": asof,
        "regimeOn": target.get("regimeOn"), "targets": weights, "cashWeight": target.get("cashWeight"),
        "signals": n_sig, "orders": n_ord, "blocked": n_blk,
        "totalValueKrw": round(total2, 0), "cashKrw": round(cash, 0),
        "drawdown": round(drawdown, 4), "halted": not halt.ok, "skipped": skipped,
        "note": f"GTAA 멀티에셋 월간 리밸런싱(내부 sim). 목표 {len(weights)}종목 + 현금 {int((target.get('cashWeight') or 0)*100)}%.",
    }
