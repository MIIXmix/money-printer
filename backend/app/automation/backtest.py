"""사용자 전략 백테스트 — 단일 종목 롱/플랫. 결정적 시뮬, 수수료·슬리피지 반영.

차트 포인트(지표 계산됨)를 시간순으로 훑으며 entry/exit 신호로 매매한다.
신호는 '확정된 봉'(전봉) 기준으로 판단하고 다음 봉 시가가 아닌 당봉 종가로 체결한다
(보수적 단순화). 결과는 수익률·MDD·승률·거래수 등 정직한 통계.
"""

from __future__ import annotations

from typing import Any

from . import strategy as strat_mod
from .strategy import StrategyDef


def run(points: list[dict], strat: StrategyDef, *, seed: float = 1_000_000.0,
        fee_pct: float = 0.0015, slippage_pct: float = 0.001,
        sell_tax_pct: float = 0.0) -> dict[str, Any]:
    """단일 종목 롱/플랫 백테스트.

    look-ahead 제거: 신호는 확정된 봉 i(종가까지 알려짐)로 판단하고 **다음 봉 i+1 시가**로
    체결한다(현실적). sell_tax_pct = 매도 거래세(KR 약 0.18%). 비용 = 수수료+슬리피지(+매도세).
    """
    pts = strat_mod.with_derived([p for p in points if p.get("close") is not None])
    if len(pts) < 3 or not strat.has_entry():
        return {"ok": False, "reason": "데이터 부족(최소 3봉) 또는 진입 조건 없음", "trades": 0}

    cash = float(seed)
    qty = 0.0
    avg_cost = 0.0
    buy_cost = 1.0 + fee_pct + slippage_pct
    sell_proceeds = 1.0 - fee_pct - slippage_pct - sell_tax_pct

    trades: list[dict] = []
    peak = float(seed)
    max_dd = 0.0

    # i까지 확정, i+1 시가로 체결 → 마지막 봉 직전까지만 결정.
    for i in range(1, len(pts) - 1):
        prev, cur, nxt = pts[i - 1], pts[i], pts[i + 1]
        fill_price = float(nxt.get("open") or nxt.get("close"))

        if qty <= 0:
            if strat_mod.entry_signal(strat, cur, prev) and cash > 0 and fill_price > 0:
                exec_price = fill_price * buy_cost
                qty = cash / exec_price
                avg_cost = fill_price
                cash = 0.0
                trades.append({"side": "buy", "price": fill_price, "i": i + 1})
        else:
            sell, reason = strat_mod.exit_signal(strat, cur, prev, avg_cost)
            if sell and fill_price > 0:
                exec_price = fill_price * sell_proceeds
                cash = qty * exec_price
                pnl = (fill_price - avg_cost) / avg_cost if avg_cost else 0.0
                trades.append({"side": "sell", "price": fill_price, "i": i + 1, "pnl": pnl, "reason": reason})
                qty = 0.0
                avg_cost = 0.0

        mark = cash + qty * float(cur["close"])
        peak = max(peak, mark)
        dd = (mark - peak) / peak if peak else 0.0
        max_dd = min(max_dd, dd)

    final_price = float(pts[-1]["close"])
    final_equity = cash + qty * final_price
    total_return = (final_equity - seed) / seed if seed else 0.0

    sells = [t for t in trades if t["side"] == "sell"]
    wins = [t for t in sells if (t.get("pnl") or 0) > 0]
    win_rate = (len(wins) / len(sells)) if sells else None
    avg_pnl = (sum((t.get("pnl") or 0) for t in sells) / len(sells)) if sells else None

    first_price = float(pts[0]["close"])
    buy_hold = (final_price - first_price) / first_price if first_price else 0.0

    return {
        "ok": True,
        "bars": len(pts),
        "seed": seed,
        "finalEquity": round(final_equity, 0),
        "totalReturn": round(total_return, 4),
        "buyHoldReturn": round(buy_hold, 4),
        "maxDrawdown": round(max_dd, 4),
        "trades": len(sells),
        "openPosition": qty > 0,
        "winRate": round(win_rate, 4) if win_rate is not None else None,
        "avgTradePnl": round(avg_pnl, 4) if avg_pnl is not None else None,
        "feePct": fee_pct,
        "slippagePct": slippage_pct,
        "note": "확정봉 기준 신호·당봉 종가 체결의 보수적 단순화. 분봉/슬리피지 모델은 실제와 다를 수 있음.",
    }
