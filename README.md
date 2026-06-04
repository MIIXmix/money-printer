# 돈복사기 (money-printer)

주식 투자자를 위한 고밀도 한국어 금융 터미널 + **규칙 기반 자동매매 연구 도구**입니다. 미국·한국 주식, ETF, 지수, 금리, 원자재, 환율, 섹터 히트맵, 뉴스, SEC·DART 공시, 옵션, 포트폴리오(원화 환산), 모의 주문(내부 + KIS 모의투자), 사용자 정의 전략 빌더와 자동 실행을 한 화면에서 다룹니다.

> ⚠️ **이름은 농담입니다. 수익을 보장하지 않습니다.** 이 앱은 **페이퍼/모의 전용** 연구·학습 도구입니다. 실제 매매 권유가 아니며, 모든 백테스트는 과거 데이터 기반으로 미래 수익을 약속하지 않습니다. 거래비용·세금·슬리피지·시장 위험으로 실현 수익은 더 낮을 수 있고 원금 손실이 가능합니다.

**개인 사용자용 로컬 앱**입니다. 각자 자기 PC에서 실행하고, 마스터 비밀번호로 앱 전체를 잠급니다. 데이터·API 키·전략은 모두 본인 기기(`​.data`)에만 저장됩니다.

**책임투자 설계**: 투자가 너무 쉬워 보이지 않게 위험 고지·면책, 거래비용 안내(수수료·세금 별도), 집중도 경고를 곳곳에 둡니다. 자동매매도 리스크 가드(일손실·낙폭 정지)를 전략 위에 강제하고, **AI는 주문 결정에 절대 관여하지 않습니다**(코드·요약 보조만).

기본 원칙: 가짜 시장 숫자는 표시하지 않습니다. 값이 없거나 키가 필요한 경우 `데이터 없음`, `API 필요`, `지연 데이터` 상태를 UI와 API 응답에 그대로 노출합니다.

## 로그인 우선 + 첫 실행 온보딩

- **앱 전체 잠금**: 최초 실행 시 마스터 비밀번호를 설정합니다. 이후 모든 화면(시세·차트·뉴스·포트폴리오 포함)은 잠금 해제 후에만 보입니다.
- **분실 시 복구 불가**: 로컬 단일 사용자 앱이라 비밀번호 재설정 경로가 없습니다. 비밀번호를 잊으면 `.data` 폴더를 지우고 처음부터 다시 설정해야 합니다(저장된 포트폴리오·키 삭제됨).
- **단계별 온보딩 마법사**: 첫 설정 직후 ①앱 소개 + 위험 고지(원금 손실·정보용·지연 데이터·모의) ②Gemini 키 발급 안내 ③DART 키(선택) ④완료 순서로 안내합니다. 키는 모두 선택이며 건너뛸 수 있습니다.
- **키 없이도 동작**: 시세·차트·한국 뉴스는 키 없이 바로 사용됩니다. 키는 AI 번역/분석(Gemini), 한국 전자공시(DART)를 추가로 켭니다.

## 현재 구현

- 포트폴리오: 종목 검색(회사명/티커), 시장 선택(미국/코스피/코스닥), **현재가로 담기**(평단=실시간 시세) + 평단 직접 입력, 현재가·예상금액 미리보기, 보유 추가·수정·**부분 매도**·삭제(중복 종목 가중평균 합산), 종목 클릭 → 차트, **원화(KRW) 환산** 총 평가/원금/손익/수익률, 종목별 비중 도넛, 섹터/국가/통화 배분
- 책임투자 가드레일: 위험 고지·상시 면책, 거래비용 안내(수수료·세금 별도 → 실제 수익률 더 낮음), 분산/집중도 경고(단일 종목·40%/60%+)
- 모의 주문: **내부 모의**(즉시 기록) + **KIS 모의투자**(한국투자증권 OpenAPI 모의 도메인 — 토큰·현금주문·잔고). 실거래 도메인은 호출하지 않음
- 환율 위젯: USD·EUR·CNY/KRW, JPY는 100엔 기준, USD/JPY, EUR/USD (60초 갱신)
- 섹터 히트맵: 코스피·나스닥100 트리맵 (시작 시 백그라운드 워밍 → 즉시 표시)
- 한국 종목: KOSPI/KOSDAQ 목록을 네이버 금융 공개 페이지에서 지연 조회(시작 시 워밍 → 회사명 검색 즉시), 실패 시 내장 스냅샷 fallback
- 사용자별 레이아웃 저장, API 키 암호화 저장
- 차트: lightweight-charts 기반 풀 인터랙티브 차트
  - 차트 타입: 캔들 / 하이킨아시 / 바 / 라인 / 영역 / 베이스라인
  - 스케일: 일반 / 로그 / % · 휠 확대·축소, 드래그 이동, 크로스헤어/OHLC 레전드
  - 가격 오버레이(토글): 거래량, 볼린저밴드, 일목구름표(전환·기준·선행A/B·후행선 + 음영 구름, 26봉 선행 투영), VWAP, Parabolic SAR, 피봇 지지/저항(P·R1·R2·S1·S2)
  - 이동평균: 클릭으로 추가/삭제, 종류(SMA·EMA)·기간 순환 변경 (클라이언트 계산)
  - 보조지표 별도 패널(토글): RSI, MACD, 스토캐스틱, ADX/+DI/-DI, ATR, OBV
  - 그리기 도구: 추세선, 수평선, 피보나치 되돌림 (클릭 작도, 전체 지우기)
- 기간: `1M / 3M / 6M / 1Y / 2Y / 5Y / 10Y`
- 인터벌: `1D / 1W / 1M`
- UI: 상단 전역 메뉴, 명령창, AI 버튼, 지수 스트립, 내부 탭, 드래그앤드롭 위젯, 위젯 세로 리사이즈, 좌/중앙/우 패널 폭 조절
- 주문: 기본 모의(내부 + KIS 모의투자). 실거래 API 경로는 서버 플래그가 꺼져 있으면 차단
- **전략 빌더 & 자동매매(페이퍼 전용)**: 지표 조건(이동평균·RSI·MACD·볼린저·일목 등)을 AND로 조합해 진입/청산/손절/익절 전략을 만들고, 종목별 백테스트(룩어헤드 제거·다음봉 시가 체결·한국 매도세 반영) 후 ON 토글로 자동 실행. 멀티에셋 모멘텀 **로테이션 엔진**(월간 리밸런싱·롱온리·결정적)도 내장. 신규 사용자는 기본 예시 전략 **Example 1**(SMA 골든크로스, 비활성)이 1개 시드됩니다. 리스크 가드(일손실 −5% 매수금지·전체 낙폭 −20% 정지·단일 비중·현금 하한)는 전략 위에 강제되며 **AI는 주문 경로에 관여하지 않습니다**.

자세한 사용 절차는 **[사용법 가이드(HOW TO USE)](docs/HOW_TO_USE.md)** 참고.

## 빠른 실행 (원클릭)

사전 준비: **Python 3.11+**, **Node.js 18+** 설치 (각각 python.org, nodejs.org).

1. `start.bat` 더블클릭 (또는 PowerShell에서 `./start.ps1`).
2. 스크립트가 자동으로: 가상환경 생성 → 백엔드 의존성 설치 → 프론트 빌드 → `127.0.0.1:8000` 서빙 → 브라우저 자동 오픈.
3. 첫 화면에서 **마스터 비밀번호 설정** → 온보딩 마법사 → 사용 시작.
4. 종료: 실행 중인 터미널 창에서 `Ctrl+C`.

> 루프백(`127.0.0.1`)에만 바인딩되어 같은 네트워크의 다른 기기에서 접근할 수 없습니다.

수동 실행이 필요하면:

```powershell
cd path\to\korean_finance_terminal
npm install; npm run build
python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

프론트 개발 서버(HMR)가 필요하면 별도 터미널에서 `npm run dev` (→ `http://127.0.0.1:5173`).

## API 키 (모두 선택, 앱 안에서 입력)

키 없이도 `yfinance` 기반 공개 지연 시세·차트, 한국/미국 뉴스(RSS), SEC EDGAR 공개 API가 동작합니다. 키는 **온보딩 마법사 또는 설정에서 직접 입력**하며, 사용자별로 암호화되어 `.data`에만 저장됩니다(`.env`에 넣지 않아도 됩니다).

- **Gemini**(AI 번역·분석): https://aistudio.google.com/app/apikey → 로그인 → Create API key → 복사 후 입력
- **DART**(한국 전자공시): https://opendart.fss.or.kr → 인증키 신청/관리 → 오픈API 인증키 신청 → 이메일로 수신 후 입력
- **KIS 모의투자**(한국투자증권, 선택): https://apiportal.koreainvestment.com → **모의투자** 신청 → 앱키·시크릿·모의 계좌번호 발급 → 주문 탭 `KIS 모의투자`에 입력. 실거래 아님(모의 도메인만 사용).

| 범위 | 기본 구현 | 키 필요 | 상태 정책 |
| --- | --- | --- | --- |
| 미국 주식/ETF/지수/원자재/FX/한국 주식 | yfinance 공개 엔드포인트 | 없음 | `지연 데이터`, 실패 시 `데이터 없음` |
| KOSPI/KOSDAQ 종목 목록 | Naver Finance 시가총액 공개 페이지 | 없음 | `지연 데이터`, 실패 시 `스냅샷` |
| SEC 공시 | SEC `data.sec.gov` | 없음, `SEC_USER_AGENT` 권장 | `지연/공개 데이터` |
| DART 공시 | OpenDART | `DART_API_KEY` | 없으면 `API 필요` |
| AI 요약/번역 | 로컬 규칙 기반 | `GEMINI_API_KEY` 선택 | 없으면 로컬 요약 |
| 옵션 | yfinance option chain | 없음 | 없으면 `옵션 데이터 없음` |
| 모의 주문 | 내부 모의(기록) | 없음 | 즉시 `accepted_paper` |
| KIS 모의투자 | 한국투자증권 OpenAPI(모의 도메인) | KIS 앱키·시크릿·모의계좌 | 없으면 `KIS 키 필요` |

## 문서

- [사용법 가이드 (HOW TO USE)](docs/HOW_TO_USE.md)
- [API 키 설정](docs/API_KEYS.md)
- [데이터 출처와 제한](docs/DATA_SOURCES.md)
- [보안/로그인/API 키 저장](docs/SECURITY.md)
- [브로커 연동 구조](docs/BROKERS.md)
- [실서버 배포](docs/DEPLOYMENT.md)
- [레이아웃 커스터마이징](docs/LAYOUT_CUSTOMIZATION.md)
- [실제/가짜 데이터 정책](docs/REAL_DATA_POLICY.md)

## 검증 명령

```powershell
npm run build
npm run lint
backend\.venv\Scripts\python -m compileall backend\app
backend\.venv\Scripts\python -m pytest backend\tests -q
```

차트 기간/인터벌 변경 확인:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/market/chart?symbol=AAPL&period=1M&interval=1D"
Invoke-RestMethod "http://127.0.0.1:8000/api/market/chart?symbol=AAPL&period=1Y&interval=1W"
Invoke-RestMethod "http://127.0.0.1:8000/api/market/korea/universe?market=KOSPI&limit=20"
Invoke-RestMethod "http://127.0.0.1:8000/api/market/korea/universe?market=KOSDAQ&query=테크윙&limit=5"
```

안전 ZIP 생성:

```powershell
.\scripts\package_project.ps1
```

이 스크립트는 `.env`, `.data`, `.runlogs`, `node_modules`, `backend\.venv`를 제외하고 ZIP 내부에 비밀키가 들어가지 않았는지 검사합니다.

## 보안 모델

- **앱 비밀**(`APP_SECRET`)은 최초 실행 시 강력한 난수로 자동 생성되어 `.data/secret.key`에 저장됩니다. 별도로 설정할 필요가 없으며, 약한 placeholder가 배포에 섞이지 않습니다.
- **인증**: 단일 마스터 비밀번호. PBKDF2-HMAC-SHA256(320k iterations) 해싱, HMAC 서명·만료(기본 4시간)·버전 기반 토큰. 비밀번호 변경 시 기존 토큰 무효화. 로그인 시도 제한(throttle).
- **API 키 암호화**: 사용자가 입력한 Gemini/DART 키는 Fernet으로 암호화되어 DB에 저장됩니다(평문 저장 안 함). 토큰 서명 키와 암호화 키는 HKDF로 분리 파생됩니다.
- **전체 잠금**: 모든 데이터/AI/포트폴리오 라우트가 인증을 요구합니다. 응답에 보안 경고·키 설정 상태를 노출하지 않습니다.
- **전송/헤더**: 루프백 바인딩, CSP·X-Frame-Options·nosniff 등 보안 헤더, CORS 제한, 입력 검증(심볼/코드 길이·형식, 설정 키 allowlist).
- **절대 배포에 포함 금지**: `.env`, `.data/`(DB·secret.key)는 `.gitignore` 및 패키징 스크립트에서 제외됩니다. ZIP/공유 전 이 파일들이 들어가지 않았는지 확인하세요.

## 운영 주의

- 마스터 비밀번호는 복구 불가. 분실 시 `.data` 폴더 삭제 후 재설정(저장 데이터 삭제됨).
- yfinance는 Yahoo가 공식 보증하는 상업용 API가 아닙니다. 개인 학습·정보용이며 상업/고신뢰 실시간 용도는 정식 데이터 계약이 필요합니다.
- `LIVE_TRADING_ENABLED=false`가 기본값입니다. 실거래는 별도 어댑터와 명시 활성화 없이는 실행하지 않습니다.
- KIS 연동은 **모의투자 도메인(openapivts)만** 호출합니다. 실거래(실전 도메인)는 의도적으로 미구현이며, 켜려면 별도 어댑터 + 안전장치(주문 확인·일일 한도·감사 로그)가 필요합니다.
- 투자 판단/매매 권유용이 아니라 데이터 통합과 상태 표시용 터미널입니다.
