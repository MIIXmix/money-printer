"""StrategyEngine — 설명 가능한 규칙 기반/계량 전략. AI/LLM은 여기 관여하지 않는다.
입력은 차트 지표 포인트(historical_chart 출력)이며, 출력은 근거가 붙은 신호다.

전략 요약(기본값 근거는 config 주석 참고):
- 시장 레짐: 대표 지수/ETF가 단기·중기 이동평균 위면 risk-on. 과매도·SMA60 이탈이면 risk-off.
- 진입(모멘텀): 가격이 SMA20·SMA60 위, RSI 45~70, MACD 히스토그램 양수, 거래량 평균 이상.
  RSI 75+ 과열은 신규 매수 금지.
- 눌림목: 장기 추세 상승 + 가격이 SMA20 근처 조정 + RSI 40~55 회복.
- 청산: 추세 훼손(SMA20 이탈), 손절(-7% 기본), 과열 후 모멘텀 약화.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config


@dataclass
class Eval:
    symbol: str
    action: str                 # BUY|SELL|HOLD
    reason: str
    score: int = 0
    kind: str = ""              # momentum|pullback|exit|""
    checks: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"symbol": self.symbol, "action": self.action, "reason": self.reason,
                "score": self.score, "kind": self.kind, "checks": self.checks}


def last_real_point(points: list[dict]) -> dict | None:
    for p in reversed(points or []):
        if p.get("close") is not None:
            return p
    return None


def avg_volume(points: list[dict], n: int = 20) -> float | None:
    vols = [p.get("volume") for p in (points or []) if p.get("volume") is not None]
    if not vols:
        return None
    tail = vols[-n:]
    return sum(tail) / len(tail) if tail else None


# ── 시장 레짐 ────────────────────────────────────────────────────────────────

def evaluate_regime(index_points: dict[str, list[dict]]) -> tuple[str, str]:
    """대표 지수/ETF 포인트들로 risk-on/off/neutral 판정. (regime, detail)."""
    ups = 0
    total = 0
    stressed: list[str] = []
    for sym, pts in index_points.items():
        last = last_real_point(pts)
        if not last:
            continue
        total += 1
        close = last.get("close")
        sma20 = last.get("sma20")
        sma60 = last.get("sma60")
        rsi = last.get("rsi14")
        if close is not None and sma20 is not None and sma60 is not None and close > sma20 and close > sma60:
            ups += 1
        if (rsi is not None and rsi < 30) or (close is not None and sma60 is not None and close < sma60 * 0.95):
            stressed.append(sym)
    if total == 0:
        return "neutral", "레짐 판정용 지수 데이터 없음"
    if stressed:
        return "risk-off", f"급락/과매도 감지: {', '.join(stressed)} — 신규 매수 축소"
    if ups >= (total + 1) // 2:
        return "risk-on", f"대표 지수 {ups}/{total} 이평선 위 — 위험 선호"
    return "risk-off", f"대표 지수 약세({ups}/{total} 이평선 위) — 신규 매수 축소"


# ── 종목 평가 ────────────────────────────────────────────────────────────────

def _need(last: dict, *keys: str) -> bool:
    return all(last.get(k) is not None for k in keys)


def entry_eval(symbol: str, points: list[dict], params: config.StrategyParams) -> Eval:
    last = last_real_point(points)
    if not last or not _need(last, "close", "sma20", "sma60", "rsi14"):
        return Eval(symbol, "HOLD", "지표 데이터 부족", kind="momentum")
    close = last["close"]; sma20 = last["sma20"]; sma60 = last["sma60"]; rsi = last["rsi14"]
    mh = last.get("macdHist")
    vol = last.get("volume")
    av = avg_volume(points)

    if rsi >= params.rsi_overheat:
        return Eval(symbol, "HOLD", f"RSI {rsi:.0f} 과열 — 신규 매수 금지", kind="momentum",
                    checks={"rsiOverheat": True})

    checks = {
        "aboveSma20": close > sma20,
        "aboveSma60": close > sma60,
        "rsiBand": params.rsi_buy_min <= rsi <= params.rsi_buy_max,
        "macdHistPositive": (mh is not None and mh > 0),
        "volumeAboveAvg": (vol is not None and av is not None and vol >= av * params.volume_factor),
    }
    score = sum(1 for v in checks.values() if v)
    core_ok = checks["aboveSma20"] and checks["aboveSma60"] and checks["rsiBand"]
    confirm_ok = checks["macdHistPositive"] or checks["volumeAboveAvg"]
    if core_ok and confirm_ok:
        reason = f"모멘텀 진입: 가격 SMA20/60 위, RSI {rsi:.0f}, " + (
            "MACD 히스토그램 양수" if checks["macdHistPositive"] else "거래량 평균 이상")
        return Eval(symbol, "BUY", reason, score=score, kind="momentum", checks=checks)
    return Eval(symbol, "HOLD", "모멘텀 진입 조건 미충족", score=score, kind="momentum", checks=checks)


def pullback_eval(symbol: str, points: list[dict], params: config.StrategyParams) -> Eval:
    last = last_real_point(points)
    if not last or not _need(last, "close", "sma20", "rsi14"):
        return Eval(symbol, "HOLD", "지표 데이터 부족", kind="pullback")
    close = last["close"]; sma20 = last["sma20"]; rsi = last["rsi14"]
    long_ma = last.get("sma120") or last.get("sma60")
    if long_ma is None:
        return Eval(symbol, "HOLD", "장기 추세 데이터 부족", kind="pullback")
    if rsi >= params.rsi_overheat:
        return Eval(symbol, "HOLD", f"RSI {rsi:.0f} 과열 — 신규 매수 금지", kind="pullback")
    trend_up = close > long_ma
    near_sma20 = abs(close - sma20) / sma20 <= config.PULLBACK_NEAR_SMA20 if sma20 else False
    rsi_ok = config.RSI_PULLBACK_MIN <= rsi <= config.RSI_PULLBACK_MAX
    checks = {"trendUp": trend_up, "nearSma20": near_sma20, "rsiRecover": rsi_ok}
    if trend_up and near_sma20 and rsi_ok:
        return Eval(symbol, "BUY", f"눌림목 진입: 장기 상승 추세 + SMA20 근처 조정 + RSI {rsi:.0f} 회복",
                    score=3, kind="pullback", checks=checks)
    return Eval(symbol, "HOLD", "눌림목 조건 미충족", kind="pullback", checks=checks)


def exit_eval(symbol: str, points: list[dict], avg_cost_native: float | None, params: config.StrategyParams) -> Eval:
    last = last_real_point(points)
    if not last or last.get("close") is None:
        return Eval(symbol, "HOLD", "현재가 데이터 없음 — 청산 보류", kind="exit")
    close = last["close"]; sma20 = last.get("sma20"); rsi = last.get("rsi14"); mh = last.get("macdHist")
    # 손절
    if avg_cost_native and avg_cost_native > 0:
        ret = (close - avg_cost_native) / avg_cost_native
        if ret <= params.stop_loss_pct:
            return Eval(symbol, "SELL", f"손절: 평단 대비 {ret * 100:.1f}% (한도 {params.stop_loss_pct * 100:.0f}%)",
                        kind="exit", checks={"stopLoss": True})
    # 추세 훼손
    if sma20 is not None and close < sma20:
        return Eval(symbol, "SELL", "추세 훼손: 종가가 SMA20 아래", kind="exit", checks={"belowSma20": True})
    # 과열 후 모멘텀 약화
    if rsi is not None and rsi >= params.rsi_overheat and mh is not None and mh < 0:
        return Eval(symbol, "SELL", f"과열({rsi:.0f}) 후 모멘텀 약화(MACD 히스토그램 음수)",
                    kind="exit", checks={"overheatFade": True})
    return Eval(symbol, "HOLD", "추세 유지 — 보유", kind="exit")
