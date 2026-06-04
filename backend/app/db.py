from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import settings


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    _ensure_parent(settings.database_path)
    # timeout: 동시 writer(스케줄러 스레드 + 요청 스레드) 락 대기. WAL: 읽기-쓰기 동시성.
    con = sqlite3.connect(settings.database_path, timeout=10.0)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA busy_timeout = 10000")
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA synchronous = NORMAL")
        yield con
        con.commit()
    finally:
        con.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: str | bytes | None, fallback: Any = None) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def init_db() -> None:
    with get_db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              token_version INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_settings (
              user_id INTEGER NOT NULL,
              key TEXT NOT NULL,
              value_json TEXT NOT NULL,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (user_id, key),
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS api_keys (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              provider TEXT NOT NULL,
              label TEXT NOT NULL,
              encrypted_value TEXT NOT NULL,
              masked_value TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS holdings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              name TEXT NOT NULL DEFAULT '',
              quantity REAL NOT NULL,
              average_cost REAL NOT NULL,
              currency TEXT NOT NULL DEFAULT 'USD',
              market TEXT NOT NULL DEFAULT 'US',
              sector TEXT NOT NULL DEFAULT '',
              country TEXT NOT NULL DEFAULT '',
              target_weight REAL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS paper_orders (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              side TEXT NOT NULL,
              quantity REAL NOT NULL,
              order_type TEXT NOT NULL,
              limit_price REAL,
              mode TEXT NOT NULL DEFAULT 'paper',
              status TEXT NOT NULL DEFAULT 'accepted_paper',
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS watchlist (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              label TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(user_id, symbol),
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- ── 자동전략(Paper) ──────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS automation_account (
              user_id INTEGER PRIMARY KEY,
              status TEXT NOT NULL DEFAULT 'stopped',     -- stopped|running|blocked
              seed_krw REAL NOT NULL DEFAULT 500000,
              cash_krw REAL NOT NULL DEFAULT 500000,
              peak_value_krw REAL NOT NULL DEFAULT 500000,
              halted INTEGER NOT NULL DEFAULT 0,          -- 전체 낙폭 한도 도달 → 1
              halt_reason TEXT NOT NULL DEFAULT '',
              started_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS automation_settings (
              user_id INTEGER PRIMARY KEY,
              settings_json TEXT NOT NULL DEFAULT '{}',
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_strategies (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              name TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 0,         -- on/off
              definition_json TEXT NOT NULL DEFAULT '{}', -- 진입/청산/손절익절/유니버스/사이징/타임프레임
              last_backtest_json TEXT,                    -- 최근 백테스트 결과
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS automation_positions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              market TEXT NOT NULL DEFAULT 'US',
              currency TEXT NOT NULL DEFAULT 'USD',
              quantity REAL NOT NULL,
              avg_cost_native REAL NOT NULL,             -- 평단 (종목 통화)
              cost_krw REAL NOT NULL,                    -- 매입금액 (KRW 환산)
              opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(user_id, symbol),
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS strategy_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              trigger TEXT NOT NULL DEFAULT 'manual',     -- manual|scheduled
              regime TEXT,
              data_status TEXT,
              signals_count INTEGER NOT NULL DEFAULT 0,
              orders_count INTEGER NOT NULL DEFAULT 0,
              blocked_count INTEGER NOT NULL DEFAULT 0,
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS strategy_signals (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              run_id INTEGER,
              symbol TEXT NOT NULL,
              action TEXT NOT NULL,                       -- BUY|SELL|HOLD|REBALANCE|BLOCKED
              reason TEXT NOT NULL DEFAULT '',
              data_status TEXT NOT NULL DEFAULT '',
              risk_checks_json TEXT NOT NULL DEFAULT '{}',
              est_amount_krw REAL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS auto_orders (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              run_id INTEGER,
              symbol TEXT NOT NULL,
              side TEXT NOT NULL,                         -- buy|sell
              quantity REAL NOT NULL DEFAULT 0,
              price_native REAL,                          -- 체결가(슬리피지 반영, 종목 통화)
              gross_krw REAL,                             -- 체결금액 KRW
              fee_krw REAL NOT NULL DEFAULT 0,
              slippage_krw REAL NOT NULL DEFAULT 0,
              realized_pnl_krw REAL,
              status TEXT NOT NULL,                       -- filled|blocked|skipped
              block_reason TEXT NOT NULL DEFAULT '',
              data_status TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              snap_date TEXT NOT NULL,                    -- YYYY-MM-DD (KST)
              total_value_krw REAL NOT NULL,
              cash_krw REAL NOT NULL,
              positions_value_krw REAL NOT NULL DEFAULT 0,
              cum_return REAL,                            -- vs seed
              daily_return REAL,
              drawdown REAL,                              -- vs peak
              positions_json TEXT NOT NULL DEFAULT '[]',
              data_status TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(user_id, snap_date),
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS risk_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              event TEXT NOT NULL,                        -- daily_loss_block|drawdown_halt|instrument_block|data_block|...
              detail TEXT NOT NULL DEFAULT '',
              symbol TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS promotion_snapshots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              passed INTEGER NOT NULL DEFAULT 0,
              checks_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS automation_audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              kind TEXT NOT NULL,                         -- decision|order|block|risk|settings|lifecycle
              message TEXT NOT NULL DEFAULT '',
              data_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        # Lightweight migration for DBs created before token_version existed.
        cols = {row["name"] for row in con.execute("PRAGMA table_info(users)").fetchall()}
        if "token_version" not in cols:
            con.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")

        # Schema-drift migration: 일부 기존 DB는 user_strategies를 config_json으로 만들었다.
        # canonical 컬럼은 definition_json. 누락 시 추가하고 config_json 내용을 복사한다.
        scols = {row["name"] for row in con.execute("PRAGMA table_info(user_strategies)").fetchall()}
        if scols:  # 테이블 존재
            if "definition_json" not in scols:
                con.execute("ALTER TABLE user_strategies ADD COLUMN definition_json TEXT NOT NULL DEFAULT '{}'")
                if "config_json" in scols:
                    con.execute("UPDATE user_strategies SET definition_json = config_json "
                                "WHERE (definition_json IS NULL OR definition_json = '{}') AND config_json IS NOT NULL")
            if "last_backtest_json" not in scols:
                con.execute("ALTER TABLE user_strategies ADD COLUMN last_backtest_json TEXT")
