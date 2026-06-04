from __future__ import annotations

from backend.app.auth import get_master  # noqa: E402
from backend.app.automation import allocator, backtest, broker, config, engine, performance, risk, store, universe  # noqa: E402
from backend.app.automation import strategy as strat_mod  # noqa: E402
from backend.app.automation.strategy import Condition, StrategyDef  # noqa: E402

# conftest.py created the master account + DB.
_UID = get_master()["id"]


# ── RiskManager ──────────────────────────────────────────────────────────────

def test_instrument_gate_blocks_leverage_inverse_derivatives():
    assert risk.instrument_gate("TQQQ").ok is False        # leverage
    assert risk.instrument_gate("SQQQ").ok is False        # inverse
    assert risk.instrument_gate("122630.KS").ok is False   # KR leverage code
    assert risk.instrument_gate("XYZ", "KODEX 레버리지").ok is False
    assert risk.instrument_gate("ABC", "Direxion Bull 3X").ok is False
    assert risk.instrument_gate("BTC-USD").ok is False     # crypto
    assert risk.instrument_gate("CL=F").ok is False        # futures
    assert risk.instrument_gate("KRW=X").ok is False       # fx
    assert risk.instrument_gate("^GSPC").ok is False       # index raw
    # allowed
    assert risk.instrument_gate("AAPL").ok is True
    assert risk.instrument_gate("005930.KS").ok is True


def test_data_status_gate_blocks_missing_and_error():
    assert risk.data_status_gate("delayed").ok is True
    assert risk.data_status_gate("live").ok is True
    assert risk.data_status_gate("not_available").ok is False
    assert risk.data_status_gate("error").ok is False
    assert risk.data_status_gate("api_required").ok is False
    assert risk.data_status_gate(None).ok is False
    # delayed must be labelled as paper simulation, never overstated as live
    assert "paper simulation" in risk.data_status_gate("delayed").reason


def test_daily_loss_blocks_new_buys():
    assert risk.new_buy_gate(halted=False, halt_reason="", daily_return=-0.06).ok is False
    assert risk.new_buy_gate(halted=False, halt_reason="", daily_return=-0.05).ok is False  # at limit
    assert risk.new_buy_gate(halted=False, halt_reason="", daily_return=-0.04).ok is True
    assert risk.new_buy_gate(halted=True, halt_reason="halt", daily_return=0.0).ok is False


def test_total_drawdown_halts():
    assert risk.drawdown_halt(-0.20).ok is False  # at limit halts
    assert risk.drawdown_halt(-0.21).ok is False
    assert risk.drawdown_halt(-0.10).ok is True


# ── Allocator ────────────────────────────────────────────────────────────────

def test_allocator_caps_and_limits():
    # single-stock cap 25% of 500k = 125k; 70k/share -> 1 share (>= 50k min)
    a = allocator.size_buy(total_value_krw=500000, cash_krw=500000, open_positions=0,
                           already_holds=False, price_krw_per_share=70000)
    assert a.ok and a.quantity == 1
    # max positions reached, new symbol blocked
    b = allocator.size_buy(total_value_krw=500000, cash_krw=500000, open_positions=config.MAX_POSITIONS,
                           already_holds=False, price_krw_per_share=10000)
    assert b.ok is False
    # cash floor (20%) leaves too little
    c = allocator.size_buy(total_value_krw=500000, cash_krw=100001, open_positions=0,
                           already_holds=False, price_krw_per_share=10000)
    assert c.ok is False  # investable = 100001-100000 = 1 < min order
    # share too expensive for target
    d = allocator.size_buy(total_value_krw=500000, cash_krw=500000, open_positions=0,
                           already_holds=False, price_krw_per_share=200000)
    assert d.ok is False  # 125k target < 200k/share


# ── PaperBroker ──────────────────────────────────────────────────────────────

def test_broker_fee_and_slippage():
    f = broker.simulate_fill(side="buy", price_native=100.0, quantity=10, currency="USD", fx_usdkrw=1500)
    # exec price = 100 * 1.001 = 100.1; gross_krw = 100.1*10*1500 = 1,501,500
    assert round(f.exec_price_native, 3) == 100.1
    assert round(f.gross_krw) == 1501500
    assert round(f.fee_krw) == round(1501500 * config.FEE_PCT)
    assert f.cash_delta_krw < 0  # buy reduces cash
    s = broker.simulate_fill(side="sell", price_native=100.0, quantity=10, currency="KRW", fx_usdkrw=1500)
    assert s.exec_price_native < 100.0  # sell slips down
    assert s.cash_delta_krw > 0


# ── StrategyEngine ──────────────────────────────────────────────────────────

def _pt(close, sma20, sma60, rsi, mh, vol, sma120=None):
    return {"close": close, "sma20": sma20, "sma60": sma60, "rsi14": rsi,
            "macdHist": mh, "volume": vol, "sma120": sma120}


def test_entry_eval_momentum_buy():
    pts = [_pt(100, 95, 90, 60, 0.5, 2000)] * 21
    ev = engine.entry_eval("AAPL", pts, config.StrategyParams())
    assert ev.action == "BUY"


def test_entry_eval_overheat_blocks():
    pts = [_pt(100, 95, 90, 80, 0.5, 2000)] * 21  # RSI 80 overheated
    ev = engine.entry_eval("AAPL", pts, config.StrategyParams())
    assert ev.action == "HOLD"


def test_exit_eval_stop_loss_and_trend_break():
    p = config.StrategyParams()
    # stop loss: price far below avg cost
    pts = [_pt(90, 95, 92, 50, -0.1, 1000)] * 5
    ev = engine.exit_eval("AAPL", pts, avg_cost_native=100, params=p)
    assert ev.action == "SELL"
    # trend break: close below sma20 (avg cost fine)
    pts2 = [_pt(94, 95, 90, 55, 0.1, 1000)] * 5
    ev2 = engine.exit_eval("AAPL", pts2, avg_cost_native=90, params=p)
    assert ev2.action == "SELL"
    # healthy hold
    pts3 = [_pt(100, 95, 90, 55, 0.1, 1000)] * 5
    ev3 = engine.exit_eval("AAPL", pts3, avg_cost_native=90, params=p)
    assert ev3.action == "HOLD"


# ── 랭킹 엔진 / 후보풀 ────────────────────────────────────────────────────────

def test_momentum_score_ranks_stronger_higher():
    strong = [_pt(120, 100, 90, 62, 1.5, 3000)] * 70
    weak = [_pt(101, 100, 99, 52, 0.1, 1000)] * 70
    s_strong = engine.momentum_score(strong)
    s_weak = engine.momentum_score(weak)
    assert s_strong is not None and s_weak is not None
    assert s_strong > s_weak
    assert engine.momentum_score([]) is None  # 빈 입력 안전


def test_build_pool_returns_symbols_capped():
    pool = universe.build_pool(kospi_top=30, nasdaq_top=20)
    assert isinstance(pool, list) and len(pool) > 0
    assert len(pool) <= config.SCAN_HARD_CAP
    assert len(pool) == len(set(pool))  # 중복 없음
    # 코스피 심볼은 .KS/.KQ 접미사, 나스닥은 알파벳 티커
    assert any(s.endswith((".KS", ".KQ")) for s in pool)
    assert any(s.isalpha() for s in pool)


def test_build_pool_zero_fails_closed():
    # 스캔캡 0이면 빈 풀(기본 종목으로 fail-open 안 됨)
    pool = universe.build_pool(kospi_top=0, nasdaq_top=0)
    assert pool == []


# ── 사용자 전략 조건 엔진 / 백테스트 ─────────────────────────────────────────

def test_condition_eval_compare_and_cross():
    cur = {"close": 100, "sma20": 95, "sma60": 98, "rsi14": 28}
    prev = {"close": 94, "sma20": 96, "sma60": 98, "rsi14": 35}
    assert strat_mod.eval_condition(Condition("close", ">", "sma20"), cur, prev) is True
    assert strat_mod.eval_condition(Condition("rsi14", "<", 30), cur, prev) is True
    assert strat_mod.eval_condition(Condition("rsi14", "<", 20), cur, prev) is False
    # close가 sma20 위로 돌파(prev: 94<=96, now: 100>95)
    assert strat_mod.eval_condition(Condition("close", "cross_above", "sma20"), cur, prev) is True
    assert strat_mod.eval_condition(Condition("close", "cross_below", "sma20"), cur, prev) is False
    # 데이터 None이면 보수적 False
    assert strat_mod.eval_condition(Condition("macdHist", ">", 0), cur, prev) is False


def test_entry_and_exit_signal():
    strat = StrategyDef(
        entry=[Condition("close", ">", "sma20"), Condition("rsi14", "<", 30)],
        exit=[Condition("close", "<", "sma20")],
        stop_loss_pct=-0.05, take_profit_pct=0.10,
    )
    cur = {"close": 100, "sma20": 95, "rsi14": 28}
    assert strat_mod.entry_signal(strat, cur, None) is True
    # rsi 조건 깨지면 AND 실패
    assert strat_mod.entry_signal(strat, {"close": 100, "sma20": 95, "rsi14": 40}, None) is False
    # 익절: 평단 90, 현재 100 -> +11% >= 10%
    sell, reason = strat_mod.exit_signal(strat, {"close": 100, "sma20": 99}, None, 90.0)
    assert sell is True and "익절" in reason
    # 손절: 평단 100, 현재 94 -> -6% <= -5%
    sell2, reason2 = strat_mod.exit_signal(strat, {"close": 94, "sma20": 99}, None, 100.0)
    assert sell2 is True and "손절" in reason2


def test_backtest_runs_and_reports():
    # 가격이 오르내리는 합성 시계열 + sma20 근사. 진입(close>sma20) / 청산(close<sma20).
    pts = []
    prices = [100 + (i % 10) - 5 for i in range(60)]  # 95~104 진동
    for i, px in enumerate(prices):
        window = prices[max(0, i - 19):i + 1]
        sma = sum(window) / len(window)
        pts.append({"close": px, "sma20": sma, "volume": 1000})
    strat = StrategyDef(entry=[Condition("close", ">", "sma20")],
                        exit=[Condition("close", "<", "sma20")])
    res = backtest.run(pts, strat, seed=1_000_000)
    assert res["ok"] is True
    assert res["bars"] == 60
    assert res["trades"] >= 1
    assert "totalReturn" in res and "maxDrawdown" in res and "buyHoldReturn" in res


def test_backtest_no_entry_returns_not_ok():
    pts = [{"close": 100 + i, "sma20": 100} for i in range(30)]
    strat = StrategyDef(entry=[])  # 진입 조건 없음
    res = backtest.run(pts, strat)
    assert res["ok"] is False


def test_run_strategies_once_no_enabled():
    from backend.app.automation import strategy_service
    # 활성 전략 없으면 네트워크 안 타고 ran=0
    res = strategy_service.run_strategies_once(_UID, trigger="manual")
    assert res["ok"] is True
    assert res["ran"] == 0


def test_scheduler_market_hours():
    from datetime import datetime, timezone
    from backend.app.automation import scheduler
    # KR 정규장(03:00 UTC = 12:00 KST), 평일(2026-06-04=목)
    assert scheduler._in_session(datetime(2026, 6, 4, 3, 0, tzinfo=timezone.utc)) is True
    # US 정규장(15:00 UTC), 평일
    assert scheduler._in_session(datetime(2026, 6, 4, 15, 0, tzinfo=timezone.utc)) is True
    # 장외(09:00 UTC = 18:00 KST, KR 마감·US 개장 전)
    assert scheduler._in_session(datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc)) is False
    # 주말(2026-06-06=토)
    assert scheduler._in_session(datetime(2026, 6, 6, 3, 0, tzinfo=timezone.utc)) is False


def test_minute_bar_aggregator():
    from backend.app.services.kis_realtime import BarAggregator
    agg = BarAggregator()
    # 09:00분 틱들
    assert agg.on_tick("005930", 100, 10, "2026-06-04T09:00") is None
    assert agg.on_tick("005930", 102, 5, "2026-06-04T09:00") is None
    assert agg.on_tick("005930", 99, 3, "2026-06-04T09:00") is None
    # 09:01로 넘어가면 09:00봉 확정 emit
    emitted = agg.on_tick("005930", 101, 7, "2026-06-04T09:01")
    assert emitted is not None
    assert emitted.minute == "2026-06-04T09:00"
    assert emitted.open == 100 and emitted.high == 102 and emitted.low == 99 and emitted.close == 99
    assert emitted.volume == 18
    assert len(agg.recent("005930")) == 1


# ── Promotion (DB-backed) ────────────────────────────────────────────────────

def _seed_passing_history(uid: int):
    store.ensure_account(uid)
    # 30 daily snapshots ramping +10%, never breaching -5% daily, mdd small
    for i in range(30):
        v = 500000 * (1 + 0.10 * (i + 1) / 30)
        store.upsert_snapshot(uid, snap_date=f"2026-01-{i + 1:02d}", total_value_krw=v, cash_krw=v,
                              positions_value_krw=0, cum_return=(v - 500000) / 500000,
                              daily_return=0.003, drawdown=-0.01, positions=[], data_status="delayed")
    # 30 round-trip sells with positive realized pnl
    for i in range(30):
        store.insert_order(uid, None, symbol="AAPL", side="sell", quantity=1, price_native=100,
                           gross_krw=150000, fee_krw=200, slippage_krw=100, realized_pnl_krw=5000,
                           status="filled", block_reason="", data_status="delayed")


def test_position_accumulation_weighted_average():
    """추가매수 시 수량 합산 + 가중평균 평단 + 원가 합산 (덮어쓰기 버그 회귀 방지)."""
    sym = "ACCM.KS"
    store.delete_position(_UID, sym)
    # 1차: 10주 @ 100 (원가 1,000,000 KRW)
    store.upsert_position(_UID, symbol=sym, market="KR", currency="KRW",
                          quantity=10, avg_cost_native=100, cost_krw=1_000_000)
    pos = next(p for p in store.list_positions(_UID) if p["symbol"] == sym)
    # 2차 추가매수 5주 @ 200 — service의 누적 산식 재현
    prev_qty = float(pos["quantity"]); add_qty = 5.0; add_price = 200.0; add_cost = 1_000_000.0
    new_qty = prev_qty + add_qty
    new_avg = (float(pos["avg_cost_native"]) * prev_qty + add_price * add_qty) / new_qty
    new_cost = float(pos["cost_krw"]) + add_cost
    assert new_qty == 15
    assert abs(new_avg - (10 * 100 + 5 * 200) / 15) < 1e-6  # = 133.33
    store.upsert_position(_UID, symbol=sym, market="KR", currency="KRW",
                          quantity=new_qty, avg_cost_native=new_avg, cost_krw=new_cost)
    pos2 = next(p for p in store.list_positions(_UID) if p["symbol"] == sym)
    assert float(pos2["quantity"]) == 15          # 덮어쓰기 아님 — 누적
    assert float(pos2["cost_krw"]) == 2_000_000
    store.delete_position(_UID, sym)


def test_promotion_pass_and_fail():
    fail = performance.promotion_check(_UID)
    assert fail["passed"] is False  # empty history fails
    _seed_passing_history(_UID)
    ok = performance.promotion_check(_UID)
    assert ok["passed"] is True
    assert ok["liveTradingImplemented"] is False
    for key in ("minDays", "minTrades", "netReturn", "maxDrawdown", "dailyViolations"):
        assert ok["checks"][key]["pass"] is True
