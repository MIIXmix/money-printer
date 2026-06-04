"""PaperBroker — 실제 브로커 호출 없는 모의 체결. 수수료·슬리피지를 반영하고
체결 결과(KRW 환산 포함)를 반환한다. DB 반영은 store가 담당한다."""

from __future__ import annotations

from dataclasses import dataclass

from . import config


@dataclass
class Fill:
    side: str                    # buy|sell
    quantity: float
    exec_price_native: float     # 슬리피지 반영 체결가 (종목 통화)
    gross_krw: float             # 체결금액(수수료 전) KRW
    fee_krw: float
    slippage_krw: float
    cash_delta_krw: float        # 현금 변화(매수 음수, 매도 양수)

    def as_dict(self) -> dict:
        return {
            "side": self.side,
            "quantity": self.quantity,
            "execPriceNative": round(self.exec_price_native, 4),
            "grossKrw": round(self.gross_krw, 0),
            "feeKrw": round(self.fee_krw, 0),
            "slippageKrw": round(self.slippage_krw, 0),
            "cashDeltaKrw": round(self.cash_delta_krw, 0),
        }


def _to_krw(amount_native: float, currency: str, fx_usdkrw: float) -> float:
    if (currency or "").upper() == "USD":
        return amount_native * fx_usdkrw
    return amount_native  # KRW 등 기타는 그대로(환율 미지원 통화는 호출 전에 거른다)


def simulate_fill(
    *,
    side: str,
    price_native: float,
    quantity: float,
    currency: str,
    fx_usdkrw: float,
    fee_pct: float = config.FEE_PCT,
    slippage_pct: float = config.SLIPPAGE_PCT,
) -> Fill:
    """모의 체결. 매수는 슬리피지만큼 불리한 가격, 매도는 유리한 쪽 반대로 체결."""
    qty = float(quantity)
    if side == "buy":
        exec_price = price_native * (1 + slippage_pct)
    else:
        exec_price = price_native * (1 - slippage_pct)
    gross_native = exec_price * qty
    gross_krw = _to_krw(gross_native, currency, fx_usdkrw)
    fee_krw = gross_krw * fee_pct
    slippage_native = abs(exec_price - price_native) * qty
    slippage_krw = _to_krw(slippage_native, currency, fx_usdkrw)
    if side == "buy":
        cash_delta = -(gross_krw + fee_krw)   # 매수: 체결금액 + 수수료 차감
    else:
        cash_delta = gross_krw - fee_krw       # 매도: 체결금액 - 수수료 입금
    return Fill(
        side=side,
        quantity=qty,
        exec_price_native=exec_price,
        gross_krw=gross_krw,
        fee_krw=fee_krw,
        slippage_krw=slippage_krw,
        cash_delta_krw=cash_delta,
    )
