from __future__ import annotations

from backend.app.auth import get_master  # noqa: E402
from backend.app.automation import allocator, broker, config, engine, performance, risk, store  # noqa: E402

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


def test_promotion_pass_and_fail():
    fail = performance.promotion_check(_UID)
    assert fail["passed"] is False  # empty history fails
    _seed_passing_history(_UID)
    ok = performance.promotion_check(_UID)
    assert ok["passed"] is True
    assert ok["liveTradingImplemented"] is False
    for key in ("minDays", "minTrades", "netReturn", "maxDrawdown", "dailyViolations"):
        assert ok["checks"][key]["pass"] is True
