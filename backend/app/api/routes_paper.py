"""FastAPI endpoints and WebSocket stream for AlgoTrade Paper Trading System."""

from __future__ import annotations
import csv
import io
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Response
from pydantic import BaseModel, Field

from backend.app.paper.service import paper_service
from backend.app.paper.session import SessionStatus, ReplaySpeed

router = APIRouter(prefix="/paper", tags=["Paper Trading"])


class CreateSessionRequest(BaseModel):
    dataset_id: str = "AAPL"
    symbols: Optional[List[str]] = None
    timeframe: str = "1d"
    strategy: str = "TimeSeriesMomentum"
    strategy_params: Dict[str, Any] = Field(default_factory=dict)
    provider: str = "rule_based"
    mode: str = "HISTORICAL_REPLAY"
    data_provider: str = "HISTORICAL"
    data_provider_type: Optional[str] = None
    live_provider: Optional[str] = None
    bar_interval: str = "1m"
    max_data_age_seconds: float = 15.0
    max_desync_seconds: float = 5.0
    initial_capital: float = 100_000.0
    speed: str = "1x"
    allow_shorting: bool = False
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    seed: int = 42
    jev_config: Optional[Dict[str, Any]] = None
    ml_config: Optional[Dict[str, Any]] = None
    execution_config: Optional[Dict[str, Any]] = None
    risk_config: Optional[Dict[str, Any]] = None


class SpeedChangeRequest(BaseModel):
    speed: str


@router.get("/status")
def get_paper_trading_status() -> Dict[str, Any]:
    """Paper trading engine status endpoint."""
    active_sessions = [s for s in paper_service.sessions.values() if s.status == SessionStatus.RUNNING]
    return {
        "is_active": len(active_sessions) > 0,
        "active_sessions_count": len(active_sessions),
        "total_sessions": len(paper_service.sessions),
        "mode": "SIMULATION_ONLY",
        "message": f"AlgoTrade paper engine ready. {len(active_sessions)} running sessions.",
    }


@router.post("/sessions")
def create_paper_session(req: CreateSessionRequest) -> Dict[str, Any]:
    """Creates a new persistent paper trading session."""
    try:
        session = paper_service.create_session(req.model_dump())
        return session.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions")
def list_paper_sessions() -> List[Dict[str, Any]]:
    """Returns list of all active and historic paper trading sessions."""
    return paper_service.list_sessions()


@router.get("/sessions/{session_id}")
def get_paper_session(session_id: str) -> Dict[str, Any]:
    """Returns full state for a specific paper trading session."""
    sess = paper_service.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return sess.to_dict()


@router.post("/sessions/{session_id}/start")
def start_paper_session(session_id: str) -> Dict[str, Any]:
    """Starts execution of an idle or paused paper trading session."""
    try:
        session = paper_service.start_session(session_id)
        return session.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/pause")
def pause_paper_session(session_id: str) -> Dict[str, Any]:
    """Pauses a running paper trading session."""
    try:
        session = paper_service.pause_session(session_id)
        return session.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")


@router.post("/sessions/{session_id}/resume")
def resume_paper_session(session_id: str) -> Dict[str, Any]:
    """Resumes paused historical bar replay."""
    try:
        sess = paper_service.resume_session(session_id)
        return sess.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")


@router.post("/sessions/{session_id}/stop")
def stop_paper_session(session_id: str) -> Dict[str, Any]:
    """Stops and finalizes a paper trading session."""
    try:
        session = paper_service.stop_session(session_id)
        return session.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")


@router.post("/sessions/{session_id}/step")
def step_paper_session(session_id: str) -> Dict[str, Any]:
    """Advances one bar forward synchronously in a paused historical session."""
    try:
        session, events = paper_service.step_session(session_id)
        return {
            "session": session.to_dict(),
            "events_count": len(events),
            "events": events,
            "bar_index": session.current_bar_index,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/speed")
def change_replay_speed(session_id: str, req: SpeedChangeRequest) -> Dict[str, Any]:
    """Changes the replay speed multiplier on the fly."""
    try:
        speed = ReplaySpeed(req.speed)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid speed. Choose from: {[s.value for s in ReplaySpeed]}")
    try:
        session = paper_service.set_replay_speed(session_id, speed)
        return session.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")


@router.get("/sessions/{session_id}/orders")
def get_session_orders(session_id: str) -> List[Dict[str, Any]]:
    """Returns order history for the specified paper trading session."""
    return paper_service.get_orders(session_id)


@router.get("/sessions/{session_id}/positions")
def get_session_positions(session_id: str) -> List[Dict[str, Any]]:
    """Returns open positions with mark-to-market prices."""
    return paper_service.get_positions(session_id)


@router.get("/sessions/{session_id}/events")
def get_session_events(session_id: str) -> List[Dict[str, Any]]:
    """Returns recent runtime and market events for this session."""
    return paper_service.get_events(session_id, limit=100)


@router.get("/sessions/{session_id}/export")
def export_session_results(session_id: str) -> Dict[str, Any]:
    """Exports full session results, equity curve, orders, and trades as JSON."""
    try:
        return paper_service.export_results(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")


@router.get("/sessions/{session_id}/export/trades.csv")
def export_trades_csv(session_id: str) -> Response:
    """Exports trades log as CSV format with decision source metadata."""
    try:
        data = paper_service.export_results(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "trade_id", "symbol", "entry_time", "exit_time", "direction",
        "quantity", "entry_price", "exit_price", "realized_pnl", "return_pct", "exit_reason",
        "decision_source", "model_version", "jev_mode",
    ])
    for t in data.get("trades", []):
        writer.writerow([
            t.get("trade_id", ""),
            t.get("symbol", ""),
            t.get("entry_time", ""),
            t.get("exit_time", ""),
            t.get("direction", ""),
            t.get("quantity", 0),
            t.get("entry_price", 0.0),
            t.get("exit_price", 0.0),
            t.get("realized_pnl", 0.0),
            t.get("return_pct", 0.0),
            t.get("exit_reason", ""),
            t.get("decision_source", "RULE_BASED"),
            t.get("model_version", ""),
            t.get("jev_mode", "NONE"),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="paper_trades_{session_id}.csv"'}
    )


@router.get("/sessions/{session_id}/export/equity.csv")
def export_equity_csv(session_id: str) -> Response:
    """Exports session equity curve as CSV format."""
    try:
        data = paper_service.export_results(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "equity", "cash", "realized_pnl", "unrealized_pnl"])
    for eq in data.get("equity_curve", []):
        writer.writerow([
            eq.get("timestamp", ""),
            eq.get("equity", 0.0),
            eq.get("cash", 0.0),
            eq.get("realized_pnl", 0.0),
            eq.get("unrealized_pnl", 0.0),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="paper_equity_{session_id}.csv"'}
    )


# Legacy compatibility endpoints
@router.post("/start")
def legacy_start_paper_trading() -> Dict[str, str]:
    return {"status": "SUCCESS", "message": "Create or select a session to run paper trading."}


@router.post("/stop")
def legacy_stop_paper_trading() -> Dict[str, str]:
    return {"status": "STOPPED", "message": "Paper trading stopped."}


async def paper_ws_handler(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    paper_service.register_websocket(session_id, websocket)

    # Send initial state snapshot
    sess = paper_service.get_session(session_id)
    if sess:
        await websocket.send_json({
            "event_type": "CONNECTED",
            "session": sess.to_dict(),
            "positions": paper_service.get_positions(session_id),
            "orders": paper_service.get_orders(session_id),
            "recent_events": paper_service.get_events(session_id, limit=30),
        })

    try:
        while True:
            # Client can ping or send step commands
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        paper_service.unregister_websocket(session_id, websocket)
    except Exception:
        paper_service.unregister_websocket(session_id, websocket)


@router.websocket("/ws/{session_id}")
async def websocket_route(websocket: WebSocket, session_id: str) -> None:
    await paper_ws_handler(websocket, session_id)
