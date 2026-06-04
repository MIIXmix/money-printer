"""자동전략(Paper Trading) 엔진.

안전 원칙:
- LLM/AI는 코드·요약에만. 매수/매도 판단은 검증 가능한 StrategyEngine → RiskManager
  → PaperBroker만 통과한다.
- 실제 브로커 호출·실전 주문 없음. 전부 모의(paper). 실전 전환은 문서·체크리스트·게이트만.
- 데이터 없으면 가짜 가격을 만들지 않는다. dataStatus를 항상 기록한다.
- 수익 보장 표현 금지. 규칙 기반 계량 전략일 뿐이다.
"""
