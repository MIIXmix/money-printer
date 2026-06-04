"""RiskManager — 모든 한도를 강제하는 게이트. 한도값은 config 상수이며 전략 엔진이
바꿀 수 없다. 모든 차단은 사유와 함께 반환되어 audit/risk_events에 기록된다."""

from __future__ import annotations

from dataclasses import dataclass

from . import config


@dataclass
class Gate:
    ok: bool
    reason: str = ""

    def as_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason}


# 거래 허용 데이터 상태. 'delayed'는 paper 시뮬레이션으로만 허용(과대평가 금지).
_OK_DATA_STATUS = {"delayed", "live"}
_DELAYED = {"delayed"}


def data_status_gate(status: str | None) -> Gate:
    s = (status or "").strip().lower()
    if s in _OK_DATA_STATUS:
        return Gate(True, "live" if s == "live" else "delayed-data paper simulation")
    return Gate(False, f"데이터 상태 차단: {status or 'unknown'}")


def is_delayed(status: str | None) -> bool:
    return (status or "").strip().lower() in _DELAYED


def instrument_gate(symbol: str, name: str = "") -> Gate:
    """롱온리 주식/ETF만 허용. 레버리지·인버스·파생·코인·선물·환율은 차단."""
    sym = (symbol or "").strip().upper()
    nm = (name or "").lower()
    if not sym:
        return Gate(False, "심볼 없음")
    # 코인 / 선물 / 환율 / 지수원본 = 거래 대상 아님 (참고 데이터)
    if sym.endswith("-USD") or sym.endswith("-USDT"):
        return Gate(False, "코인 금지")
    if sym.endswith("=F"):
        return Gate(False, "선물 금지")
    if sym.endswith("=X"):
        return Gate(False, "환율은 참고 데이터(거래 대상 아님)")
    if sym.startswith("^"):
        return Gate(False, "지수 원본은 참고 데이터(거래 대상 아님)")
    if sym in config.BLOCKED_SYMBOLS:
        return Gate(False, "레버리지/인버스 ETF 금지")
    for kw in config.BLOCKED_NAME_KEYWORDS:
        if kw in nm:
            return Gate(False, f"레버리지/인버스 추정({kw}) — 금지")
    return Gate(True, "")


def new_buy_gate(*, halted: bool, halt_reason: str, daily_return: float | None) -> Gate:
    """신규 매수 허용 여부. 전체 정지 또는 당일 손실 한도면 차단."""
    if halted:
        return Gate(False, halt_reason or "자동전략 정지(전체 낙폭 한도)")
    if daily_return is not None and daily_return <= config.DAILY_LOSS_HALT:
        return Gate(False, f"당일 손실 {daily_return * 100:.2f}% — 신규 매수 금지(-5% 한도)")
    return Gate(True, "")


def drawdown_halt(drawdown: float | None) -> Gate:
    """전체 낙폭이 한도(-20%) 이하면 자동전략 정지 신호."""
    if drawdown is not None and drawdown <= config.TOTAL_DRAWDOWN_HALT:
        return Gate(False, f"전체 낙폭 {drawdown * 100:.2f}% — 자동전략 정지(-20% 한도)")
    return Gate(True, "")


def limits_snapshot() -> dict:
    """현재 강제되는 한도(읽기 전용). UI/audit 표시용."""
    return {
        "dailyLossHalt": config.DAILY_LOSS_HALT,
        "totalDrawdownHalt": config.TOTAL_DRAWDOWN_HALT,
        "minCashPct": config.MIN_CASH_PCT,
        "maxSinglePct": config.MAX_SINGLE_PCT,
        "maxPositions": config.MAX_POSITIONS,
        "feePct": config.FEE_PCT,
        "slippagePct": config.SLIPPAGE_PCT,
        "longOnly": True,
        "leverageInverseBlocked": True,
    }
