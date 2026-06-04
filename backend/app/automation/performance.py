"""PerformanceTracker — 스냅샷·체결 기록에서 성과 지표와 30일 전환 충족 여부를 계산.
모든 수치는 수수료·슬리피지 반영(스냅샷의 total_value가 현금 차감을 포함)."""

from __future__ import annotations

from typing import Any

from . import config, store


def compute(user_id: int) -> dict[str, Any]:
    acct = store.get_account(user_id)
    seed = float(acct.get("seed_krw") or config.SEED_KRW)
    snaps = store.all_snapshots(user_id)
    orders = store.all_filled_orders(user_id)

    total_now = float(snaps[-1]["total_value_krw"]) if snaps else float(acct.get("cash_krw") or seed)
    cum_return = (total_now - seed) / seed if seed else None

    # MDD (peak-to-trough on snapshot total value)
    peak = seed
    mdd = 0.0
    for s in snaps:
        v = float(s["total_value_krw"])
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, (v - peak) / peak)

    days = len({s["snap_date"] for s in snaps})
    daily_violations = sum(1 for s in snaps if s.get("daily_return") is not None and float(s["daily_return"]) <= config.DAILY_LOSS_HALT)

    trades = len(orders)
    sells = [o for o in orders if o["side"] == "sell" and o.get("realized_pnl_krw") is not None]
    wins = [o for o in sells if float(o["realized_pnl_krw"]) > 0]
    win_rate = (len(wins) / len(sells)) if sells else None
    avg_pnl = (sum(float(o["realized_pnl_krw"]) for o in sells) / len(sells)) if sells else None
    realized_pnl = sum(float(o["realized_pnl_krw"]) for o in sells)
    fees = sum(float(o.get("fee_krw") or 0) for o in orders)
    slippage = sum(float(o.get("slippage_krw") or 0) for o in orders)

    return {
        "seedKrw": seed,
        "totalValueKrw": round(total_now, 0),
        "cumReturn": round(cum_return, 4) if cum_return is not None else None,
        "maxDrawdown": round(mdd, 4),
        "days": days,
        "trades": trades,
        "winRate": round(win_rate, 4) if win_rate is not None else None,
        "avgPnlKrw": round(avg_pnl, 0) if avg_pnl is not None else None,
        "realizedPnlKrw": round(realized_pnl, 0),
        "feesKrw": round(fees, 0),
        "slippageKrw": round(slippage, 0),
        "dailyViolations": daily_violations,
    }


def promotion_check(user_id: int) -> dict[str, Any]:
    perf = compute(user_id)
    checks = {
        "minDays": {"need": config.PROMOTION_MIN_DAYS, "value": perf["days"],
                    "pass": perf["days"] >= config.PROMOTION_MIN_DAYS},
        "minTrades": {"need": config.PROMOTION_MIN_TRADES, "value": perf["trades"],
                      "pass": perf["trades"] >= config.PROMOTION_MIN_TRADES},
        "netReturn": {"need": config.PROMOTION_MIN_NET_RETURN, "value": perf["cumReturn"],
                      "pass": perf["cumReturn"] is not None and perf["cumReturn"] >= config.PROMOTION_MIN_NET_RETURN},
        "maxDrawdown": {"need": config.PROMOTION_MAX_DRAWDOWN, "value": perf["maxDrawdown"],
                        "pass": perf["maxDrawdown"] >= config.PROMOTION_MAX_DRAWDOWN},
        "dailyViolations": {"need": config.PROMOTION_MAX_DAILY_VIOLATIONS, "value": perf["dailyViolations"],
                            "pass": perf["dailyViolations"] <= config.PROMOTION_MAX_DAILY_VIOLATIONS},
    }
    passed = all(c["pass"] for c in checks.values())
    return {
        "passed": passed,
        "checks": checks,
        "performance": perf,
        "note": "기준 통과 후에도 실전 자동매매는 사용자 수동 승인 + 별도 후속 구현 전까지 불가합니다.",
        "liveTradingImplemented": False,
    }
