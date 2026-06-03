from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any

import httpx
import pandas as pd
import yfinance as yf

from .indicators import add_indicators, frame_to_points
from .kis import quote_price


DEFAULT_MARKET_SYMBOLS = [
    "^GSPC",
    "^IXIC",
    "^DJI",
    "^VIX",
    "^TNX",
    "CL=F",
    "GC=F",
    "KRW=X",
    "BTC-USD",
    "005930.KS",
    "000660.KS",
    "SPY",
    "QQQ",
]

SYMBOL_LABELS = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "^DJI": "Dow",
    "^VIX": "VIX",
    "^TNX": "US 10Y",
    "CL=F": "WTI",
    "GC=F": "Gold",
    "KRW=X": "USD/KRW",
    "BTC-USD": "BTC/USD",
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "SPY": "SPY ETF",
    "QQQ": "QQQ ETF",
}

PERIOD_MAP = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "2Y": "2y",
    "5Y": "5y",
    "10Y": "10y",
}

INTERVAL_MAP = {"1D": "1d", "1W": "1wk", "1M": "1mo"}

PROJECT_ROOT = Path(__file__).resolve().parents[3]
KOREA_SNAPSHOT_PATH = PROJECT_ROOT / "data" / "korea_universe_screen_snapshot_2026-06-01.csv"
KOREA_SNAPSHOT_AS_OF = "2026-06-01"
NAVER_MARKET_LABELS = {"KOSPI": "0", "KOSDAQ": "1"}
NAVER_CACHE_TTL = timedelta(minutes=30)
_KOREA_UNIVERSE_CACHE: dict[str, dict[str, Any]] = {}

CHART_CACHE_TTL = timedelta(seconds=60)
_CHART_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}

NASDAQ100_PATH = PROJECT_ROOT / "data" / "nasdaq100_sectors.csv"
KOSPI_SECTORS_PATH = PROJECT_ROOT / "data" / "kospi_sectors.csv"
HEATMAP_CACHE_TTL = timedelta(minutes=30)
_HEATMAP_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if pd.isna(number):
            return None
        return round(number, 4)
    except Exception:
        return None


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "").replace("+", "")
    if not text or text.upper() in {"N/A", "NA", "NAN", "-"}:
        return None
    return _safe_float(text)


def _symbol_for_krx(code: str, market: str) -> str:
    suffix = "KQ" if market == "KOSDAQ" else "KS"
    return f"{str(code).zfill(6)}.{suffix}"


class _NaverMarketSumParser(HTMLParser):
    def __init__(self, market: str):
        super().__init__(convert_charrefs=True)
        self.market = market
        self.rows: list[dict[str, Any]] = []
        self._in_tr = False
        self._in_td = False
        self._cells: list[str] = []
        self._cell_parts: list[str] = []
        self._code: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._in_tr = True
            self._cells = []
            self._code = None
        elif self._in_tr and tag == "td":
            self._in_td = True
            self._cell_parts = []
        elif self._in_tr and tag == "a":
            href = dict(attrs).get("href") or ""
            match = re.search(r"/item/main\.naver\?code=(\d+)", href)
            if match:
                self._code = match.group(1).zfill(6)

    def handle_data(self, data: str) -> None:
        if self._in_td:
            text = " ".join(data.split())
            if text:
                self._cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._in_td:
            self._cells.append(" ".join(self._cell_parts).strip())
            self._in_td = False
            self._cell_parts = []
        elif tag == "tr" and self._in_tr:
            self._append_current_row()
            self._in_tr = False

    def _append_current_row(self) -> None:
        if not self._code or len(self._cells) < 12:
            return
        name = self._cells[1]
        if not name:
            return
        self.rows.append(
            {
                "market": self.market,
                "code": self._code,
                "symbol": _symbol_for_krx(self._code, self.market),
                "name": name,
                "price": _parse_number(self._cells[2]),
                "changePercent": _parse_number(self._cells[4]),
                "marketCap": _parse_number(self._cells[6]),
                "shares": _parse_number(self._cells[7]),
                "foreignRatio": _parse_number(self._cells[8]),
                "volume": _parse_number(self._cells[9]),
                "per": _parse_number(self._cells[10]),
                "roe": _parse_number(self._cells[11]),
                "currency": "KRW",
                "status": "delayed",
                "message": "네이버 금융 공개 페이지 지연 데이터",
                "source": "Naver Finance market cap page",
            }
        )


def _naver_market_page(market: str, page: int) -> tuple[list[dict[str, Any]], int]:
    sosok = NAVER_MARKET_LABELS[market]
    url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
    response = httpx.get(
        url,
        headers={"User-Agent": "KoreanFinanceTerminal/0.1 public-market-universe"},
        timeout=8,
        follow_redirects=True,
    )
    response.raise_for_status()
    parser = _NaverMarketSumParser(market)
    parser.feed(response.text)
    page_numbers = [int(match) for match in re.findall(rf"sosok={sosok}(?:&amp;|&)page=(\d+)", response.text)]
    return parser.rows, max(page_numbers or [page])


def _naver_universe(market: str) -> list[dict[str, Any]]:
    cached = _KOREA_UNIVERSE_CACHE.get(market)
    now = datetime.now(timezone.utc)
    if cached and now - cached["loaded_at"] < NAVER_CACHE_TTL:
        return cached["items"]

    first_rows, last_page = _naver_market_page(market, 1)
    items = list(first_rows)
    if last_page > 1:
        pages = list(range(2, min(last_page, 90) + 1))
        with ThreadPoolExecutor(max_workers=8) as executor:
            for rows, _ in executor.map(lambda page: _naver_market_page(market, page), pages):
                items.extend(rows)
    deduped = {item["code"]: item for item in items}
    result = list(deduped.values())
    _KOREA_UNIVERSE_CACHE[market] = {"loaded_at": now, "items": result}
    return result


def _snapshot_universe(market: str) -> list[dict[str, Any]]:
    if not KOREA_SNAPSHOT_PATH.exists():
        return []
    frame = pd.read_csv(KOREA_SNAPSHOT_PATH, dtype={"코드": str}).fillna("")
    if market in {"KOSPI", "KOSDAQ"}:
        frame = frame[frame["시장"].astype(str).str.upper() == market]
    items: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        market_name = str(row.get("시장", "")).upper()
        code = str(row.get("코드", "")).zfill(6)
        if not market_name or not code:
            continue
        items.append(
            {
                "market": market_name,
                "code": code,
                "symbol": _symbol_for_krx(code, market_name),
                "name": row.get("종목명") or code,
                "price": _parse_number(row.get("현재가")),
                "changePercent": _parse_number(row.get("등락률")),
                "marketCap": _parse_number(row.get("시가총액")),
                "volume": _parse_number(row.get("거래량")),
                "tradingValueKrw100m": _parse_number(row.get("거래대금억원_추정")),
                "per": _parse_number(row.get("PER")),
                "roe": _parse_number(row.get("ROE")),
                "screenScore": _parse_number(row.get("점수")),
                "currency": "KRW",
                "status": "delayed",
                "message": f"{KOREA_SNAPSHOT_AS_OF} 스크리닝 스냅샷",
                "source": "Local Naver/KRX screen snapshot",
            }
        )
    return items


def korea_universe(market: str = "KOSPI", query: str = "", limit: int = 100, source: str = "auto") -> dict[str, Any]:
    requested_market = (market or "KOSPI").strip().upper()
    requested_source = (source or "auto").strip().lower()
    limit = min(max(int(limit or 100), 1), 500)
    if requested_market not in {"KOSPI", "KOSDAQ", "ALL"}:
        return {
            "status": "not_available",
            "message": "지원하지 않는 한국 시장",
            "market": requested_market,
            "items": [],
            "source": "none",
            "asOf": _now(),
        }

    markets = ["KOSPI", "KOSDAQ"] if requested_market == "ALL" else [requested_market]
    items: list[dict[str, Any]] = []
    used_source = requested_source
    coverage = "full_public_page"
    errors: list[str] = []

    if requested_source in {"auto", "naver"}:
        try:
            for market_name in markets:
                items.extend(_naver_universe(market_name))
            used_source = "naver"
        except Exception as exc:
            errors.append(f"Naver universe unavailable: {type(exc).__name__}")
            if requested_source == "naver":
                return {
                    "status": "error",
                    "message": "네이버 금융 전체 목록 조회 오류",
                    "market": requested_market,
                    "query": query,
                    "items": [],
                    "errors": errors,
                    "source": "Naver Finance market cap page",
                    "asOf": _now(),
                }

    if not items and requested_source in {"auto", "snapshot"}:
        for market_name in markets:
            items.extend(_snapshot_universe(market_name))
        used_source = "snapshot"
        coverage = "screened_snapshot"

    normalized_query = (query or "").strip().upper()
    if normalized_query:
        items = [
            item
            for item in items
            if normalized_query in item["symbol"].upper()
            or normalized_query in item["code"].upper()
            or normalized_query in str(item["name"]).upper()
        ]

    items.sort(key=lambda item: (item.get("market") or "", -(item.get("marketCap") or 0), item.get("name") or ""))
    total = len(items)
    status = "delayed" if items else "not_available"
    if used_source == "naver":
        message = "네이버 금융 공개 페이지 기준 전체 목록 지연 데이터"
    elif items:
        message = f"{KOREA_SNAPSHOT_AS_OF} 후보 스크리닝 스냅샷"
    else:
        message = "한국 종목 데이터 없음"
    return {
        "status": status,
        "message": message,
        "market": requested_market,
        "query": query,
        "count": min(total, limit),
        "total": total,
        "coverage": coverage,
        "items": items[:limit],
        "source": "Naver Finance market cap page" if used_source == "naver" else "Local Naver/KRX screen snapshot",
        "sourceMode": used_source,
        "asOf": _now() if used_source == "naver" else KOREA_SNAPSHOT_AS_OF,
        "policy": "No synthetic Korean equity values. Naver public pages are delayed and not a contracted realtime feed.",
        "errors": errors,
    }


def _history_last(symbol: str) -> tuple[float | None, float | None, str | None]:
    hist = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=False)
    if hist.empty:
        return None, None, None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None, None, None
    last = _safe_float(closes.iloc[-1])
    previous = _safe_float(closes.iloc[-2]) if len(closes) >= 2 else None
    ts = hist.index[-1].isoformat() if hasattr(hist.index[-1], "isoformat") else str(hist.index[-1])
    return last, previous, ts


def _kis_quote(normalized: str) -> dict[str, Any] | None:
    """KIS 키가 있으면 한국 종목 실시간 시세를 표준 quote 형식으로 반환."""
    from ..auth import get_api_key  # lazy import to avoid import cycles

    cred = get_api_key("kis")
    if not cred:
        return None
    q = quote_price(cred, normalized)
    if not q or q.get("price") is None:
        return None
    return {
        "symbol": normalized,
        "name": SYMBOL_LABELS.get(normalized, normalized),
        "price": q["price"],
        "previousClose": q.get("previousClose"),
        "change": q.get("change"),
        "changePercent": q.get("changePercent"),
        "marketCap": None,
        "currency": "KRW",
        "status": "live",
        "message": "KIS 실시간",
        "source": q.get("source") or "KIS",
        "asOf": _now(),
    }


def quote(symbol: str) -> dict[str, Any]:
    normalized = symbol.strip().upper()
    if not normalized:
        return {"symbol": symbol, "status": "not_available", "message": "데이터 없음"}
    # 한국 종목 + KIS 키가 있으면 실시간 시세 우선(yfinance는 당일 장중 데이터를 잘 안 줌).
    if normalized.endswith((".KS", ".KQ")):
        kis_q = _kis_quote(normalized)
        if kis_q is not None:
            return kis_q
    try:
        ticker = yf.Ticker(normalized)
        fast = {}
        try:
            fast = dict(ticker.fast_info)
        except Exception:
            fast = {}
        last = _safe_float(fast.get("last_price") or fast.get("lastPrice"))
        previous = _safe_float(fast.get("previous_close") or fast.get("previousClose"))
        currency = fast.get("currency") or ""
        timestamp = _now()
        if last is None:
            last, previous, timestamp = _history_last(normalized)
        if last is None:
            return {
                "symbol": normalized,
                "name": SYMBOL_LABELS.get(normalized, normalized),
                "status": "not_available",
                "message": "데이터 없음",
                "source": "yfinance",
                "asOf": _now(),
            }
        change = _safe_float(last - previous) if previous is not None else None
        change_percent = _safe_float((change / previous) * 100) if change is not None and previous else None
        market_cap = _safe_float(fast.get("market_cap") or fast.get("marketCap"))
        return {
            "symbol": normalized,
            "name": SYMBOL_LABELS.get(normalized, normalized),
            "price": last,
            "previousClose": previous,
            "change": change,
            "changePercent": change_percent,
            "marketCap": market_cap,
            "currency": currency,
            "status": "delayed",
            "message": "지연 데이터",
            "source": "yfinance Yahoo Finance public endpoints",
            "asOf": timestamp or _now(),
        }
    except Exception as exc:
        return {
            "symbol": normalized,
            "name": SYMBOL_LABELS.get(normalized, normalized),
            "status": "error",
            "message": f"데이터 조회 오류: {type(exc).__name__}",
            "source": "yfinance",
            "asOf": _now(),
        }


def quotes(symbols: list[str]) -> list[dict[str, Any]]:
    unique = []
    for symbol in symbols:
        item = symbol.strip().upper()
        if item and item not in unique:
            unique.append(item)
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(unique)))) as executor:
        return list(executor.map(quote, unique[:40]))


FX_CACHE_TTL = timedelta(minutes=10)
_FX_CACHE: dict[str, tuple[datetime, float]] = {}


def usd_to_krw() -> float | None:
    """USD→KRW 환율 (1 USD가 몇 KRW). 10분 캐시. yfinance KRW=X 사용."""
    now = datetime.now(timezone.utc)
    cached = _FX_CACHE.get("USDKRW")
    if cached and now - cached[0] < FX_CACHE_TTL:
        return cached[1]
    rate = _safe_float(quote("KRW=X").get("price"))
    if rate and rate > 0:
        _FX_CACHE["USDKRW"] = (now, rate)
        return rate
    return cached[1] if cached else None


# 주린이용 주요 환율 쌍 (yfinance 심볼 → 한국어 라벨, 표시 배율)
# 엔화는 한국 관례상 100엔 기준으로 표시 → mult=100
FX_PAIRS = [
    ("KRW=X", "USD/KRW", "원/달러", 1),
    ("JPYKRW=X", "JPY100/KRW", "원/100엔", 100),
    ("EURKRW=X", "EUR/KRW", "원/유로", 1),
    ("CNYKRW=X", "CNY/KRW", "원/위안", 1),
    ("JPY=X", "USD/JPY", "엔/달러", 1),
    ("EURUSD=X", "EUR/USD", "달러/유로", 1),
]


def fx_rates() -> dict[str, Any]:
    """주요 환율 쌍 목록. 좌측 소형 위젯용."""
    symbols = [pair[0] for pair in FX_PAIRS]
    raw = {q.get("symbol"): q for q in quotes(symbols)}
    items = []
    for symbol, label, korean, mult in FX_PAIRS:
        q = raw.get(symbol, {})
        price = q.get("price")
        change = q.get("change")
        items.append(
            {
                "symbol": symbol,
                "label": label,
                "korean": korean,
                "price": price * mult if price is not None else None,
                "change": change * mult if change is not None else None,
                "changePercent": q.get("changePercent"),  # 배율 무관(비율)
                "status": q.get("status", "not_available"),
            }
        )
    return {
        "items": items,
        "status": "delayed",
        "source": "yfinance Yahoo Finance public endpoints",
        "asOf": _now(),
    }


def market_overview() -> dict[str, Any]:
    data = quotes(DEFAULT_MARKET_SYMBOLS)
    gainers = [item for item in data if (item.get("changePercent") or 0) > 0]
    decliners = [item for item in data if (item.get("changePercent") or 0) < 0]
    return {
        "status": "ok",
        "source": "yfinance Yahoo Finance public endpoints",
        "policy": "No synthetic market values. Missing providers return explicit status.",
        "asOf": _now(),
        "quotes": data,
        "breadth": {
            "advancers": len(gainers),
            "decliners": len(decliners),
            "unchangedOrMissing": len(data) - len(gainers) - len(decliners),
        },
    }


def historical_chart(symbol: str, period: str, interval: str) -> dict[str, Any]:
    yf_period = PERIOD_MAP.get(period.upper())
    yf_interval = INTERVAL_MAP.get(interval.upper())
    normalized = symbol.strip().upper()
    if not yf_period or not yf_interval:
        return {
            "symbol": normalized,
            "status": "not_available",
            "message": "지원하지 않는 기간 또는 인터벌",
            "points": [],
        }
    cache_key = f"{normalized}|{period.upper()}|{interval.upper()}"
    cached = _CHART_CACHE.get(cache_key)
    if cached and datetime.now(timezone.utc) - cached[0] < CHART_CACHE_TTL:
        return cached[1]
    try:
        frame = yf.Ticker(normalized).history(period=yf_period, interval=yf_interval, auto_adjust=False)
        if frame.empty:
            return {
                "symbol": normalized,
                "period": period,
                "interval": interval,
                "status": "not_available",
                "message": "데이터 없음",
                "points": [],
                "source": "yfinance",
                "asOf": _now(),
            }
        frame = add_indicators(frame.dropna(how="all").copy())
        payload = {
            "symbol": normalized,
            "period": period,
            "interval": interval,
            "status": "delayed",
            "message": "지연 데이터",
            "source": "yfinance Yahoo Finance public endpoints",
            "asOf": _now(),
            "points": frame_to_points(frame),
        }
        _CHART_CACHE[cache_key] = (datetime.now(timezone.utc), payload)
        return payload
    except Exception as exc:
        return {
            "symbol": normalized,
            "period": period,
            "interval": interval,
            "status": "error",
            "message": f"차트 조회 오류: {type(exc).__name__}",
            "points": [],
            "source": "yfinance",
            "asOf": _now(),
        }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        with open(path, encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows.append(row)
    except Exception:
        return []
    return rows


def _heatmap_nasdaq() -> dict[str, Any]:
    rows = _read_csv_rows(NASDAQ100_PATH)
    symbols = [r["symbol"] for r in rows]
    quote_map = {q["symbol"]: q for q in quotes(symbols)}
    # Retry symbols Yahoo throttled on the first burst (no market cap returned).
    missing = [s for s in symbols if not quote_map.get(s.upper(), {}).get("marketCap")]
    if missing:
        for retry_quote in quotes(missing):
            if retry_quote.get("marketCap"):
                quote_map[retry_quote["symbol"]] = retry_quote
    items: list[dict[str, Any]] = []
    for row in rows:
        data = quote_map.get(row["symbol"].upper(), {})
        items.append(
            {
                "symbol": row["symbol"],
                "name": row.get("name") or row["symbol"],
                "sector": row.get("sector") or "기타",
                "marketCap": data.get("marketCap"),
                "changePercent": data.get("changePercent"),
                "price": data.get("price"),
            }
        )
    return {
        "market": "NASDAQ100",
        "status": "delayed",
        "message": "지연 데이터",
        "source": "yfinance Yahoo Finance public endpoints + 내장 섹터 매핑",
        "asOf": _now(),
        "items": items,
    }


def _heatmap_kospi() -> dict[str, Any]:
    universe = korea_universe("KOSPI", limit=300)
    sector_map = {row["code"]: row.get("sector") or "기타" for row in _read_csv_rows(KOSPI_SECTORS_PATH)}
    items: list[dict[str, Any]] = []
    for item in universe.get("items", []):
        if not item.get("marketCap"):
            continue
        items.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "sector": sector_map.get(item["code"], "기타"),
                "marketCap": item.get("marketCap"),
                "changePercent": item.get("changePercent"),
                "price": item.get("price"),
            }
        )
    items.sort(key=lambda entry: entry["marketCap"] or 0, reverse=True)
    items = items[:140]
    return {
        "market": "KOSPI",
        "status": universe.get("status", "delayed"),
        "message": universe.get("message", "지연 데이터"),
        "source": f"{universe.get('source', 'Naver Finance')} + 내장 섹터 매핑",
        "asOf": _now(),
        "items": items,
    }


def _has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def _search_korea(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for market in ("KOSPI", "KOSDAQ"):
        try:
            data = korea_universe(market, query=text, limit=8)
        except Exception:
            continue
        for item in data.get("items", []):
            symbol = item.get("symbol")
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            out.append({"symbol": symbol, "name": item.get("name") or symbol, "exchange": market, "type": "EQUITY"})
    return out


def _search_yahoo(text: str) -> list[dict[str, Any]]:
    response = httpx.get(
        "https://query2.finance.yahoo.com/v1/finance/search",
        params={"q": text, "quotesCount": 12, "newsCount": 0, "lang": "en-US"},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) korean-finance-terminal"},
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()
    out: list[dict[str, Any]] = []
    for item in payload.get("quotes", []):
        symbol = item.get("symbol")
        if not symbol:
            continue
        out.append(
            {
                "symbol": symbol,
                "name": item.get("shortname") or item.get("longname") or symbol,
                "exchange": item.get("exchDisp") or item.get("exchange") or "",
                "type": item.get("quoteType") or "",
            }
        )
    return out


EARNINGS_CACHE_TTL = timedelta(minutes=10)
_EARNINGS_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}


def equity_calendar(symbol: str) -> dict[str, Any]:
    normalized = symbol.strip().upper()
    if not normalized:
        return {"symbol": symbol, "status": "not_available", "message": "데이터 없음"}
    cached = _EARNINGS_CACHE.get(normalized)
    if cached and datetime.now(timezone.utc) - cached[0] < EARNINGS_CACHE_TTL:
        return cached[1]
    try:
        ticker = yf.Ticker(normalized)
        try:
            info = ticker.get_info() or {}
        except Exception:
            info = {}
        # yfinance returns dividendYield already as a percentage (e.g. 0.35 == 0.35%).
        raw_yield = info.get("dividendYield")
        dividend_yield = round(raw_yield, 2) if isinstance(raw_yield, (int, float)) else None
        ex_div = info.get("exDividendDate")
        ex_div_date = None
        if isinstance(ex_div, (int, float)):
            ex_div_date = datetime.fromtimestamp(ex_div, timezone.utc).date().isoformat()
        earnings_date = None
        try:
            calendar = ticker.calendar
            entry = calendar.get("Earnings Date") if isinstance(calendar, dict) else None
            if entry:
                first = entry[0] if isinstance(entry, (list, tuple)) else entry
                earnings_date = str(first)
        except Exception:
            earnings_date = None
        payload = {
            "symbol": normalized,
            "name": info.get("shortName") or SYMBOL_LABELS.get(normalized, normalized),
            "earningsDate": earnings_date,
            "dividendYield": dividend_yield,
            "exDividendDate": ex_div_date,
            "trailingEps": _safe_float(info.get("trailingEps")),
            "forwardPE": _safe_float(info.get("forwardPE")),
            "status": "delayed",
            "source": "yfinance Yahoo Finance public endpoints",
            "asOf": _now(),
        }
        _EARNINGS_CACHE[normalized] = (datetime.now(timezone.utc), payload)
        return payload
    except Exception as exc:
        return {
            "symbol": normalized,
            "status": "error",
            "message": f"실적/배당 조회 오류: {type(exc).__name__}",
            "source": "yfinance",
            "asOf": _now(),
        }


def search_symbols(query: str) -> dict[str, Any]:
    text = query.strip()
    if not text:
        return {"query": text, "results": []}
    try:
        if _has_hangul(text) or text.isdigit():
            results = _search_korea(text)
            source = "Naver Finance 종목 검색"
        else:
            results = _search_yahoo(text)
            source = "Yahoo Finance search"
        return {"query": text, "results": results, "source": source, "status": "delayed"}
    except Exception as exc:
        return {"query": text, "results": [], "status": "error", "message": type(exc).__name__}


def market_heatmap(market: str = "NASDAQ100") -> dict[str, Any]:
    key = market.strip().upper()
    cached = _HEATMAP_CACHE.get(key)
    if cached and datetime.now(timezone.utc) - cached[0] < HEATMAP_CACHE_TTL:
        return cached[1]
    if key == "NASDAQ100":
        payload = _heatmap_nasdaq()
    elif key == "KOSPI":
        payload = _heatmap_kospi()
    else:
        return {"market": market, "status": "not_available", "message": "지원하지 않는 시장", "items": []}
    _HEATMAP_CACHE[key] = (datetime.now(timezone.utc), payload)
    return payload


def options_chain(symbol: str) -> dict[str, Any]:
    normalized = symbol.strip().upper()
    try:
        ticker = yf.Ticker(normalized)
        expirations = list(ticker.options or [])
        if not expirations:
            return {
                "symbol": normalized,
                "status": "not_available",
                "message": "옵션 데이터 없음",
                "expirations": [],
                "calls": [],
                "puts": [],
                "source": "yfinance",
            }
        expiry = expirations[0]
        chain = ticker.option_chain(expiry)
        cols = ["contractSymbol", "strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]
        return {
            "symbol": normalized,
            "status": "delayed",
            "message": "지연 데이터",
            "source": "yfinance Yahoo Finance public endpoints",
            "expiration": expiry,
            "expirations": expirations[:12],
            "calls": chain.calls[cols].head(30).fillna("").to_dict("records"),
            "puts": chain.puts[cols].head(30).fillna("").to_dict("records"),
        }
    except Exception as exc:
        return {
            "symbol": normalized,
            "status": "error",
            "message": f"옵션 조회 오류: {type(exc).__name__}",
            "expirations": [],
            "calls": [],
            "puts": [],
            "source": "yfinance",
        }
