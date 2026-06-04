"""자동전략 기본 설정값. 모든 한도는 코드 상수이며 전략 엔진이 임의로 바꿀 수 없다
(RiskManager만 참조). 사용자 설정은 일부 파라미터만 덮어쓴다."""

from __future__ import annotations

from dataclasses import dataclass, field

# ── 계좌/리스크 한도 (전략이 변경 불가) ──────────────────────────────────────
SEED_KRW = 500_000.0
DAILY_LOSS_HALT = -0.05          # 당일 -5% 도달 → 신규 매수 금지
TOTAL_DRAWDOWN_HALT = -0.20      # 전체 낙폭 -20% 도달 → 자동전략 정지

# ── 배분 ────────────────────────────────────────────────────────────────────
MIN_CASH_PCT = 0.20              # 현금 비중 최소 20% 유지
MAX_SINGLE_PCT = 0.25            # 단일 종목 최대 25%
MAX_POSITIONS = 4               # 동시 보유 최대 4종목
MIN_ORDER_KRW = 50_000.0        # 최소 주문금액(기본)

# ── 비용 (수수료·슬리피지) ──────────────────────────────────────────────────
# 보수적 기본값: 모의가 과대평가되지 않도록 약간 높게 둔다.
FEE_PCT = 0.0015                # 체결금액 대비 수수료 0.15%
SLIPPAGE_PCT = 0.001            # 체결 슬리피지 0.10%
KR_SELL_TAX_PCT = 0.0018        # 한국 증권거래세(매도시, 보수적 0.18%). 미국은 0.

# ── 전략 파라미터 (사용자 설정으로 일부 덮어쓰기 가능) ──────────────────────
STOP_LOSS_PCT = -0.07           # 개별 종목 손절 -7%
RSI_BUY_MIN = 45.0              # 진입 RSI 하한
RSI_BUY_MAX = 70.0             # 진입 RSI 상한
RSI_OVERHEAT = 75.0           # 과열 — 신규 매수 금지 / 청산 신호 가중
RSI_PULLBACK_MIN = 40.0
RSI_PULLBACK_MAX = 55.0
PULLBACK_NEAR_SMA20 = 0.03     # 가격이 SMA20의 ±3% 이내면 눌림목
VOLUME_FACTOR = 1.0           # 거래량 ≥ 최근 평균 × 이 값

# ── 시장 레짐 판단용 대표 지수/ETF ─────────────────────────────────────────
# 앱에서 yfinance로 조회 가능한 심볼만 사용.
REGIME_SYMBOLS_US = ["SPY", "QQQ"]
REGIME_SYMBOLS_KR = ["069500.KS"]   # KODEX 200 (코스피 추종)

# ── 후보 유니버스 (관심종목·보유가 없을 때의 기본 풀, 롱온리·비레버리지) ────
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "JPM",
    "005930.KS", "000660.KS", "035420.KS", "005380.KS", "051910.KS",
]

# ── 광역 스캔(랭킹 엔진) — universe_mode='auto'일 때 후보풀 크기 ───────────────
# 코스피 스냅샷 거래대금 상위 N + 나스닥100 상위 M을 차트 조회 후 모멘텀 랭킹.
# 사이클당 차트 호출 수 = (대략) N+M. 속도/레이트리밋 고려해 보수적 기본값.
SCAN_KOSPI_TOP = 40
SCAN_NASDAQ_TOP = 40
SCAN_HARD_CAP = 160     # 후보풀 절대 상한(폭주 방지)

# ── 차단 종목 (레버리지/인버스/파생형 ETF). 30일 검증에서 금지 ──────────────
BLOCKED_SYMBOLS = {
    # 미국 레버리지/인버스
    "TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXU", "SPXL", "SPXS",
    "UDOW", "SDOW", "TNA", "TZA", "LABU", "LABD", "FAS", "FAZ",
    "YINN", "YANG", "TMF", "TMV", "BOIL", "KOLD", "UVXY", "SVXY", "VIXY",
    # 한국 레버리지/인버스 (코드)
    "122630.KS", "252670.KS", "233740.KS", "251340.KS", "123320.KS",
}

# 이름 키워드 차단 (대소문자 무시)
BLOCKED_NAME_KEYWORDS = [
    "레버리지", "인버스", "곱버스", "2x", "3x", "bull", "bear",
    "ultra", "ultrapro", "inverse", "leveraged", "-1x", "short ",
]

# ── 30일 실전 전환 기준 (전부 충족해야 통과) ────────────────────────────────
PROMOTION_MIN_DAYS = 30
PROMOTION_MIN_TRADES = 30
PROMOTION_MIN_NET_RETURN = 0.10     # 수수료·슬리피지 반영 순수익률 +10%
PROMOTION_MAX_DRAWDOWN = -0.10      # 최대 낙폭 -10% 이하
PROMOTION_MAX_DAILY_VIOLATIONS = 0  # 하루 -5% 위반 0회


@dataclass
class StrategyParams:
    """런타임 파라미터 묶음. 사용자 설정으로 덮어쓰는 값만 포함(리스크 한도 제외)."""

    stop_loss_pct: float = STOP_LOSS_PCT
    rsi_buy_min: float = RSI_BUY_MIN
    rsi_buy_max: float = RSI_BUY_MAX
    rsi_overheat: float = RSI_OVERHEAT
    volume_factor: float = VOLUME_FACTOR
    min_order_krw: float = MIN_ORDER_KRW
    universe: list[str] = field(default_factory=lambda: list(DEFAULT_UNIVERSE))

    @classmethod
    def from_settings(cls, raw: dict | None) -> "StrategyParams":
        raw = raw or {}
        p = cls()
        for key in ("stop_loss_pct", "rsi_buy_min", "rsi_buy_max", "rsi_overheat", "volume_factor", "min_order_krw"):
            if isinstance(raw.get(key), (int, float)):
                setattr(p, key, float(raw[key]))
        uni = raw.get("universe")
        if isinstance(uni, list) and uni:
            p.universe = [str(s).upper() for s in uni][:30]
        # 안전: 최소주문금액 하한, 손절 음수 보장
        p.min_order_krw = max(10_000.0, p.min_order_krw)
        if p.stop_loss_pct > 0:
            p.stop_loss_pct = -abs(p.stop_loss_pct)
        return p
