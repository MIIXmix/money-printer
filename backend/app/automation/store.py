"""automation DB 접근 계층. 모든 SQL은 파라미터 바인딩."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import get_db, json_dumps, json_loads, row_to_dict
from . import config
from .config import StrategyParams

_KST = timezone(timedelta(hours=9))


def kst_now() -> datetime:
    return datetime.now(_KST)


def kst_date() -> str:
    return kst_now().strftime("%Y-%m-%d")


# ── 계좌 ────────────────────────────────────────────────────────────────────

def ensure_account(user_id: int) -> dict[str, Any]:
    with get_db() as con:
        row = con.execute("SELECT * FROM automation_account WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            con.execute(
                "INSERT INTO automation_account(user_id, seed_krw, cash_krw, peak_value_krw) VALUES(?, ?, ?, ?)",
                (user_id, config.SEED_KRW, config.SEED_KRW, config.SEED_KRW),
            )
            row = con.execute("SELECT * FROM automation_account WHERE user_id = ?", (user_id,)).fetchone()
    return row_to_dict(row)


def get_account(user_id: int) -> dict[str, Any]:
    return ensure_account(user_id)


def update_account(user_id: int, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with get_db() as con:
        con.execute(
            f"UPDATE automation_account SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (*fields.values(), user_id),
        )


def get_params(user_id: int) -> StrategyParams:
    with get_db() as con:
        row = con.execute("SELECT settings_json FROM automation_settings WHERE user_id = ?", (user_id,)).fetchone()
    raw = json_loads(row["settings_json"], {}) if row else {}
    return StrategyParams.from_settings(raw)


def save_settings(user_id: int, raw: dict[str, Any]) -> None:
    with get_db() as con:
        con.execute(
            """
            INSERT INTO automation_settings(user_id, settings_json, updated_at)
            VALUES(?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET settings_json = excluded.settings_json, updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, json_dumps(raw)),
        )


# ── 포지션 ──────────────────────────────────────────────────────────────────

def list_positions(user_id: int) -> list[dict[str, Any]]:
    with get_db() as con:
        rows = con.execute("SELECT * FROM automation_positions WHERE user_id = ? ORDER BY symbol", (user_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


def upsert_position(user_id: int, *, symbol: str, market: str, currency: str,
                    quantity: float, avg_cost_native: float, cost_krw: float) -> None:
    with get_db() as con:
        con.execute(
            """
            INSERT INTO automation_positions(user_id, symbol, market, currency, quantity, avg_cost_native, cost_krw)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, symbol) DO UPDATE SET
              quantity = excluded.quantity, avg_cost_native = excluded.avg_cost_native,
              cost_krw = excluded.cost_krw, market = excluded.market, currency = excluded.currency,
              updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, symbol, market, currency, quantity, avg_cost_native, cost_krw),
        )


def delete_position(user_id: int, symbol: str) -> None:
    with get_db() as con:
        con.execute("DELETE FROM automation_positions WHERE user_id = ? AND symbol = ?", (user_id, symbol))


# ── 로그/기록 ───────────────────────────────────────────────────────────────

def insert_run(user_id: int, *, trigger: str, regime: str | None, data_status: str | None) -> int:
    with get_db() as con:
        cur = con.execute(
            "INSERT INTO strategy_runs(user_id, trigger, regime, data_status) VALUES(?, ?, ?, ?)",
            (user_id, trigger, regime, data_status),
        )
        return int(cur.lastrowid)


def finalize_run(run_id: int, *, signals: int, orders: int, blocked: int, note: str = "") -> None:
    with get_db() as con:
        con.execute(
            "UPDATE strategy_runs SET signals_count = ?, orders_count = ?, blocked_count = ?, note = ? WHERE id = ?",
            (signals, orders, blocked, note, run_id),
        )


def insert_signal(user_id: int, run_id: int, *, symbol: str, action: str, reason: str,
                  data_status: str, risk_checks: dict, est_amount_krw: float | None) -> None:
    with get_db() as con:
        con.execute(
            """
            INSERT INTO strategy_signals(user_id, run_id, symbol, action, reason, data_status, risk_checks_json, est_amount_krw)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, run_id, symbol, action, reason, data_status, json_dumps(risk_checks), est_amount_krw),
        )


def insert_order(user_id: int, run_id: int | None, *, symbol: str, side: str, quantity: float,
                 price_native: float | None, gross_krw: float | None, fee_krw: float,
                 slippage_krw: float, realized_pnl_krw: float | None, status: str,
                 block_reason: str, data_status: str) -> None:
    with get_db() as con:
        con.execute(
            """
            INSERT INTO auto_orders(user_id, run_id, symbol, side, quantity, price_native, gross_krw,
              fee_krw, slippage_krw, realized_pnl_krw, status, block_reason, data_status)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, run_id, symbol, side, quantity, price_native, gross_krw, fee_krw,
             slippage_krw, realized_pnl_krw, status, block_reason, data_status),
        )


def insert_risk_event(user_id: int, *, event: str, detail: str, symbol: str | None = None) -> None:
    with get_db() as con:
        con.execute(
            "INSERT INTO risk_events(user_id, event, detail, symbol) VALUES(?, ?, ?, ?)",
            (user_id, event, detail, symbol),
        )


def insert_audit(user_id: int, *, kind: str, message: str, data: dict | None = None) -> None:
    with get_db() as con:
        con.execute(
            "INSERT INTO automation_audit(user_id, kind, message, data_json) VALUES(?, ?, ?, ?)",
            (user_id, kind, message, json_dumps(data or {})),
        )


def upsert_snapshot(user_id: int, *, snap_date: str, total_value_krw: float, cash_krw: float,
                    positions_value_krw: float, cum_return: float | None, daily_return: float | None,
                    drawdown: float | None, positions: list, data_status: str) -> None:
    with get_db() as con:
        con.execute(
            """
            INSERT INTO portfolio_snapshots(user_id, snap_date, total_value_krw, cash_krw, positions_value_krw,
              cum_return, daily_return, drawdown, positions_json, data_status)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, snap_date) DO UPDATE SET
              total_value_krw = excluded.total_value_krw, cash_krw = excluded.cash_krw,
              positions_value_krw = excluded.positions_value_krw, cum_return = excluded.cum_return,
              daily_return = excluded.daily_return, drawdown = excluded.drawdown,
              positions_json = excluded.positions_json, data_status = excluded.data_status
            """,
            (user_id, snap_date, total_value_krw, cash_krw, positions_value_krw, cum_return,
             daily_return, drawdown, json_dumps(positions), data_status),
        )


def insert_promotion(user_id: int, *, passed: bool, checks: dict) -> None:
    with get_db() as con:
        con.execute(
            "INSERT INTO promotion_snapshots(user_id, passed, checks_json) VALUES(?, ?, ?)",
            (user_id, 1 if passed else 0, json_dumps(checks)),
        )


# ── 조회 ────────────────────────────────────────────────────────────────────

def recent_signals(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    with get_db() as con:
        rows = con.execute(
            "SELECT * FROM strategy_signals WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def recent_orders(user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with get_db() as con:
        rows = con.execute(
            "SELECT * FROM auto_orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def all_filled_orders(user_id: int) -> list[dict[str, Any]]:
    with get_db() as con:
        rows = con.execute(
            "SELECT * FROM auto_orders WHERE user_id = ? AND status = 'filled' ORDER BY id ASC", (user_id,)
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def all_snapshots(user_id: int) -> list[dict[str, Any]]:
    with get_db() as con:
        rows = con.execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id = ? ORDER BY snap_date ASC", (user_id,)
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def recent_audit(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    with get_db() as con:
        rows = con.execute(
            "SELECT * FROM automation_audit WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def recent_risk_events(user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with get_db() as con:
        rows = con.execute(
            "SELECT * FROM risk_events WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()
    return [row_to_dict(r) for r in rows]
