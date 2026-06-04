"""KIS 실시간 시세(웹소켓) — 한국주 체결가 스트림 → 1분봉 합성. **Phase 5b 설계/인터페이스.**

⚠️ 이 모듈은 구조(스켈레톤)만 제공한다. 실제 웹소켓 연결·체결은 한국 정규장
(09:00~15:30 KST)에서만 검증 가능하므로 자동 시작하지 않는다. 활성화·검증은 장중에.

KIS 실시간 흐름(모의 도메인):
  1. approval_key 발급: POST {REST}/oauth2/Approval  body {grant_type:client_credentials, appkey, secretkey}
     - 주의: 일반 access_token과 별개. 웹소켓 인증용 키.
  2. 웹소켓 접속: ws://ops.koreainvestment.com:31000 (실전) / 모의 동일 포트 계열
     (실시간 도메인은 실전/모의 공용인 경우가 있어 장중 확인 필요)
  3. 구독 메시지: tr_id 'H0STCNT0'(국내주식 실시간 체결가), tr_key=종목코드(6자리)
     header에 approval_key, custtype 'P'
  4. 수신: '|' 구분 체결 데이터 스트림. 체결가/체결시각 파싱 → 1분봉 OHLCV 합성.

실시간 미국주는 KIS/yfinance 무료로는 사실상 불가(유료 피드 필요) — 미국은 지연 분봉 유지.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# 실시간 도메인(장중 검증 필요). 실전/모의 구분은 KIS 문서 기준 장중 확인.
KIS_WS_URL = "ws://ops.koreainvestment.com:31000"
KIS_WS_TR_TRADE = "H0STCNT0"  # 국내주식 실시간 체결가


@dataclass
class MinuteBar:
    minute: str            # 'YYYY-MM-DDTHH:MM'
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class BarAggregator:
    """체결 틱을 1분봉으로 누적. 분이 바뀌면 직전 봉을 확정해 emit."""
    bars: dict[str, list[MinuteBar]] = field(default_factory=dict)  # symbol -> 확정 1분봉들
    _cur: dict[str, MinuteBar] = field(default_factory=dict)

    def on_tick(self, symbol: str, price: float, volume: float, minute: str) -> MinuteBar | None:
        cur = self._cur.get(symbol)
        emitted: MinuteBar | None = None
        if cur is None or cur.minute != minute:
            if cur is not None:
                self.bars.setdefault(symbol, []).append(cur)
                emitted = cur
            self._cur[symbol] = MinuteBar(minute, price, price, price, price, volume)
        else:
            cur.high = max(cur.high, price)
            cur.low = min(cur.low, price)
            cur.close = price
            cur.volume += volume
        return emitted

    def recent(self, symbol: str, n: int = 200) -> list[MinuteBar]:
        return (self.bars.get(symbol) or [])[-n:]


def build_approval_payload(appkey: str, appsecret: str) -> dict[str, Any]:
    """approval_key 발급 요청 body(설계). 실제 호출은 장중 검증 시."""
    return {"grant_type": "client_credentials", "appkey": appkey, "secretkey": appsecret}


def build_subscribe_message(approval_key: str, symbol_code6: str) -> str:
    """국내주식 실시간 체결가 구독 메시지(설계). symbol_code6 = 6자리 종목코드."""
    return json.dumps({
        "header": {"approval_key": approval_key, "custtype": "P", "tr_type": "1", "content-type": "utf-8"},
        "body": {"input": {"tr_id": KIS_WS_TR_TRADE, "tr_key": symbol_code6}},
    })


def parse_trade_frame(raw: str) -> dict[str, Any] | None:
    """체결 프레임 파싱(설계 스텁). '|' 구분 형식은 장중 실제 응답으로 확정 필요.

    예상 필드 위치(KIS 문서): MKSC_SHRN_ISCD(종목), STCK_PRPR(현재가), CNTG_VOL(체결량),
    STCK_CNTG_HOUR(체결시각). 실제 인덱스는 장중 응답으로 검증.
    """
    if not raw or raw[0] in ("{", "0", "1") is False:
        return None
    # 장중 검증 전까지 파싱 미구현(설계). None 반환.
    return None


# NOTE: 자동 시작/연결 없음. 장중 검증 단계에서 asyncio websocket 클라이언트로 연결,
# parse_trade_frame로 틱 추출 → BarAggregator.on_tick → 1분봉을 strategy 평가에 주입.
