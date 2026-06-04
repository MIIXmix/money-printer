"""모멘텀 로테이션 + 추세(레짐) 필터 전략 — 연구근거 기반(횡단면 12-1 모멘텀,
200일/10개월 이평 레짐, 월간 리밸런싱). 롱온리·결정적·AI 미관여.

근거(요약): Jegadeesh-Titman 12-1 모멘텀 + Faber 10개월 이평 타이밍(MDD 반감) +
Antonacci 절대모멘텀. 월간 리밸런싱이 일간보다 비용·휩쏘 면에서 우월(Alpha Architect).

⚠️ 한계: 데이터는 yfinance(생존편향 → 백테스트 과대). 한국 모멘텀은 약함.
이 모듈은 연구·백테스트용 엔진이며, 실현 기대치는 과거치보다 낮게 봐야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..services.market_data import historical_chart


@dataclass
class RotationParams:
    top_n: int = 10                # 보유 종목 수(분산 위해 기본 10)
    lookback_m: int = 12           # 모멘텀 형성기간(개월)
    skip_m: int = 1                # 최근 1개월 제외(단기 반전 회피)
    regime_ma_m: int = 10          # 레짐 이평(개월, ~200일)
    regime_mode: str = "index"     # 'index'(단일지수 게이트) | 'none'(자산별 절대모멘텀만, GTAA)
    cash_for_empty: bool = False   # True=빈 슬롯 현금화(Faber GTAA, 약세장 자동 디리스킹)
    weight: str = "invvol"         # 'equal' | 'invvol'(역변동성)
    vol_lookback_m: int = 6        # 변동성 산출 개월
    max_weight: float = 0.25       # 단일 종목 최대 비중
    vol_target: float | None = None  # 연율 변동성 타게팅(예: 0.12). None=off
    vt_lookback_m: int = 6         # 변동성 타게팅 트레일링 산출 개월
    vt_max_lev: float = 1.0        # 최대 노출(레버리지 금지=1.0)
    fee_pct: float = 0.0015
    slippage_pct: float = 0.001
    kr_sell_tax_pct: float = 0.0018


@dataclass
class _Series:
    # 월말 종가 시계열: dates(정렬) + close(dict date->close)
    dates: list[str] = field(default_factory=list)
    close: dict[str, float] = field(default_factory=dict)


def _monthly_close(symbol: str, period: str = "10Y") -> _Series:
    """일봉을 월말 종가로 다운샘플."""
    ch = historical_chart(symbol, period, "1D")
    pts = [p for p in (ch.get("points") or []) if p.get("close") is not None]
    by_month: dict[str, tuple[str, float]] = {}  # 'YYYY-MM' -> (date, close) 마지막값
    for p in pts:
        t = str(p.get("time") or "")[:10]
        if len(t) < 7:
            continue
        ym = t[:7]
        by_month[ym] = (t, float(p["close"]))  # 같은 달은 마지막(월말)으로 덮어씀
    s = _Series()
    for ym in sorted(by_month):
        d, c = by_month[ym]
        s.dates.append(ym)
        s.close[ym] = c
    return s


def _momentum(s: _Series, ym: str, lookback_m: int, skip_m: int) -> float | None:
    """ym 시점 기준 12-1 모멘텀 = close[ym-skip] / close[ym-lookback-skip] - 1."""
    months = s.dates
    if ym not in s.close:
        return None
    i = months.index(ym)
    i_recent = i - skip_m
    i_old = i - lookback_m - skip_m
    if i_old < 0 or i_recent < 0:
        return None
    c_recent = s.close.get(months[i_recent])
    c_old = s.close.get(months[i_old])
    if not c_recent or not c_old:
        return None
    return c_recent / c_old - 1.0


def _vol(s: _Series, ym: str, n: int) -> float | None:
    """ym까지 최근 n개월 월간수익률 표준편차(역변동성 가중용)."""
    months = s.dates
    if ym not in s.close:
        return None
    i = months.index(ym)
    rets = []
    for j in range(max(1, i - n + 1), i + 1):
        c0 = s.close.get(months[j - 1]); c1 = s.close.get(months[j])
        if c0 and c1:
            rets.append(c1 / c0 - 1.0)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return var ** 0.5 or None


def backtest(universe: list[str], index_symbol: str, params: RotationParams,
             period: str = "10Y", seed: float = 1_000_000.0) -> dict[str, Any]:
    """월간 모멘텀 로테이션 + 레짐 필터 백테스트.

    매월: 지수가 레짐이평 위면 위험-on → 모멘텀 상위 top_n 동일가중 보유,
    아래면 위험-off → 현금. 다음 달 수익률로 평가. 회전율에 비용·세금 반영.
    """
    series = {sym: _monthly_close(sym, period) for sym in universe}
    idx = _monthly_close(index_symbol, period)
    series = {k: v for k, v in series.items() if len(v.dates) > 0}
    if len(idx.dates) < params.regime_ma_m + 2 or not series:
        return {"ok": False, "reason": "데이터 부족", "universe": len(series)}

    # 공통 월 캘린더(지수 기준)
    cal = idx.dates
    start_i = max(params.lookback_m + params.skip_m, params.regime_ma_m) + 1
    if start_i >= len(cal) - 1:
        return {"ok": False, "reason": "백테스트 기간 부족"}

    cash = float(seed)
    equity_curve: list[tuple[str, float]] = []
    prev_holdings: set[str] = set()
    peak = float(seed)
    max_dd = 0.0
    months_invested = 0
    rebalances = 0
    monthly_rets: list[float] = []
    gross_rets: list[float] = []   # 변동성 타게팅용(스케일 전 총수익) — 순환참조 회피

    for i in range(start_i, len(cal) - 1):
        ym = cal[i]; nxt = cal[i + 1]

        # 레짐: 지수 종가 > 최근 regime_ma_m 개월 평균
        if params.regime_mode == "none":
            regime_on = True  # 자산별 절대모멘텀(m>0)이 디리스킹 담당 (GTAA)
        else:
            idx_window = [idx.close[m] for m in cal[i - params.regime_ma_m + 1: i + 1] if m in idx.close]
            idx_now = idx.close.get(ym)
            regime_on = bool(idx_window and idx_now and idx_now > (sum(idx_window) / len(idx_window)))

        holdings: list[str] = []
        if regime_on:
            ranked = []
            for sym, s in series.items():
                m = _momentum(s, ym, params.lookback_m, params.skip_m)
                if m is not None and m > 0:  # 절대모멘텀: 양수만
                    ranked.append((m, sym))
            ranked.sort(reverse=True)
            holdings = [sym for _, sym in ranked[: params.top_n]]

        # 회전율 비용(직전 대비 교체된 종목)
        new_set = set(holdings)
        turnover = len(new_set.symmetric_difference(prev_holdings))
        if turnover:
            rebalances += 1
        # 비용: 교체 1건당 (매도+매수) 비용. KR 종목 매도세 추가.
        cost = 0.0
        for sym in new_set.symmetric_difference(prev_holdings):
            per = params.fee_pct + params.slippage_pct
            if sym.upper().endswith((".KS", ".KQ")):
                per += params.kr_sell_tax_pct / 2  # 평균적으로 매도측만
            cost += per
        cost_frac = (cost / max(1, len(new_set) or 1)) if new_set else 0.0

        # 가중치: equal 또는 invvol(역변동성, 단일 상한). 합=1.
        weights: dict[str, float] = {}
        if holdings:
            if params.weight == "invvol":
                raw = {}
                for sym in holdings:
                    v = _vol(series[sym], ym, params.vol_lookback_m)
                    raw[sym] = (1.0 / v) if (v and v > 0) else 0.0
                tot = sum(raw.values())
                if tot > 0:
                    weights = {k: min(params.max_weight, v / tot) for k, v in raw.items()}
                    s2 = sum(weights.values())
                    weights = {k: v / s2 for k, v in weights.items()} if s2 > 0 else {k: 1.0 / len(holdings) for k in holdings}
                else:
                    weights = {k: 1.0 / len(holdings) for k in holdings}
            else:
                weights = {k: 1.0 / len(holdings) for k in holdings}

            # GTAA: 빈 슬롯 현금화. 합=len/top_n (<1이면 나머지 현금)
            if params.cash_for_empty and params.top_n > 0:
                fill = min(1.0, len(holdings) / params.top_n)
                weights = {k: v * fill for k, v in weights.items()}

        # 다음 달 수익률 = 보유 종목 가중 평균(현금이면 0)
        if holdings:
            port_ret = 0.0
            for sym, w in weights.items():
                s = series[sym]
                c0 = s.close.get(ym); c1 = s.close.get(nxt)
                if c0 and c1:
                    port_ret += w * (c1 / c0 - 1.0)
            months_invested += 1
        else:
            port_ret = 0.0  # 현금

        gross_rets.append(port_ret)  # 스케일 전 기록(변동성 추정용)

        # 변동성 타게팅: 트레일링 실현변동성으로 노출 스케일(룩어헤드 없음)
        if params.vol_target and holdings and len(gross_rets) > 2:
            window = gross_rets[-params.vt_lookback_m - 1: -1]  # 직전까지(현재월 제외)
            window = [r for r in window if r is not None]
            if len(window) >= 2:
                m = sum(window) / len(window)
                v = (sum((r - m) ** 2 for r in window) / (len(window) - 1)) ** 0.5
                ann_vol = v * (12 ** 0.5)
                if ann_vol > 0:
                    scale = min(params.vt_max_lev, params.vol_target / ann_vol)
                    port_ret *= scale  # 나머지는 현금(0)

        port_ret -= cost_frac
        cash *= (1.0 + port_ret)
        monthly_rets.append(port_ret)
        equity_curve.append((nxt, cash))
        peak = max(peak, cash)
        dd = (cash - peak) / peak if peak else 0.0
        max_dd = min(max_dd, dd)
        prev_holdings = new_set

    final = cash
    n_months = len(monthly_rets)
    years = n_months / 12.0 if n_months else 1.0
    cagr = (final / seed) ** (1.0 / years) - 1.0 if years > 0 and final > 0 else 0.0
    # Sharpe(월간, 무위험 0 가정)
    if n_months > 1:
        mean = sum(monthly_rets) / n_months
        var = sum((r - mean) ** 2 for r in monthly_rets) / (n_months - 1)
        std = var ** 0.5
        sharpe = (mean / std) * (12 ** 0.5) if std > 0 else None
    else:
        sharpe = None

    # 벤치마크: 지수 매수후보유(같은 구간)
    bh = None
    if cal[start_i] in idx.close and cal[-1] in idx.close and idx.close[cal[start_i]]:
        bh = idx.close[cal[-1]] / idx.close[cal[start_i]] - 1.0

    return {
        "ok": True,
        "months": n_months,
        "years": round(years, 1),
        "finalEquity": round(final, 0),
        "totalReturn": round(final / seed - 1.0, 4),
        "cagr": round(cagr, 4),
        "maxDrawdown": round(max_dd, 4),
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "indexBuyHold": round(bh, 4) if bh is not None else None,
        "pctInvested": round(months_invested / n_months, 2) if n_months else 0.0,
        "rebalances": rebalances,
        "universe": len(series),
        "note": "월간 모멘텀 로테이션 + 레짐필터. yfinance 생존편향으로 과대 가능 — 실현 기대 더 낮게.",
    }


def target_weights(universe: list[str], params: RotationParams,
                   index_symbol: str = "SPY", period: str = "5Y") -> dict[str, Any]:
    """현재(최신 완성월) 기준 목표 보유·비중 산출 — 라이브 월간 리밸런싱용.

    백테스트와 동일 로직(12-1 모멘텀, 자산별/지수 레짐, 빈슬롯 현금화, equal/invvol)을
    가장 최근 월에 1회 적용. 반환 weights 합 ≤ 1(나머지 현금). AI 미관여·결정적.
    """
    series = {sym: _monthly_close(sym, period) for sym in universe}
    series = {k: v for k, v in series.items() if len(v.dates) > 0}
    if not series:
        return {"ok": False, "reason": "데이터 부족", "weights": {}, "asof": None}

    # 최신 공통 월(최소 lookback+skip 충족) — 각 시계열의 마지막 월 중 최소값
    last_months = [v.dates[-1] for v in series.values()]
    ym = min(last_months)  # 모두가 데이터 가진 가장 최근 월
    need = params.lookback_m + params.skip_m + 1

    # 레짐 게이트
    regime_on = True
    if params.regime_mode != "none":
        idx = _monthly_close(index_symbol, period)
        if ym in idx.close and len(idx.dates) >= params.regime_ma_m:
            i = idx.dates.index(ym)
            win = [idx.close[m] for m in idx.dates[max(0, i - params.regime_ma_m + 1): i + 1] if m in idx.close]
            regime_on = bool(win and idx.close[ym] > sum(win) / len(win))
        else:
            regime_on = False

    ranked: list[tuple[float, str]] = []
    if regime_on:
        for sym, s in series.items():
            if len(s.dates) < need or s.dates[-1] != ym and ym not in s.close:
                continue
            m = _momentum(s, ym, params.lookback_m, params.skip_m)
            if m is not None and m > 0:  # 절대모멘텀: 양수만
                ranked.append((m, sym))
        ranked.sort(reverse=True)
    holdings = [sym for _, sym in ranked[: params.top_n]]

    weights: dict[str, float] = {}
    if holdings:
        if params.weight == "invvol":
            raw = {}
            for sym in holdings:
                v = _vol(series[sym], ym, params.vol_lookback_m)
                raw[sym] = (1.0 / v) if (v and v > 0) else 0.0
            tot = sum(raw.values())
            if tot > 0:
                weights = {k: min(params.max_weight, v / tot) for k, v in raw.items()}
                s2 = sum(weights.values())
                weights = {k: v / s2 for k, v in weights.items()} if s2 > 0 else {k: 1.0 / len(holdings) for k in holdings}
            else:
                weights = {k: 1.0 / len(holdings) for k in holdings}
        else:
            weights = {k: 1.0 / len(holdings) for k in holdings}
        if params.cash_for_empty and params.top_n > 0:
            fill = min(1.0, len(holdings) / params.top_n)
            weights = {k: v * fill for k, v in weights.items()}

    return {
        "ok": True,
        "asof": ym,
        "regimeOn": regime_on,
        "weights": {k: round(v, 4) for k, v in weights.items()},
        "cashWeight": round(max(0.0, 1.0 - sum(weights.values())), 4),
        "momentum": {sym: round(m, 4) for m, sym in ranked[: params.top_n]},
        "universe": len(series),
        "note": "최신월 목표비중. 음수모멘텀·빈슬롯은 현금. yfinance 데이터 기반.",
    }
