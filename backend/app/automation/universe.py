"""광역 후보풀 빌더. 로컬 스냅샷 CSV에서 코스피(거래대금 상위) + 나스닥100을
심볼 리스트로 만든다. 실시간 조회는 하지 않으며(스냅샷 기반), 실제 매매 판단은
service.run_once가 각 후보를 차트 조회 + 엔진 평가 + 모멘텀 랭킹으로 거른다.
"""

from __future__ import annotations

from . import config


def _kospi_top(kospi_top: int) -> list[str]:
    if kospi_top <= 0:
        return []
    try:
        import pandas as pd

        from ..services.market_data import KOREA_SNAPSHOT_PATH

        df = pd.read_csv(KOREA_SNAPSHOT_PATH, dtype={"코드": str}).fillna("")
        df["_turnover"] = pd.to_numeric(df.get("거래대금억원_추정"), errors="coerce").fillna(0.0)
        df = df.sort_values("_turnover", ascending=False)
        out: list[str] = []
        for _, row in df.iterrows():
            if len(out) >= kospi_top:
                break
            code = str(row.get("코드") or "").strip()
            if not code:
                continue
            code = code.zfill(6)
            # 우선주/신주인수권 등은 끝자리가 0이 아니다(보통주만 통과).
            # yfinance에 없거나 유동성 낮아 404 노이즈를 만든다.
            if code[-1] != "0":
                continue
            market = str(row.get("시장") or "").strip().upper()
            suffix = ".KQ" if market == "KOSDAQ" else ".KS"
            out.append(code + suffix)
        return out
    except Exception:
        return []


def _nasdaq_top(nasdaq_top: int) -> list[str]:
    if nasdaq_top <= 0:
        return []
    try:
        import pandas as pd

        from ..services.market_data import NASDAQ100_PATH

        df = pd.read_csv(NASDAQ100_PATH).fillna("")
        out: list[str] = []
        for _, row in df.head(nasdaq_top).iterrows():
            sym = str(row.get("symbol") or "").strip().upper()
            if sym:
                out.append(sym)
        return out
    except Exception:
        return []


def build_pool(kospi_top: int | None = None, nasdaq_top: int | None = None) -> list[str]:
    """코스피 거래대금 상위 + 나스닥100 상위를 합친 후보 심볼 리스트(중복 제거).

    **Fail-closed**: 스캔 결과가 비면(CSV 없음/스캔캡 0/데이터 실패) 빈 리스트를 반환한다.
    조용히 기본 종목으로 매매하지 않는다 — 후보가 없으면 주문도 없어야 한다.
    """
    k = config.SCAN_KOSPI_TOP if kospi_top is None else int(kospi_top)
    n = config.SCAN_NASDAQ_TOP if nasdaq_top is None else int(nasdaq_top)
    seen: set[str] = set()
    pool: list[str] = []
    for sym in _kospi_top(k) + _nasdaq_top(n):
        if sym not in seen:
            seen.add(sym)
            pool.append(sym)
    return pool[: config.SCAN_HARD_CAP]
