"""자동 실행 스케줄러 — 로컬 앱이 떠 있는 동안 자동전략/사용자전략을 주기 평가.

두 계약을 한 루프가 처리한다:
  1. legacy 자동전략: automation_account.status == 'running' (정지 아님) → service.run_once
  2. 사용자 전략 빌더: settings.strategy_autorun + 활성 전략 존재 → run_strategies_once

가드: 정규장 시간(KR/US)에만, 중복 실행 lock, 매 틱 audit. 네트워크/DB 블로킹은
run_in_executor로 별도 스레드 실행. 실거래 경로는 호출하지 않는다(paper only).
주의: 공휴일/DST 미반영(보수적 UTC 창). 수동 run-once는 이 가드를 우회한다.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from datetime import datetime, timezone

from ..auth import get_master
from . import service, store, strategy_service

_task: asyncio.Task | None = None
_running = False  # 중복 실행 방지 lock
_awake = False    # 현재 sleep 방지 상태
_MIN_INTERVAL = 60
_DEFAULT_INTERVAL = 300

# Windows SetThreadExecutionState 플래그 — 자동화 활성 동안 PC가 잠들지 않게.
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def _set_awake(keep: bool) -> None:
    """자동화가 도는 동안만 시스템 sleep 차단(Windows). 그 외엔 정상 절전 허용."""
    global _awake
    if keep == _awake:
        return
    _awake = keep
    if sys.platform != "win32":
        return
    try:
        import ctypes
        flags = _ES_CONTINUOUS | (_ES_SYSTEM_REQUIRED if keep else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


def _interval(user_id: int) -> int:
    raw = store.get_settings_raw(user_id)
    v = raw.get("strategy_interval_sec")
    try:
        return max(_MIN_INTERVAL, int(v))
    except (TypeError, ValueError):
        return _DEFAULT_INTERVAL


def _in_session(now_utc: datetime | None = None) -> bool:
    """정규장(KR 또는 US) 시간대인지 대략 판정. 주말 제외, 공휴일/DST 미반영.

    KR 정규장 09:00~15:30 KST = 00:00~06:30 UTC.
    US 정규장 09:30~16:00 ET = 13:30~20:00(EDT)/14:30~21:00(EST) → 13:30~21:00 UTC로 포괄.
    """
    now = now_utc or datetime.now(timezone.utc)
    if now.weekday() >= 5:  # 토(5)·일(6)
        return False
    minutes = now.hour * 60 + now.minute
    kr = 0 <= minutes <= 6 * 60 + 30          # 00:00~06:30 UTC
    us = 13 * 60 + 30 <= minutes <= 21 * 60    # 13:30~21:00 UTC
    return kr or us


def _tick(uid: int) -> None:
    """동기 틱(스레드 실행). 활성 엔진 1개만 실행 — 두 시스템이 같은 장부를 다투지 않게."""
    raw = store.get_settings_raw(uid)
    acct = store.ensure_account(uid)
    if acct.get("halted"):
        return
    engine = service.active_engine(uid)
    ran = None
    if engine == "builder":
        if raw.get("strategy_autorun") and store.enabled_strategies(uid):
            try:
                strategy_service.run_strategies_once(uid, trigger="scheduled")
                ran = "strategies"
            except Exception as exc:  # noqa: BLE001
                store.insert_audit(uid, kind="lifecycle", message=f"[scheduler] 전략 오류: {type(exc).__name__}")
    else:  # legacy
        if acct.get("status") == "running":
            try:
                service.run_once(uid, trigger="scheduled")
                ran = "automation"
            except Exception as exc:  # noqa: BLE001
                store.insert_audit(uid, kind="lifecycle", message=f"[scheduler] 자동전략 오류: {type(exc).__name__}")
    if ran:
        store.insert_audit(uid, kind="lifecycle", message=f"[scheduler] 정규장 자동 실행: {engine}/{ran}")


async def _loop() -> None:
    global _running
    while True:
        delay = _DEFAULT_INTERVAL
        try:
            master = get_master()
            if master:
                uid = master["id"]
                raw = store.get_settings_raw(uid)
                acct = store.ensure_account(uid)
                engine = service.active_engine(uid)
                if acct.get("halted"):
                    wants = False
                elif engine == "builder":
                    wants = bool(raw.get("strategy_autorun") and store.enabled_strategies(uid))
                else:
                    wants = acct.get("status") == "running"
                active = bool(wants) and _in_session()
                _set_awake(active)  # 활성+장중이면 PC sleep 차단, 아니면 절전 허용
                if active and not _running:
                    _running = True
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, _tick, uid)
                    finally:
                        _running = False
                delay = _interval(uid)
            else:
                _set_awake(False)
        except Exception:
            delay = _DEFAULT_INTERVAL
        await asyncio.sleep(delay)


def start() -> None:
    global _task
    if _task is None or _task.done():
        with contextlib.suppress(RuntimeError):
            _task = asyncio.create_task(_loop())


def stop() -> None:
    global _task
    _set_awake(False)
    if _task is not None:
        _task.cancel()
        _task = None
