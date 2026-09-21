"""Experiment storage abstraction and SQLite implementation."""

from __future__ import annotations
from abc import ABC, abstractmethod
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.core.config import settings
from backend.app.research.result import ExperimentResult


class BaseExperimentStorage(ABC):
    """Abstract interface for persisting and querying experiment results."""

    @abstractmethod
    def save_experiment(self, result: ExperimentResult) -> str:
        """Persists an experiment result and returns its experiment_id."""
        pass

    @abstractmethod
    def load_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Retrieves an experiment result by its unique experiment_id."""
        pass

    @abstractmethod
    def list_experiments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns summarized metadata for stored experiments."""
        pass

    @abstractmethod
    def delete_experiment(self, experiment_id: str) -> bool:
        """Deletes an experiment by ID. Returns True if deleted, False otherwise."""
        pass


class SQLiteExperimentStorage(BaseExperimentStorage):
    """SQLite-backed experiment store. Lightweight, embedded, and zero-configuration."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = settings.data_dir
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "experiments.db")
        else:
            self.db_path = str(db_path)
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    configuration_hash TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    sharpe_ratio REAL,
                    total_return REAL,
                    max_drawdown REAL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_config_hash ON experiments(configuration_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_name ON experiments(strategy_name)")
            conn.commit()

    def save_experiment(self, result: ExperimentResult) -> str:
        metrics = result.metrics or {}
        strat_name = result.strategy_info.get("name", result.config.get("strategy", {}).get("name", "Unknown"))
        dataset_id = result.dataset_metadata.get("dataset_id", result.config.get("dataset", {}).get("dataset_id", "Unknown"))

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO experiments (
                    experiment_id,
                    configuration_hash,
                    strategy_name,
                    dataset_id,
                    sharpe_ratio,
                    total_return,
                    max_drawdown,
                    created_at,
                    completed_at,
                    result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.experiment_id,
                    result.configuration_hash,
                    strat_name,
                    dataset_id,
                    metrics.get("sharpe_ratio"),
                    metrics.get("total_return"),
                    metrics.get("maximum_drawdown"),
                    result.created_at,
                    result.completed_at,
                    result.to_json(),
                ),
            )
            conn.commit()
        return result.experiment_id

    def load_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT result_json FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            )
            row = cursor.fetchone()
            if row:
                return ExperimentResult.from_json(row["result_json"])
        return None

    def list_experiments(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    experiment_id,
                    configuration_hash,
                    strategy_name,
                    dataset_id,
                    sharpe_ratio,
                    total_return,
                    max_drawdown,
                    created_at,
                    completed_at
                FROM experiments
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def delete_experiment(self, experiment_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
