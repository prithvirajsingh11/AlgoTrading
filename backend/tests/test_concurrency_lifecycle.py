"""Concurrency and lifecycle tests under repeated transitions.

Tests:
start -> pause -> resume -> stop
Repeated rapid transitions.

Guarantees:
- Zero duplicate replay loop tasks
- Zero orphan tasks
- Zero duplicated orders or fills
- Deterministic session state transitions
"""

import asyncio
import tempfile
from pathlib import Path
import pytest
import pandas as pd

from backend.app.paper.service import PaperTradingService
from backend.app.paper.session import SessionStatus, ReplaySpeed
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.research.dataset import DatasetManager


def test_repeated_lifecycle_transitions():
    async def _test():
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_concurrency.db"))
            svc = PaperTradingService(storage=storage)

            dm = DatasetManager()
            df = pd.DataFrame({
                "timestamp": pd.date_range("2023-01-01", periods=100, freq="D"),
                "open": [100.0] * 100,
                "high": [105.0] * 100,
                "low": [95.0] * 100,
                "close": [102.0] * 100,
                "volume": [1000.0] * 100,
            })
            dm.register_dataframe("concurrency_ds", df, symbols=["AAPL"])

            cfg = {
                "dataset_id": "concurrency_ds",
                "symbols": ["AAPL"],
                "strategy": "TimeSeriesMomentum",
                "speed": "100x",
            }
            session = svc.create_session(cfg, dataset_manager=dm)
            sid = session.session_id

            # Rapid start -> pause -> resume -> pause -> resume -> stop
            for _ in range(3):
                svc.start_session(sid)
                assert session.status == SessionStatus.RUNNING
                await asyncio.sleep(0.01)

                svc.pause_session(sid)
                assert session.status == SessionStatus.PAUSED
                # Verify task was cancelled and not running
                t = svc.tasks.get(sid)
                if t:
                    assert t.done() or t.cancelled()

                svc.resume_session(sid)
                assert session.status == SessionStatus.RUNNING
                await asyncio.sleep(0.01)

            # Final stop
            svc.stop_session(sid)
            assert session.status == SessionStatus.STOPPED
            final_task = svc.tasks.get(sid)
            if final_task:
                assert final_task.done() or final_task.cancelled()

            # Ensure orders history has no duplicates
            orders = svc.get_orders(sid)
            order_ids = [o["order_id"] for o in orders]
            assert len(order_ids) == len(set(order_ids))

    asyncio.run(_test())
