"""SQLite persistence for paper-trading sessions, orders, and event logs."""

from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.core.config import settings
from backend.app.paper.session import PaperTradingSession, SessionStatus
from backend.app.paper.orders import PaperOrderRecord


class SQLitePaperStorage:
    """Manages persistent SQLite storage for paper trading sessions, orders, and event streams."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_dir = settings.data_dir / "paper"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = db_dir / "paper_sessions.db"
        else:
            self.db_path = db_path

        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    stopped_at TEXT,
                    dataset_id TEXT NOT NULL,
                    symbols TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    initial_capital REAL NOT NULL,
                    current_equity REAL NOT NULL,
                    cash REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    speed TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_bar_index INTEGER NOT NULL,
                    total_bars INTEGER NOT NULL,
                    simulation_timestamp TEXT,
                    config_json TEXT NOT NULL
                )
            """)

            # Orders table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_orders (
                    order_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    requested_price REAL,
                    fill_price REAL,
                    status TEXT NOT NULL,
                    commission REAL NOT NULL,
                    slippage REAL NOT NULL,
                    rejection_reason TEXT,
                    FOREIGN KEY (session_id) REFERENCES paper_sessions (session_id)
                )
            """)

            # Events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES paper_sessions (session_id)
                )
            """)
            conn.commit()

    def save_session(self, session: PaperTradingSession) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO paper_sessions (
                    session_id, created_at, started_at, stopped_at,
                    dataset_id, symbols, strategy, provider,
                    initial_capital, current_equity, cash,
                    realized_pnl, unrealized_pnl, speed, status,
                    current_bar_index, total_bars, simulation_timestamp,
                    config_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    started_at=excluded.started_at,
                    stopped_at=excluded.stopped_at,
                    current_equity=excluded.current_equity,
                    cash=excluded.cash,
                    realized_pnl=excluded.realized_pnl,
                    unrealized_pnl=excluded.unrealized_pnl,
                    speed=excluded.speed,
                    status=excluded.status,
                    current_bar_index=excluded.current_bar_index,
                    total_bars=excluded.total_bars,
                    simulation_timestamp=excluded.simulation_timestamp,
                    config_json=excluded.config_json
            """, (
                session.session_id,
                session.created_at,
                session.started_at,
                session.stopped_at,
                session.dataset_id,
                json.dumps(session.symbols),
                session.strategy,
                session.provider,
                session.initial_capital,
                session.current_equity,
                session.cash,
                session.realized_pnl,
                session.unrealized_pnl,
                session.speed,
                session.status.value,
                session.current_bar_index,
                session.total_bars,
                session.simulation_timestamp,
                json.dumps(session.to_dict()),
            ))
            conn.commit()

    def load_session(self, session_id: str) -> Optional[PaperTradingSession]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT config_json FROM paper_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            data = json.loads(row["config_json"])
            return PaperTradingSession.from_dict(data)

    def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def save_order(self, order: PaperOrderRecord) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO paper_orders (
                    order_id, session_id, timestamp, symbol, side,
                    order_type, quantity, requested_price, fill_price,
                    status, commission, slippage, rejection_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO UPDATE SET
                    status=excluded.status,
                    fill_price=excluded.fill_price,
                    commission=excluded.commission,
                    slippage=excluded.slippage,
                    rejection_reason=excluded.rejection_reason
            """, (
                order.order_id,
                order.session_id,
                order.timestamp,
                order.symbol,
                order.side,
                order.order_type,
                order.quantity,
                order.requested_price,
                order.fill_price,
                order.status,
                order.commission,
                order.slippage,
                order.rejection_reason,
            ))
            conn.commit()

    def load_orders(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_orders WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def save_event(self, session_id: str, timestamp: str, event_type: str, payload: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO paper_events (session_id, timestamp, event_type, payload_json)
                VALUES (?, ?, ?, ?)
            """, (
                session_id,
                timestamp,
                event_type,
                json.dumps(payload),
            ))
            conn.commit()

    def load_events(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT timestamp, event_type, payload_json FROM paper_events
                WHERE session_id = ? ORDER BY event_id ASC LIMIT ?
            """, (session_id, limit)).fetchall()
            events = []
            for r in rows:
                item = json.loads(r["payload_json"])
                item["event_type"] = r["event_type"]
                item["timestamp"] = r["timestamp"]
                events.append(item)
            return events

    def close(self) -> None:
        """Closes any persistent connections (no-op as connections are context-managed per operation)."""
        pass

