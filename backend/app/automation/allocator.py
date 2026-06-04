"""PortfolioAllocator — 500k KRW 기준 비중·주문 수량 결정. 현금 하한 20%,
단일 종목 25%, 동시 4종목, 최소 주문금액을 강제한다."""

from __future__ import annotations

from dataclasses import dataclass

from . import config


@dataclass
class Allocation:
    quantity: int
    order_krw: float
    ok: bool
    reason: str = ""

    def as_dict(self) -> dict:
        return {"quantity": self.quantity, "orderKrw": round(self.order_krw, 0), "ok": self.ok, "reason": self.reason}


def size_buy(
    *,
    total_value_krw: float,
    cash_krw: float,
    open_positions: int,
    already_holds: bool,
    price_krw_per_share: float,
    min_order_krw: float = config.MIN_ORDER_KRW,
) -> Allocation:
    """신규/추가 매수 수량 산정. 한도 위반 시 ok=False + 사유."""
    if price_krw_per_share <= 0:
        return Allocation(0, 0, False, "가격 데이터 없음")
    if not already_holds and open_positions >= config.MAX_POSITIONS:
        return Allocation(0, 0, False, f"동시 보유 한도({config.MAX_POSITIONS}종목) 도달")

    # 현금 하한 유지 후 투입 가능 금액
    cash_floor = total_value_krw * config.MIN_CASH_PCT
    investable = cash_krw - cash_floor
    if investable < min_order_krw:
        return Allocation(0, 0, False, f"현금 하한({int(config.MIN_CASH_PCT * 100)}%) 유지로 투입 가능액 부족")

    # 단일 종목 25% 상한
    single_cap = total_value_krw * config.MAX_SINGLE_PCT
    target = min(single_cap, investable)
    if target < min_order_krw:
        return Allocation(0, 0, False, f"단일 종목 한도 기준 목표금액({int(target)}원) < 최소주문({int(min_order_krw)}원)")

    qty = int(target // price_krw_per_share)
    if qty < 1:
        return Allocation(0, 0, False, f"1주 가격({int(price_krw_per_share)}원)이 목표금액 초과")
    order_krw = qty * price_krw_per_share
    if order_krw < min_order_krw:
        return Allocation(0, 0, False, f"주문금액({int(order_krw)}원) < 최소주문({int(min_order_krw)}원)")
    return Allocation(qty, order_krw, True, "")
