"""한국투자증권(KIS) OpenAPI — 모의투자(paper) 어댑터 (국내주식).

이 모듈은 **모의투자 도메인만** 사용한다(openapivts...). 실전 도메인은 절대
호출하지 않는다 — 실거래는 이 앱 범위 밖이며 별도 안전장치가 필요하다.

자격증명은 사용자별 암호화 저장(provider='kis')되며, JSON 문자열
{"appkey","appsecret","account_no"} 형태다. account_no는 "12345678-01" 또는
"1234567801" 형식을 받아 CANO(앞 8자리) + ACNT_PRDT_CD(뒤 2자리)로 분리한다.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

# 모의투자 전용 도메인 (실전 도메인 사용 금지)
KIS_MOCK_BASE = "https://openapivts.koreainvestment.com:29443"

# 모의투자 tr_id (현행 2025 샘플 기준) — 국내주식
TR_BUY = "VTTC0012U"
TR_SELL = "VTTC0011U"
TR_BALANCE = "VTTC8434R"

# 모의투자 tr_id — 해외주식(미국). 지정가(00)만 지원, 시장가 불가.
# 출처: koreainvestment/open-trading-api (overseas_stock).
TR_OVRS_BUY = "VTTT1002U"
TR_OVRS_SELL = "VTTT1006U"
TR_OVRS_BALANCE = "VTTS3012R"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KoreanFinanceTerminal/0.1"

# 토큰 캐시: appkey -> (access_token, expiry_epoch). KIS는 6시간 내 재발급 시
# 카카오톡 알림이 가므로 토큰을 반드시 캐시·재사용한다.
_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


class KisError(Exception):
    """KIS 자격증명/요청 오류."""


def parse_credential(raw: str | None) -> dict[str, str]:
    """저장된 JSON 자격증명 문자열을 파싱·검증."""
    if not raw:
        raise KisError("KIS 자격증명이 없습니다. 설정에서 appkey/appsecret/계좌번호를 입력하세요.")
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise KisError("KIS 자격증명 형식 오류") from exc
    appkey = (data.get("appkey") or "").strip()
    appsecret = (data.get("appsecret") or "").strip()
    account_no = (data.get("account_no") or "").strip()
    if not appkey or not appsecret or not account_no:
        raise KisError("appkey/appsecret/계좌번호가 모두 필요합니다.")
    digits = re.sub(r"\D", "", account_no)
    if len(digits) < 10:
        raise KisError("계좌번호는 10자리(예: 12345678-01)여야 합니다.")
    return {
        "appkey": appkey,
        "appsecret": appsecret,
        "cano": digits[:8],
        "acnt_prdt_cd": digits[8:10],
    }


def _get_token_sync(appkey: str, appsecret: str) -> str:
    cached = _TOKEN_CACHE.get(appkey)
    now = time.time()
    if cached and cached[1] - 60 > now:
        return cached[0]
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{KIS_MOCK_BASE}/oauth2/tokenP",
            headers={"Content-Type": "application/json"},
            json={"grant_type": "client_credentials", "appkey": appkey, "appsecret": appsecret},
        )
    if resp.status_code != 200:
        raise KisError(f"토큰 발급 실패 (HTTP {resp.status_code})")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise KisError(f"토큰 응답 오류: {data.get('msg1') or data}")
    expires_in = int(data.get("expires_in") or 86400)
    _TOKEN_CACHE[appkey] = (token, now + expires_in)
    return token


def quote_price(raw_credential: str | None, symbol: str) -> dict | None:
    """KIS 국내주식 현재가 (동기). 실패 시 None 반환(호출측이 yfinance fallback)."""
    try:
        cred = parse_credential(raw_credential)
    except Exception:
        return None
    pdno = re.sub(r"\D", "", symbol)[:6]
    if len(pdno) != 6:
        return None
    try:
        token = _get_token_sync(cred["appkey"], cred["appsecret"])
        headers = _base_headers(token, cred, "FHKST01010100")
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{KIS_MOCK_BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=headers,
                params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": pdno},
            )
        data = resp.json() if resp.content else {}
        if data.get("rt_cd") != "0":
            return None
        out = data.get("output") or {}
        price = _to_float(out.get("stck_prpr"))
        if price is None:
            return None
        change = _to_float(out.get("prdy_vrss"))
        sign = str(out.get("prdy_vrss_sign") or "")
        if change is not None and sign in ("4", "5"):  # 4 하락, 5 하한
            change = -abs(change)
        prev = price - change if change is not None else None
        pct = _to_float(out.get("prdy_ctrt"))
        if pct is not None and sign in ("4", "5"):
            pct = -abs(pct)
        return {
            "price": price,
            "previousClose": prev,
            "change": change,
            "changePercent": pct,
            "currency": "KRW",
            "source": "KIS 실시간(모의 도메인)",
        }
    except Exception:
        return None


async def _get_token(appkey: str, appsecret: str) -> str:
    cached = _TOKEN_CACHE.get(appkey)
    now = time.time()
    if cached and cached[1] - 60 > now:  # 만료 60초 전까지 재사용
        return cached[0]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{KIS_MOCK_BASE}/oauth2/tokenP",
            headers={"Content-Type": "application/json"},
            json={"grant_type": "client_credentials", "appkey": appkey, "appsecret": appsecret},
        )
    if resp.status_code != 200:
        raise KisError(f"토큰 발급 실패 (HTTP {resp.status_code})")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise KisError(f"토큰 응답 오류: {data.get('msg1') or data}")
    expires_in = int(data.get("expires_in") or 86400)
    _TOKEN_CACHE[appkey] = (token, now + expires_in)
    return token


def _base_headers(token: str, cred: dict[str, str], tr_id: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "text/plain",
        "charset": "UTF-8",
        "User-Agent": _UA,
        "authorization": f"Bearer {token}",
        "appkey": cred["appkey"],
        "appsecret": cred["appsecret"],
        "tr_id": tr_id,
        "custtype": "P",
    }


async def submit_order(
    raw_credential: str | None,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    limit_price: float | None = None,
) -> dict[str, Any]:
    """국내주식 모의 현금주문. 성공 시 주문번호 반환."""
    cred = parse_credential(raw_credential)
    pdno = re.sub(r"\D", "", symbol)[:6]
    if not pdno:
        raise KisError("국내주식 6자리 종목코드가 필요합니다 (예: 005930).")
    qty = int(quantity)
    if qty <= 0:
        raise KisError("수량은 1 이상이어야 합니다.")
    is_limit = order_type == "limit"
    ord_dvsn = "00" if is_limit else "01"  # 00 지정가, 01 시장가
    ord_unpr = str(int(limit_price)) if (is_limit and limit_price) else "0"
    tr_id = TR_BUY if side == "buy" else TR_SELL

    token = await _get_token(cred["appkey"], cred["appsecret"])
    body: dict[str, str] = {
        "CANO": cred["cano"],
        "ACNT_PRDT_CD": cred["acnt_prdt_cd"],
        "PDNO": pdno,
        "ORD_DVSN": ord_dvsn,
        "ORD_QTY": str(qty),
        "ORD_UNPR": ord_unpr,
        "EXCG_ID_DVSN_CD": "KRX",
    }
    if side == "sell":
        body["SLL_TYPE"] = "01"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{KIS_MOCK_BASE}/uapi/domestic-stock/v1/trading/order-cash",
            headers=_base_headers(token, cred, tr_id),
            json=body,
        )
    data = resp.json() if resp.content else {}
    if data.get("rt_cd") != "0":
        raise KisError(data.get("msg1") or f"주문 거부 (HTTP {resp.status_code})")
    out = data.get("output") or {}
    return {
        "status": "accepted_kis_mock",
        "mode": "kis_mock",
        "orderNo": out.get("ODNO"),
        "orderBranch": out.get("KRX_FWDG_ORD_ORGNO"),
        "orderTime": out.get("ORD_TMD"),
        "message": data.get("msg1"),
        "symbol": pdno,
        "side": side,
        "quantity": qty,
        "orderType": "limit" if is_limit else "market",
    }


async def inquire_balance(raw_credential: str | None) -> dict[str, Any]:
    """국내주식 모의 잔고 조회 (요약 + 보유종목)."""
    cred = parse_credential(raw_credential)
    token = await _get_token(cred["appkey"], cred["appsecret"])
    params = {
        "CANO": cred["cano"],
        "ACNT_PRDT_CD": cred["acnt_prdt_cd"],
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{KIS_MOCK_BASE}/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=_base_headers(token, cred, TR_BALANCE),
            params=params,
        )
    data = resp.json() if resp.content else {}
    if data.get("rt_cd") != "0":
        raise KisError(data.get("msg1") or f"잔고 조회 실패 (HTTP {resp.status_code})")
    summary = (data.get("output2") or [{}])
    summary = summary[0] if isinstance(summary, list) and summary else (summary if isinstance(summary, dict) else {})
    holdings = []
    for row in data.get("output1") or []:
        if int(row.get("hldg_qty") or 0) <= 0:
            continue
        holdings.append(
            {
                "symbol": row.get("pdno"),
                "name": row.get("prdt_name"),
                "quantity": _to_int(row.get("hldg_qty")),
                "avgPrice": _to_float(row.get("pchs_avg_pric")),
                "currentPrice": _to_float(row.get("prpr")),
                "evalAmount": _to_float(row.get("evlu_amt")),
                "pnl": _to_float(row.get("evlu_pfls_amt")),
                "pnlPercent": _to_float(row.get("evlu_pfls_rt")),
            }
        )
    return {
        "status": "ok",
        "mode": "kis_mock",
        "cash": _to_float(summary.get("dnca_tot_amt")),
        "totalEval": _to_float(summary.get("tot_evlu_amt")),
        "netAsset": _to_float(summary.get("nass_amt")),
        "totalPnl": _to_float(summary.get("evlu_pfls_smtl_amt")),
        "holdings": holdings,
    }


# ── 해외주식(미국) 모의투자 ─────────────────────────────────────────────────

# NYSE 상장으로 알려진 대표 티커(보수적). 그 외는 NASD로 본다.
# 우리 자동전략 미국 유니버스는 NASDAQ100이라 대부분 NASD다.
_NYSE_HINT = {
    "BA", "KO", "JPM", "WMT", "DIS", "V", "MA", "JNJ", "PG", "XOM", "CVX",
    "BRK.B", "UNH", "HD", "BAC", "PFE", "T", "VZ", "NKE", "MCD", "CRM", "ORCL",
}


def overseas_exchange(symbol: str) -> str:
    """티커 → KIS 해외거래소코드. 기본 NASD, 알려진 NYSE 티커만 NYSE."""
    s = (symbol or "").upper().split(".")[0]
    return "NYSE" if s in _NYSE_HINT else "NASD"


async def submit_overseas_order(
    raw_credential: str | None,
    symbol: str,
    side: str,
    quantity: float,
    limit_price: float,
    exchange: str | None = None,
) -> dict[str, Any]:
    """미국주식 모의 지정가 주문(시장가 불가). 성공 시 주문번호 반환.

    KIS 모의 해외는 ORD_DVSN='00'(지정가)만 허용하므로 limit_price 필수.
    미국 정규장(09:30~16:00 ET) 외에는 접수되어도 체결되지 않을 수 있다.
    """
    cred = parse_credential(raw_credential)
    ticker = (symbol or "").upper().split(".")[0]
    if not ticker:
        raise KisError("미국주식 티커가 필요합니다 (예: AAPL).")
    qty = int(quantity)
    if qty <= 0:
        raise KisError("수량은 1 이상이어야 합니다.")
    if not limit_price or limit_price <= 0:
        raise KisError("해외 모의는 지정가만 가능 — 주문단가가 필요합니다.")
    excg = (exchange or overseas_exchange(ticker)).upper()
    tr_id = TR_OVRS_BUY if side == "buy" else TR_OVRS_SELL
    token = await _get_token(cred["appkey"], cred["appsecret"])
    body = {
        "CANO": cred["cano"],
        "ACNT_PRDT_CD": cred["acnt_prdt_cd"],
        "OVRS_EXCG_CD": excg,
        "PDNO": ticker,
        "ORD_QTY": str(qty),
        "OVRS_ORD_UNPR": f"{float(limit_price):.2f}",
        "ORD_DVSN": "00",  # 지정가 고정(모의 제약)
        "SLL_TYPE": "" if side == "buy" else "00",
        "ORD_SVR_DVSN_CD": "0",
        "CTAC_TLNO": "",
        "MGCO_APTM_ODNO": "",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{KIS_MOCK_BASE}/uapi/overseas-stock/v1/trading/order",
            headers=_base_headers(token, cred, tr_id),
            json=body,
        )
    data = resp.json() if resp.content else {}
    if data.get("rt_cd") != "0":
        raise KisError(data.get("msg1") or f"해외 주문 거부 (HTTP {resp.status_code})")
    out = data.get("output") or {}
    return {
        "status": "accepted_kis_mock",
        "mode": "kis_mock_overseas",
        "orderNo": out.get("ODNO"),
        "orderTime": out.get("ORD_TMD"),
        "message": data.get("msg1"),
        "symbol": ticker,
        "exchange": excg,
        "side": side,
        "quantity": qty,
        "orderType": "limit",
        "limitPrice": float(limit_price),
    }


async def inquire_overseas_balance(raw_credential: str | None, exchange: str = "NASD") -> dict[str, Any]:
    """미국주식 모의 잔고 조회(거래소별). 보유종목 + 손익 요약."""
    cred = parse_credential(raw_credential)
    token = await _get_token(cred["appkey"], cred["appsecret"])
    params = {
        "CANO": cred["cano"],
        "ACNT_PRDT_CD": cred["acnt_prdt_cd"],
        "OVRS_EXCG_CD": exchange,
        "TR_CRCY_CD": "USD",
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": "",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{KIS_MOCK_BASE}/uapi/overseas-stock/v1/trading/inquire-balance",
            headers=_base_headers(token, cred, TR_OVRS_BALANCE),
            params=params,
        )
    data = resp.json() if resp.content else {}
    if data.get("rt_cd") != "0":
        raise KisError(data.get("msg1") or f"해외 잔고 조회 실패 (HTTP {resp.status_code})")
    summary = data.get("output2") or {}
    if isinstance(summary, list):
        summary = summary[0] if summary else {}
    holdings = []
    for row in data.get("output1") or []:
        if int(float(row.get("ovrs_cblc_qty") or 0)) <= 0:
            continue
        holdings.append({
            "symbol": row.get("ovrs_pdno"),
            "name": row.get("ovrs_item_name"),
            "quantity": _to_int(row.get("ovrs_cblc_qty")),
            "avgPrice": _to_float(row.get("pchs_avg_pric")),
            "currentPrice": _to_float(row.get("now_pric2")),
            "evalAmount": _to_float(row.get("ovrs_stck_evlu_amt")),
            "pnl": _to_float(row.get("frcr_evlu_pfls_amt")),
            "pnlPercent": _to_float(row.get("evlu_pfls_rt")),
            "exchange": row.get("ovrs_excg_cd"),
            "currency": row.get("tr_crcy_cd") or "USD",
        })
    return {
        "status": "ok",
        "mode": "kis_mock_overseas",
        "exchange": exchange,
        "totalEvalPnl": _to_float(summary.get("tot_evlu_pfls_amt")),
        "totalProfitRate": _to_float(summary.get("tot_pftrt")),
        "buyAmountUsd": _to_float(summary.get("frcr_buy_amt_smtl1")),
        "holdings": holdings,
    }


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None
