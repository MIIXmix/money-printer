"""사용자 정의 전략 — 지표 조건 자유 조합(AND). 진입셋/청산셋/손절·익절 분리.

차트 포인트(historical_chart/indicators.frame_to_points 출력)의 계산된 지표 필드를
참조한다. 규칙 기반·결정적이며 AI/LLM은 관여하지 않는다(설명 가능).

조건(Condition) = {left, op, right}
  - left : 지표 필드명(예 'close','rsi14','sma20','bbLower' ...)
  - op   : '>' '<' '>=' '<=' 'cross_above' 'cross_below'
  - right: 숫자(예 30) 또는 지표 필드명(예 'sma60')

진입 = entry 조건 전부 AND. 청산 = (exit 조건 전부 AND) OR 손절 OR 익절.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 조건에서 참조 가능한 지표 필드(차트 포인트 키). 화이트리스트로 안전 보장.
INDICATOR_FIELDS: tuple[str, ...] = (
    "open", "high", "low", "close", "volume",
    "sma5", "sma20", "sma50", "sma60", "sma120", "ema20",
    "bbUpper", "bbLower", "rsi14", "macd", "macdSignal", "macdHist",
    "stochK", "stochD", "atr14", "obv", "vwap", "adx", "plusDi", "minusDi", "psar",
    "pivot", "pivotR1", "pivotS1", "pivotR2", "pivotS2",
    "ichimokuTenkan", "ichimokuKijun", "ichimokuSenkouA", "ichimokuSenkouB", "ichimokuChikou",
    # 파생: 거래량 20봉 평균 대비 비율은 backtest/engine에서 미리 계산해 'volRatio'로 주입 가능
    "volRatio",
)

OPERATORS: tuple[str, ...] = (">", "<", ">=", "<=", "cross_above", "cross_below")


@dataclass
class Condition:
    left: str
    op: str
    right: Any  # float 또는 필드명(str)

    def as_dict(self) -> dict:
        return {"left": self.left, "op": self.op, "right": self.right}

    @classmethod
    def from_dict(cls, d: dict) -> "Condition":
        return cls(left=str(d.get("left", "")), op=str(d.get("op", "")), right=d.get("right"))

    def valid(self) -> bool:
        if self.left not in INDICATOR_FIELDS or self.op not in OPERATORS:
            return False
        if isinstance(self.right, str) and self.right not in INDICATOR_FIELDS:
            # 숫자 문자열은 허용
            try:
                float(self.right)
            except (TypeError, ValueError):
                return False
        return True


@dataclass
class StrategyDef:
    entry: list[Condition] = field(default_factory=list)
    exit: list[Condition] = field(default_factory=list)
    stop_loss_pct: float | None = None       # 음수 (예 -0.05)
    take_profit_pct: float | None = None      # 양수 (예 0.10)

    @classmethod
    def from_dict(cls, d: dict | None) -> "StrategyDef":
        d = d or {}
        entry = [Condition.from_dict(c) for c in (d.get("entry") or [])]
        exit_ = [Condition.from_dict(c) for c in (d.get("exit") or [])]
        sl = d.get("stop_loss_pct")
        tp = d.get("take_profit_pct")
        sl = -abs(float(sl)) if isinstance(sl, (int, float)) else None
        tp = abs(float(tp)) if isinstance(tp, (int, float)) else None
        return cls(entry=[c for c in entry if c.valid()],
                   exit=[c for c in exit_ if c.valid()],
                   stop_loss_pct=sl, take_profit_pct=tp)

    def has_entry(self) -> bool:
        return len(self.entry) > 0


def _resolve(point: dict, token: Any) -> float | None:
    """토큰이 숫자면 그 값, 필드명이면 포인트에서 읽는다."""
    if isinstance(token, (int, float)):
        return float(token)
    if isinstance(token, str):
        if token in INDICATOR_FIELDS:
            v = point.get(token)
            return float(v) if v is not None else None
        try:
            return float(token)
        except (TypeError, ValueError):
            return None
    return None


def eval_condition(cond: Condition, point: dict, prev: dict | None) -> bool:
    """단일 조건 평가. 데이터 부족(None)이면 False(보수적)."""
    lv = _resolve(point, cond.left)
    rv = _resolve(point, cond.right)
    if lv is None or rv is None:
        return False
    if cond.op == ">":
        return lv > rv
    if cond.op == "<":
        return lv < rv
    if cond.op == ">=":
        return lv >= rv
    if cond.op == "<=":
        return lv <= rv
    if cond.op in ("cross_above", "cross_below"):
        if prev is None:
            return False
        plv = _resolve(prev, cond.left)
        prv = _resolve(prev, cond.right)
        if plv is None or prv is None:
            return False
        if cond.op == "cross_above":
            return plv <= prv and lv > rv
        return plv >= prv and lv < rv
    return False


def _eval_all(conds: list[Condition], point: dict, prev: dict | None) -> bool:
    return all(eval_condition(c, point, prev) for c in conds)


def entry_signal(strat: StrategyDef, point: dict, prev: dict | None) -> bool:
    """진입 = entry 조건 전부 AND. entry 비어있으면 False(진입 안 함)."""
    if not strat.entry:
        return False
    return _eval_all(strat.entry, point, prev)


def exit_signal(strat: StrategyDef, point: dict, prev: dict | None,
                avg_cost: float | None) -> tuple[bool, str]:
    """청산 = (exit 조건 AND) OR 손절 OR 익절. (sell?, reason)."""
    close = point.get("close")
    if avg_cost and avg_cost > 0 and close is not None:
        ret = (float(close) - avg_cost) / avg_cost
        if strat.stop_loss_pct is not None and ret <= strat.stop_loss_pct:
            return True, f"손절 {ret * 100:.1f}% (한도 {strat.stop_loss_pct * 100:.0f}%)"
        if strat.take_profit_pct is not None and ret >= strat.take_profit_pct:
            return True, f"익절 {ret * 100:.1f}% (목표 {strat.take_profit_pct * 100:.0f}%)"
    if strat.exit and _eval_all(strat.exit, point, prev):
        return True, "청산 조건 충족"
    return False, ""


def with_derived(points: list[dict], vol_window: int = 20) -> list[dict]:
    """파생 지표(volRatio = 거래량/최근평균)를 포인트에 주입한 새 리스트 반환."""
    out: list[dict] = []
    vols: list[float] = []
    for p in points:
        q = dict(p)
        v = p.get("volume")
        if v is not None:
            vols.append(float(v))
        tail = vols[-vol_window:]
        avg = (sum(tail) / len(tail)) if tail else None
        q["volRatio"] = (float(v) / avg) if (v is not None and avg) else None
        out.append(q)
    return out
