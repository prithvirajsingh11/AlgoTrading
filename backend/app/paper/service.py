"""Paper Trading execution service coordinating real-time sessions, orders, risk, and WebSocket events."""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple
import logging
from starlette.websockets import WebSocket, WebSocketState

from backend.app.paper.session import (
    PaperTradingSession,
    SessionStatus,
    ReplaySpeed,
    SessionMode,
    SignalSafetyState,
)
from backend.app.paper.events import (
    PaperEvent,
    MarketEvent,
    StrategySignalEvent,
    RiskValidationEvent,
    OrderLifecycleEvent,
    FillExecutionEvent,
    PortfolioUpdateEvent,
    SessionLifecycleEvent,
    ProviderStatusEvent,
    MarketUpdateEvent,
    BarClosedEvent,
    ReconnectEvent,
    PaperErrorEvent,
    JevDecisionEvent,
    MLPredictionEvent,
)
from backend.app.paper.market_data import (
    HistoricalReplayProvider,
    MarketDataProvider,
    RealTimeMarketDataProvider,
    ConnectionState,
    InMemoryStreamingAdapter,
    GenericWebSocketAdapter,
    AlpacaMarketDataAdapter,
    BaseProviderAdapter,
    MarketTick,
)
from backend.app.paper.bar_builder import BarBuilder
from backend.app.paper.sync import SnapshotSynchronizer
from backend.app.paper.streaming_features import StreamingFeatureEngine
from backend.app.paper.account import PaperAccount
from backend.app.paper.orders import PaperOrderRecord, PaperOrderManager
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.core.config import settings

from backend.app.research.runner import STRATEGY_REGISTRY
from backend.app.strategies.base import BaseStrategy
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    SignalEvent,
    SignalType,
)
from backend.app.risk.risk_manager import RiskManager
from backend.app.risk.position_sizing import PercentEquitySizer, BasePositionSizer

logger = logging.getLogger("paper_trading")


class PaperTradingService:
    """Singleton/central service orchestrating deterministic paper trading sessions."""

    def __init__(self, storage: Optional[SQLitePaperStorage] = None):
        self.storage = storage or SQLitePaperStorage()

        self.sessions: Dict[str, PaperTradingSession] = {}
        self.accounts: Dict[str, PaperAccount] = {}
        self.providers: Dict[str, MarketDataProvider] = {}
        self.strategies: Dict[str, BaseStrategy] = {}
        self.brokers: Dict[str, SimulatedBroker] = {}
        self.risk_managers: Dict[str, RiskManager] = {}
        self.position_sizers: Dict[str, BasePositionSizer] = {}
        self.order_managers: Dict[str, PaperOrderManager] = {}
        self.decision_providers: Dict[str, Any] = {}
        self.synchronizers: Dict[str, SnapshotSynchronizer] = {}
        self.feature_engines: Dict[str, StreamingFeatureEngine] = {}
        self.bar_builders: Dict[str, BarBuilder] = {}

        self.tasks: Dict[str, asyncio.Task] = {}
        self.subscribers: Dict[str, Set[WebSocket]] = {}
        self.recent_events: Dict[str, List[Dict[str, Any]]] = {}

        # Load existing sessions from storage metadata
        self._hydrate_from_storage()


    def _hydrate_from_storage(self) -> None:
        try:
            persisted = self.storage.list_sessions(limit=50)
            for row in persisted:
                sid = row["session_id"]
                sess = self.storage.load_session(sid)
                if sess:
                    if sess.status == SessionStatus.RUNNING:
                        sess.status = SessionStatus.PAUSED
                        sess.error_message = "Session interrupted by server restart. Requires explicit resume."
                        sess.updated_at = datetime.now(timezone.utc).isoformat()
                        self.storage.save_session(sess)
                        logger.warning(f"Recovered RUNNING session {sid} as PAUSED after server restart.")
                    self.sessions[sid] = sess
                    self.recent_events[sid] = self.storage.load_events(sid, limit=50)
        except Exception as e:
            logger.warning(f"Error hydrating sessions from storage: {e}")

    def create_session(
        self,
        config: Dict[str, Any],
        dataset_manager: Optional[Any] = None,
    ) -> PaperTradingSession:
        active_sessions = [
            s for s in self.sessions.values()
            if s.status not in (SessionStatus.STOPPED, SessionStatus.ERROR)
        ]
        if len(active_sessions) >= settings.max_paper_sessions:
            raise ValueError(
                f"Maximum active paper sessions limit reached ({settings.max_paper_sessions}). "
                "Complete or remove existing sessions."
            )
        dataset_id = config.get("dataset_id", "AAPL")
        symbols = config.get("symbols") or [dataset_id]
        strategy_name = config.get("strategy", "TimeSeriesMomentum")
        strategy_params = config.get("strategy_params", {})
        provider_name = config.get("provider", "rule_based")
        initial_capital = float(config.get("initial_capital", 100_000.0))
        speed_val = config.get("speed", ReplaySpeed.ONE.value)
        allow_shorting = bool(config.get("allow_shorting", False))
        seed = int(config.get("seed", 42))

        exec_cfg = dict(config.get("execution_config") or {
            "commission_fixed": 1.0,
            "commission_percent": 0.0005,
            "slippage_bps": 5.0,
        })
        risk_cfg = dict(config.get("risk_config") or {
            "max_position_pct": 0.50,
            "max_drawdown_limit": 0.30,
            "allow_shorting": allow_shorting,
            "position_size_pct": 0.20,
        })
        risk_cfg["allow_shorting"] = allow_shorting

        # 1. Initialize market data provider (Historical, Synthetic, or Real-Time Provider)
        session_mode = config.get("mode", SessionMode.HISTORICAL_REPLAY.value)
        data_provider_type = config.get("data_provider_type", config.get("data_provider", "HISTORICAL"))
        bar_interval = config.get("bar_interval", "1m")
        synchronizer = None
        feat_engine = None
        bar_builder = None
        initial_conn_state = "DISCONNECTED"

        if session_mode == SessionMode.REAL_TIME.value or data_provider_type == "LIVE_PROVIDER":
            session_mode = SessionMode.REAL_TIME.value
            data_provider_type = "LIVE_PROVIDER"

            live_prov_name = config.get("live_provider") or config.get("provider") or settings.market_data_provider
            if live_prov_name in ("mock", "in_memory", "in_memory_mock"):
                adapter = InMemoryStreamingAdapter(
                    symbols=symbols,
                    quote_only=bool(config.get("quote_only", False)),
                )
                initial_conn_state = "CONNECTED"
            elif live_prov_name in ("alpaca", "alpaca_iex", "alpaca_sip"):
                feed_type = "sip" if "sip" in live_prov_name else settings.alpaca_data_feed
                api_key = config.get("api_key") or settings.alpaca_api_key or settings.market_data_api_key
                api_secret = config.get("api_secret") or config.get("secret_key") or settings.alpaca_secret_key or settings.market_data_api_secret
                adapter = AlpacaMarketDataAdapter(
                    api_key=api_key,
                    api_secret=api_secret,
                    symbols=symbols,
                    feed=feed_type,
                    api_url=config.get("live_api_url") or settings.market_data_api_url,
                    reconnect_attempts=settings.market_data_reconnect_attempts,
                    reconnect_backoff_factor=settings.market_data_reconnect_backoff_factor,
                )
                initial_conn_state = adapter.status.state.value
            elif live_prov_name in ("websocket", "generic_ws"):
                url = config.get("live_api_url") or settings.market_data_api_url
                if not url:
                    raise ValueError(f"Real-time market data provider '{live_prov_name}' requires API URL configuration. None supplied.")
                adapter = GenericWebSocketAdapter(
                    api_url=url,
                    api_key=settings.market_data_api_key,
                    api_secret=settings.market_data_api_secret,
                    symbols=symbols,
                )
                initial_conn_state = adapter.status.state.value
            elif "adapter" in config and isinstance(config["adapter"], BaseProviderAdapter):
                adapter = config["adapter"]
                initial_conn_state = adapter.status.state.value
            else:
                # Default to Alpaca adapter
                api_key = config.get("api_key") or settings.market_data_api_key
                api_secret = config.get("api_secret") or settings.market_data_api_secret
                adapter = AlpacaMarketDataAdapter(
                    api_key=api_key,
                    api_secret=api_secret,
                    symbols=symbols,
                    feed=settings.alpaca_data_feed,
                    api_url=config.get("live_api_url") or settings.market_data_api_url,
                    reconnect_attempts=settings.market_data_reconnect_attempts,
                    reconnect_backoff_factor=settings.market_data_reconnect_backoff_factor,
                )
                initial_conn_state = adapter.status.state.value

            data_provider = RealTimeMarketDataProvider(
                adapter=adapter,
                symbols=symbols,
                max_reconnect_attempts=settings.market_data_reconnect_attempts,
                reconnect_backoff_factor=settings.market_data_reconnect_backoff_factor,
                heartbeat_interval_seconds=settings.market_data_heartbeat_interval,
            )
            total_bars = 0
            synchronizer = SnapshotSynchronizer(
                symbols=symbols,
                max_desync_seconds=float(config.get("max_desync_seconds", settings.market_data_max_desync_seconds)),
            )
            feat_engine = StreamingFeatureEngine(symbols=symbols)
            bar_builder = BarBuilder(interval=bar_interval, symbols=symbols)

        elif (
            session_mode == SessionMode.SYNTHETIC_STREAM.value
            or data_provider_type == "SYNTHETIC"
            or config.get("live_provider") in ("mock", "in_memory", "in_memory_mock")
        ):
            session_mode = SessionMode.SYNTHETIC_STREAM.value
            data_provider_type = "SYNTHETIC"
            adapter = InMemoryStreamingAdapter(
                symbols=symbols,
                quote_only=bool(config.get("quote_only", False)),
            )
            data_provider = RealTimeMarketDataProvider(
                adapter=adapter,
                symbols=symbols,
                max_reconnect_attempts=settings.market_data_reconnect_attempts,
                reconnect_backoff_factor=settings.market_data_reconnect_backoff_factor,
                heartbeat_interval_seconds=settings.market_data_heartbeat_interval,
            )
            total_bars = 0
            synchronizer = SnapshotSynchronizer(
                symbols=symbols,
                max_desync_seconds=float(config.get("max_desync_seconds", settings.market_data_max_desync_seconds)),
            )
            feat_engine = StreamingFeatureEngine(symbols=symbols)
            bar_builder = BarBuilder(interval=bar_interval, symbols=symbols)
            initial_conn_state = "CONNECTED"

        else:
            # HISTORICAL_REPLAY
            session_mode = SessionMode.HISTORICAL_REPLAY.value
            data_provider_type = "HISTORICAL"
            data_provider = HistoricalReplayProvider(
                dataset_id=dataset_id,
                symbols=symbols,
                dataset_manager=dataset_manager or config.get("dataset_manager"),
                start_date=config.get("start_date"),
                end_date=config.get("end_date"),
            )
            total_bars = data_provider.get_total_bars()

        # 2. Build session record
        session = PaperTradingSession(
            dataset_id=dataset_id,
            symbols=symbols,
            timeframe=config.get("timeframe", "1d"),
            strategy=strategy_name,
            strategy_params=strategy_params,
            provider=provider_name,
            mode=session_mode,
            data_provider_type=data_provider_type,
            safety_state=SignalSafetyState.SIGNALS_ENABLED.value,
            max_data_age_seconds=float(config.get("max_data_age_seconds", settings.market_data_max_age_seconds)),
            connection_state=initial_conn_state,
            bar_interval=bar_interval,
            initial_capital=initial_capital,
            current_equity=initial_capital,
            cash=initial_capital,
            speed=speed_val,
            total_bars=total_bars,
            seed=seed,
            jev_config=config.get("jev_config"),
            ml_config=config.get("ml_config"),
            execution_config=exec_cfg,
            risk_config=risk_cfg,
        )
        sid = session.session_id

        # 3. Instantiate domain objects
        account = PaperAccount(initial_capital=initial_capital, allow_shorting=allow_shorting)
        broker = SimulatedBroker(
            commission_fixed=exec_cfg.get("commission_fixed", 1.0),
            commission_percent=exec_cfg.get("commission_percent", 0.0005),
            slippage_bps=exec_cfg.get("slippage_bps", 5.0),
        )
        risk_mgr = RiskManager(
            max_position_pct=risk_cfg.get("max_position_pct", 0.50),
            max_drawdown_limit=risk_cfg.get("max_drawdown_limit", 0.30),
            allow_shorting=allow_shorting,
        )
        pos_sizer = PercentEquitySizer(percent_equity=risk_cfg.get("position_size_pct", 0.20))
        order_mgr = PaperOrderManager(session_id=sid)

        # 4. Instantiate strategy
        if strategy_name not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy '{strategy_name}'. Available: {list(STRATEGY_REGISTRY.keys())}")
        strat_cls = STRATEGY_REGISTRY[strategy_name]
        strat_params_copy = dict(strategy_params)
        primary_sym = symbols[0]
        if strategy_name == "PairsTrading":
            hedge_sym = symbols[1] if len(symbols) >= 2 else "HEDGE"
            strategy = strat_cls(
                symbol=primary_sym,
                hedge_symbol=hedge_sym,
                parameters=strat_params_copy,
            )
        else:
            strategy = strat_cls(
                symbol=primary_sym,
                parameters=strat_params_copy,
            )
        strategy.reset()

        # 5. Attach Jev decision layer if requested
        if provider_name in ("typesafe_jev", "hybrid") or session.jev_config:
            from backend.app.ai.jev_decision import JevDecisionProvider
            jev_cfg = session.jev_config or {}
            self.decision_providers[sid] = JevDecisionProvider(
                cache_ttl_seconds=jev_cfg.get("cache_ttl_seconds", 3600),
                mock_mode=jev_cfg.get("mock_mode", False),
            )

        # Store in registries
        self.sessions[sid] = session
        self.accounts[sid] = account
        self.providers[sid] = data_provider
        self.strategies[sid] = strategy
        self.brokers[sid] = broker
        self.risk_managers[sid] = risk_mgr
        self.position_sizers[sid] = pos_sizer
        self.order_managers[sid] = order_mgr
        if synchronizer is not None:
            self.synchronizers[sid] = synchronizer
        if feat_engine is not None:
            self.feature_engines[sid] = feat_engine
        if bar_builder is not None:
            self.bar_builders[sid] = bar_builder
        self.recent_events[sid] = []
        self.subscribers[sid] = set()

        # Persist initial session state
        self.storage.save_session(session)


        # Emit initial lifecycle event
        init_evt = SessionLifecycleEvent(
            timestamp=session.created_at,
            event_type="SESSION_CREATED",
            session_id=sid,
            status=session.status.value,
            current_bar=0,
            total_bars=total_bars,
            message="Paper trading session created and initialized.",
        )
        self._record_event(sid, init_evt)

        return session

    def start_session(self, session_id: str) -> PaperTradingSession:
        session = self._get_required_session(session_id)
        if session.status == SessionStatus.RUNNING:
            return session

        session.status = SessionStatus.RUNNING
        if not session.started_at:
            session.started_at = datetime.now(timezone.utc).isoformat()
        self.storage.save_session(session)

        evt = SessionLifecycleEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="SESSION_STARTED",
            session_id=session_id,
            status=session.status.value,
            current_bar=session.current_bar_index,
            total_bars=session.total_bars,
            message="Paper trading session started.",
        )
        self._record_event(session_id, evt)
        self._schedule_broadcast(session_id, evt)

        # Launch async loop if not active
        existing_task = self.tasks.get(session_id)
        if existing_task is None or existing_task.done():
            if session.mode in (SessionMode.REAL_TIME.value, SessionMode.SYNTHETIC_STREAM.value):
                task = self._schedule_task(session_id, self._live_stream_loop(session_id))
            else:
                task = self._schedule_task(session_id, self._replay_loop(session_id))
            if task is not None:
                self.tasks[session_id] = task

        return session

    def pause_session(self, session_id: str) -> PaperTradingSession:
        session = self._get_required_session(session_id)
        session.status = SessionStatus.PAUSED
        self.storage.save_session(session)

        # Cancel active task
        task = self.tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        prov = self.providers.get(session_id)
        if prov and hasattr(prov, "stop"):
            prov.stop()

        evt = SessionLifecycleEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="SESSION_PAUSED",
            session_id=session_id,
            status=session.status.value,
            current_bar=session.current_bar_index,
            total_bars=session.total_bars,
            message="Paper trading session paused.",
        )
        self._record_event(session_id, evt)
        self._schedule_broadcast(session_id, evt)
        return session

    def resume_session(self, session_id: str) -> PaperTradingSession:
        return self.start_session(session_id)

    def stop_session(self, session_id: str) -> PaperTradingSession:
        session = self._get_required_session(session_id)
        session.status = SessionStatus.STOPPED
        session.stopped_at = datetime.now(timezone.utc).isoformat()
        self.storage.save_session(session)

        task = self.tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        prov = self.providers.get(session_id)
        if prov and hasattr(prov, "stop"):
            prov.stop()

        evt = SessionLifecycleEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="SESSION_STOPPED",
            session_id=session_id,
            status=session.status.value,
            current_bar=session.current_bar_index,
            total_bars=session.total_bars,
            message="Paper trading session stopped.",
        )
        self._record_event(session_id, evt)
        self._schedule_broadcast(session_id, evt)
        return session

    def set_speed(self, session_id: str, speed: Any) -> PaperTradingSession:
        session = self._get_required_session(session_id)
        speed_str = speed.value if hasattr(speed, "value") else str(speed)
        # Validate speed string
        valid_speeds = [s.value for s in ReplaySpeed]
        if speed_str not in valid_speeds:
            raise ValueError(f"Invalid speed '{speed_str}'. Must be one of {valid_speeds}")

        session.speed = speed_str
        self.storage.save_session(session)

        evt = SessionLifecycleEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="SPEED_CHANGED",
            session_id=session_id,
            status=session.status.value,
            current_bar=session.current_bar_index,
            total_bars=session.total_bars,
            message=f"Replay speed adjusted to {speed_str}.",
        )
        self._record_event(session_id, evt)
        self._schedule_broadcast(session_id, evt)
        return session

    def set_replay_speed(self, session_id: str, speed: Any) -> PaperTradingSession:
        return self.set_speed(session_id, speed)

    def _schedule_broadcast(self, session_id: str, event: PaperEvent) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast(session_id, event))
        except RuntimeError:
            pass

    def _schedule_task(self, session_id: str, coro) -> Optional[asyncio.Task]:
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(coro)
        except RuntimeError:
            coro.close()
            return None

    def step_session(self, session_id: str) -> Tuple[PaperTradingSession, List[Dict[str, Any]]]:
        """Manually steps the simulation forward by exactly one bar."""
        session = self._get_required_session(session_id)
        provider = self.providers.get(session_id)
        if not provider or not provider.has_next():
            session.status = SessionStatus.STOPPED
            session.stopped_at = datetime.now(timezone.utc).isoformat()
            self.storage.save_session(session)
            return session, []

        events = self._execute_step(session_id)
        for e in events:
            self._schedule_broadcast(session_id, e)

        return session, [e.to_dict() for e in events]

    async def _replay_loop(self, session_id: str) -> None:
        """Background coroutine advancing the historical replay according to configured speed."""
        try:
            session = self.sessions.get(session_id)
            provider = self.providers.get(session_id)
            if not session or not provider:
                return

            while session.status == SessionStatus.RUNNING and provider.has_next():
                step_events = self._execute_step(session_id)
                for evt in step_events:
                    await self._broadcast(session_id, evt)

                speed_enum = ReplaySpeed(session.speed)
                sleep_time = speed_enum.sleep_seconds
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0)  # Yield for MAX speed

            # If ended naturally by exhausting bars
            if session.status == SessionStatus.RUNNING and not provider.has_next():
                session.status = SessionStatus.STOPPED
                session.stopped_at = datetime.now(timezone.utc).isoformat()
                self.storage.save_session(session)
                comp_evt = SessionLifecycleEvent(
                    timestamp=session.simulation_timestamp or datetime.now(timezone.utc).isoformat(),
                    event_type="SESSION_COMPLETED",
                    session_id=session_id,
                    status=session.status.value,
                    current_bar=session.current_bar_index,
                    total_bars=session.total_bars,
                    message="Paper trading historical replay completed.",
                )
                self._record_event(session_id, comp_evt)
                await self._broadcast(session_id, comp_evt)

        except asyncio.CancelledError:
            logger.info(f"Replay loop task cancelled for session {session_id}")
        except Exception as e:
            logger.exception(f"Error in replay loop for session {session_id}: {e}")
            if session_id in self.sessions:
                s = self.sessions[session_id]
                s.status = SessionStatus.ERROR
                s.error_message = str(e)
                self.storage.save_session(s)

    async def _live_stream_loop(self, session_id: str) -> None:
        """Background coroutine reading live market stream and updating paper session in real time."""
        provider = None
        try:
            session = self.sessions.get(session_id)
            provider = self.providers.get(session_id)
            if not session or not provider:
                return

            if hasattr(provider, "connect"):
                try:
                    await provider.connect()
                except ValueError as ve:
                    # Unconfigured provider credentials
                    session.status = SessionStatus.ERROR
                    session.connection_state = ConnectionState.NOT_CONFIGURED.value
                    session.safety_state = SignalSafetyState.SIGNALS_PAUSED.value
                    session.error_message = str(ve)
                    self.storage.save_session(session)
                    err_evt = PaperErrorEvent(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        event_type="ERROR",
                        session_id=session_id,
                        error_type="NOT_CONFIGURED",
                        message=str(ve),
                    )
                    self._record_event(session_id, err_evt)
                    await self._broadcast(session_id, err_evt)
                    return

            if not hasattr(provider, "stream"):
                logger.error(f"Provider does not support streaming in session {session_id}")
                return

            bar_builder = self.bar_builders.get(session_id)
            feat_engine = self.feature_engines.get(session_id)
            synchronizer = self.synchronizers.get(session_id)

            async for snapshot in provider.stream():
                if session.status != SessionStatus.RUNNING:
                    break

                now = datetime.now(timezone.utc)
                now_ts = now.timestamp()
                snap_ts = snapshot.timestamp.timestamp() if hasattr(snapshot.timestamp, "timestamp") else now_ts
                data_age = max(0.0, now_ts - snap_ts)
                is_stale = data_age > session.max_data_age_seconds

                prov_status = provider.status if hasattr(provider, "status") else None
                is_connected = prov_status.connected if prov_status else True
                reconnect_cnt = prov_status.reconnect_count if prov_status else 0

                # Update session tracking fields
                session.connection_state = prov_status.state.value if prov_status else "CONNECTED"
                session.reconnect_count = reconnect_cnt
                session.last_data_timestamp = snapshot.timestamp.isoformat() if hasattr(snapshot.timestamp, "isoformat") else str(snapshot.timestamp)
                session.last_receive_timestamp = now.isoformat()
                session.latency_ms = snapshot.latency_ms or (prov_status.latency_ms if prov_status else None)

                # Broadcast ReconnectEvent if reconnect occurred
                if prov_status and prov_status.state == ConnectionState.RECONNECTING:
                    rec_evt = ReconnectEvent(
                        timestamp=now.isoformat(),
                        event_type="RECONNECT",
                        session_id=session_id,
                        provider=session.provider,
                        reconnect_attempt=reconnect_cnt,
                        reason=prov_status.last_error,
                    )
                    self._record_event(session_id, rec_evt)
                    await self._broadcast(session_id, rec_evt)

                # Broadcast ProviderStatusEvent
                status_evt = ProviderStatusEvent(
                    timestamp=now.isoformat(),
                    event_type="PROVIDER_STATUS",
                    session_id=session_id,
                    provider=session.provider,
                    status=session.connection_state,
                    connected=is_connected,
                    reconnect_count=reconnect_cnt,
                    latency_ms=session.latency_ms,
                    is_stale=is_stale,
                    safety_state=session.safety_state,
                    last_heartbeat=prov_status.last_heartbeat_at if prov_status else now.isoformat(),
                    error_message=prov_status.last_error if prov_status else None,
                )
                self._record_event(session_id, status_evt)
                await self._broadcast(session_id, status_evt)

                # Broadcast MarketUpdateEvent for each bar/quote
                for sym, bar in snapshot.bars.items():
                    m_upd = MarketUpdateEvent(
                        timestamp=snapshot.timestamp.isoformat() if hasattr(snapshot.timestamp, "isoformat") else str(snapshot.timestamp),
                        event_type="MARKET_UPDATE",
                        session_id=session_id,
                        symbol=sym,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        bid=bar.bid,
                        ask=bar.ask,
                        mid=bar.mid,
                        last_price=bar.last_price,
                        latency_ms=snapshot.latency_ms,
                        is_stale=is_stale,
                    )
                    self._record_event(session_id, m_upd)
                    await self._broadcast(session_id, m_upd)

                # Tick-to-Bar Aggregation via BarBuilder
                closed_bars: List[OHLCVBar] = []
                if bar_builder is not None:
                    for sym, bar in snapshot.bars.items():
                        tick = MarketTick(
                            symbol=sym,
                            exchange_timestamp=snapshot.timestamp,
                            received_timestamp=snapshot.received_at or now,
                            last_price=bar.last_price or bar.close,
                            bid=bar.bid,
                            ask=bar.ask,
                            volume=bar.volume,
                            source=session.data_provider_type,
                        )
                        c_bar = bar_builder.add_tick(tick)
                        if c_bar is not None:
                            closed_bars.append(c_bar)
                            b_evt = BarClosedEvent(
                                timestamp=c_bar.timestamp.isoformat(),
                                event_type="BAR_CLOSED",
                                session_id=session_id,
                                symbol=sym,
                                interval=bar_builder.interval,
                                open=c_bar.open,
                                high=c_bar.high,
                                low=c_bar.low,
                                close=c_bar.close,
                                volume=c_bar.volume or 0.0,
                                bar_index=session.current_bar_index,
                            )
                            self._record_event(session_id, b_evt)
                            await self._broadcast(session_id, b_evt)

                # Update streaming feature engine with finalized bars or raw snapshots
                if feat_engine is not None:
                    if closed_bars:
                        for cb in closed_bars:
                            feat_engine.update_bar(cb)
                    else:
                        feat_engine.update_snapshot(snapshot)

                # Multi-Asset Snapshot Synchronization & per-symbol staleness check
                is_sync = True
                if synchronizer is not None:
                    synchronizer.update_snapshot(snapshot)
                    if len(session.symbols) > 1:
                        is_sync = synchronizer.is_synchronized(now)
                        stale_syms = synchronizer.get_stale_symbols(max_age_seconds=session.max_data_age_seconds, reference_time=now)
                        if stale_syms:
                            is_stale = True
                    else:
                        is_sync = synchronizer.is_symbol_fresh(session.symbols[0], max_age_seconds=session.max_data_age_seconds, reference_time=now)
                        if not is_sync:
                            is_stale = True

                session.is_stale = is_stale

                # Signal Safety State Machine:
                # CONNECTED + FRESH DATA + SYNCHRONIZED -> SIGNALS_ENABLED
                # DISCONNECTED / RECONNECTING / ERROR / STALE -> SIGNALS_PAUSED
                if is_connected and not is_stale and is_sync and (not prov_status or prov_status.state == ConnectionState.CONNECTED):
                    session.safety_state = SignalSafetyState.SIGNALS_ENABLED.value
                else:
                    session.safety_state = SignalSafetyState.SIGNALS_PAUSED.value

                # Execute step with safety constraints
                step_events = self._execute_step(session_id, snapshot=snapshot, is_sync=is_sync)
                for evt in step_events:
                    await self._broadcast(session_id, evt)

        except asyncio.CancelledError:
            logger.info(f"Live stream loop cancelled for session {session_id}")
        except Exception as e:
            logger.exception(f"Error in live stream loop for session {session_id}: {e}")
            if session_id in self.sessions:
                s = self.sessions[session_id]
                s.status = SessionStatus.ERROR
                s.error_message = str(e)
                self.storage.save_session(s)
        finally:
            if provider and hasattr(provider, "disconnect"):
                try:
                    await provider.disconnect()
                except Exception:
                    pass

    def _execute_step(self, session_id: str, snapshot: Optional[MarketSnapshot] = None, is_sync: bool = True) -> List[PaperEvent]:
        """Core deterministic execution step for a single bar/snapshot."""
        session = self.sessions[session_id]
        provider = self.providers[session_id]
        account = self.accounts[session_id]
        strategy = self.strategies[session_id]
        broker = self.brokers[session_id]
        risk_mgr = self.risk_managers[session_id]
        pos_sizer = self.position_sizers[session_id]
        order_mgr = self.order_managers[session_id]
        jev_provider = self.decision_providers.get(session_id)

        events: List[PaperEvent] = []

        # 1. Advance snapshot
        if snapshot is None:
            idx, snapshot, bars = provider.next_snapshot()
            session.current_bar_index = idx + 1
        else:
            bars = snapshot.bars
            session.current_bar_index += 1

        ts_str = snapshot.timestamp.isoformat() if hasattr(snapshot.timestamp, "isoformat") else str(snapshot.timestamp)
        session.simulation_timestamp = ts_str
        session.last_data_timestamp = ts_str

        current_prices = {sym: bar.close for sym, bar in bars.items()}
        primary_sym = session.symbols[0]
        primary_bar = bars[primary_sym]

        # 2. Emit MarketEvent
        for sym, bar in bars.items():
            m_evt = MarketEvent(
                timestamp=ts_str,
                event_type="MARKET_BAR",
                session_id=session_id,
                symbol=sym,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                bar_index=session.current_bar_index,
                total_bars=session.total_bars,
            )
            self._record_event(session_id, m_evt)
            events.append(m_evt)

        # 3. Process pending orders from broker
        for sym in session.symbols:
            if sym in bars:
                pending_fills = broker.process_pending_orders(bars[sym])
                for fill in pending_fills:
                    account.update_fill(fill)
                    order_mgr.record_fill(fill)
                    self.storage.save_order(order_mgr.orders[fill.order.order_id])
                    if account.portfolio.get_position(fill.order.symbol).quantity == 0:
                        risk_mgr.clear_position_stop(fill.order.symbol)

                    fill_evt = FillExecutionEvent(
                        timestamp=ts_str,
                        event_type="ORDER_FILLED",
                        session_id=session_id,
                        order_id=fill.order.order_id,
                        symbol=fill.order.symbol,
                        side=fill.order.side.value,
                        quantity=fill.quantity,
                        fill_price=fill.fill_price,
                        commission=fill.commission,
                        slippage=fill.slippage,
                    )
                    self._record_event(session_id, fill_evt)
                    events.append(fill_evt)

        # 4. Check active position stops via RiskManager
        triggered_stops = risk_mgr.check_position_stops(
            portfolio=account.portfolio,
            current_prices=current_prices,
            timestamp=snapshot.timestamp,
        )
        for stop_ord in triggered_stops:
            matching_bar = bars[stop_ord.symbol]
            stop_fill = broker.execute_market_order(stop_ord, matching_bar)
            account.update_fill(stop_fill)
            broker.cancel_orders_for_symbol(stop_ord.symbol, OrderType.STOP_LOSS)

            # Record stop fill event
            stop_evt = FillExecutionEvent(
                timestamp=ts_str,
                event_type="STOP_LOSS_TRIGGERED",
                session_id=session_id,
                order_id=stop_ord.order_id,
                symbol=stop_ord.symbol,
                side=stop_ord.side.value,
                quantity=stop_fill.quantity,
                fill_price=stop_fill.fill_price,
                commission=stop_fill.commission,
                slippage=stop_fill.slippage,
            )
            self._record_event(session_id, stop_evt)
            events.append(stop_evt)

        # 5. Extract strict historical slice (zero lookahead)
        feat_engine = self.feature_engines.get(session_id)
        if feat_engine is not None:
            if provider.is_multi_asset():
                hist_slice = feat_engine.get_all_history_dfs()
            else:
                hist_slice = feat_engine.get_history_df(primary_sym)
        else:
            hist_slice = provider.get_slice(session.current_bar_index - 1)
        loop_item = snapshot if provider.is_multi_asset() else primary_bar

        # 6. Strategy evaluation (only if SIGNALS_ENABLED and data is synchronized)
        signals = []
        decision_src = "RULE_BASED"
        model_ver = None
        jev_mode = "NONE"

        if hasattr(strategy, "predictor") and getattr(strategy, "predictor", None) is not None:
            decision_src = "XGBOOST"
            if hasattr(strategy, "artifact") and getattr(strategy, "artifact", None) is not None:
                model_ver = getattr(strategy.artifact, "version", "v1")

        if session.safety_state == SignalSafetyState.SIGNALS_ENABLED.value and is_sync:
            try:
                raw_signals = strategy.generate_signal(loop_item, hist_slice)
                if isinstance(raw_signals, SignalEvent):
                    signals = [raw_signals]
                elif isinstance(raw_signals, list):
                    signals = raw_signals
                else:
                    signals = []
            except Exception as e:
                logger.error(f"Strategy signal generation error in session {session_id}: {e}")
                signals = []

        # Emit MLPredictionEvent and StrategySignalEvent
        for s in signals:
            if decision_src == "XGBOOST":
                pred_val = s.metadata.get("ml_probability", s.strength)
                ml_evt = MLPredictionEvent(
                    timestamp=ts_str,
                    event_type="ML_PREDICTION",
                    session_id=session_id,
                    symbol=s.symbol,
                    model_version=model_ver or "v1",
                    prediction=float(pred_val),
                    features_used=len(s.metadata.get("features", {})),
                )
                self._record_event(session_id, ml_evt)
                events.append(ml_evt)

            sig_evt = StrategySignalEvent(
                timestamp=ts_str,
                event_type="STRATEGY_SIGNAL",
                session_id=session_id,
                symbol=s.symbol,
                signal_type=s.signal_type.value,
                strength=s.strength,
                strategy_name=session.strategy,
                provider=session.provider,
                decision_source=decision_src,
                model_version=model_ver,
                jev_decision_mode=jev_mode,
                metadata=s.metadata,
            )
            self._record_event(session_id, sig_evt)
            events.append(sig_evt)

        # 7. Optional Jev Decision Layer evaluation
        if jev_provider is not None and signals:
            try:
                from backend.app.ai.jev_context import build_market_context
                from backend.app.ai.jev_schema import JevDecisionType

                actionable = [s for s in signals if s.signal_type in (SignalType.BUY, SignalType.SELL)]
                if actionable:
                    ctx = build_market_context(
                        symbol=actionable[0].symbol,
                        historical_slice=hist_slice,
                        portfolio=account.portfolio,
                        signals=signals,
                    )
                    decision = jev_provider.evaluate(ctx)
                    jev_mode = "CACHED_JEV" if getattr(decision, "cached", False) else "LIVE_JEV"
                    decision_src = "JEV_ASSISTED" if decision_src == "XGBOOST" else "JEV"

                    jev_evt = JevDecisionEvent(
                        timestamp=ts_str,
                        event_type="JEV_DECISION",
                        session_id=session_id,
                        symbol=actionable[0].symbol,
                        decision=decision.decision.value if hasattr(decision.decision, "value") else str(decision.decision),
                        confidence=getattr(decision, "confidence", 1.0),
                        mode=jev_mode,
                        rationale=getattr(decision, "rationale", ""),
                    )
                    self._record_event(session_id, jev_evt)
                    events.append(jev_evt)

                    if decision.decision == JevDecisionType.BUY:
                        signals = [s for s in signals if s.signal_type == SignalType.BUY]
                    elif decision.decision == JevDecisionType.SELL:
                        signals = [s for s in signals if s.signal_type == SignalType.SELL]
                    else:
                        signals = []
            except Exception as e:
                logger.warning(f"Jev evaluation failure or timeout: {e}. Defaulting to NO_ACTION.")
                signals = []

        session.decision_source = decision_src

        # 8. Order generation and authoritative RiskManager validation
        for sig in signals:
            tgt_sym = sig.symbol
            tgt_bar = bars.get(tgt_sym, primary_bar)
            tgt_price = tgt_bar.close
            pos = account.portfolio.get_position(tgt_sym)
            stop_price = sig.stop_loss_price or sig.metadata.get("stop_loss")

            if sig.signal_type == SignalType.BUY:
                if pos.quantity < 0:
                    # Covering short
                    qty = abs(pos.quantity)
                    order_rec = order_mgr.create_order(
                        symbol=tgt_sym,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=qty,
                        timestamp=snapshot.timestamp,
                        strategy_name=session.strategy,
                        provider=session.provider,
                        decision_source=decision_src,
                        model_version=model_ver,
                        jev_mode=jev_mode,
                    )
                    b_order = Order(
                        order_id=order_rec.order_id,
                        symbol=tgt_sym,
                        order_type=OrderType.MARKET,
                        side=OrderSide.BUY,
                        quantity=qty,
                        created_at=snapshot.timestamp,
                    )
                    is_valid, reason = risk_mgr.validate_order(b_order, tgt_price, account.portfolio)
                    r_evt = RiskValidationEvent(
                        timestamp=ts_str,
                        event_type="RISK_VALIDATION",
                        session_id=session_id,
                        symbol=tgt_sym,
                        approved=is_valid,
                        reason=reason,
                        requested_qty=qty,
                        approved_qty=qty if is_valid else 0.0,
                    )
                    self._record_event(session_id, r_evt)
                    events.append(r_evt)

                    if is_valid:
                        fill = broker.execute_market_order(b_order, tgt_bar)
                        account.update_fill(fill)
                        order_mgr.record_fill(fill)
                        self.storage.save_order(order_rec)
                        risk_mgr.clear_position_stop(tgt_sym)
                        broker.cancel_orders_for_symbol(tgt_sym, OrderType.STOP_LOSS)

                        f_evt = FillExecutionEvent(
                            timestamp=ts_str,
                            event_type="ORDER_FILLED",
                            session_id=session_id,
                            order_id=b_order.order_id,
                            symbol=tgt_sym,
                            side="BUY",
                            quantity=fill.quantity,
                            fill_price=fill.fill_price,
                            commission=fill.commission,
                            slippage=fill.slippage,
                        )
                        self._record_event(session_id, f_evt)
                        events.append(f_evt)
                    else:
                        order_mgr.record_rejection(order_rec.order_id, reason or "Risk limit exceeded")
                        self.storage.save_order(order_rec)
                else:
                    # Opening / expanding long
                    hedge_ratio = sig.metadata.get("hedge_qty_ratio")
                    if tgt_sym == primary_sym or hedge_ratio is None:
                        qty = pos_sizer.calculate_quantity(tgt_sym, tgt_price, account.portfolio)
                    else:
                        base_p = current_prices.get(primary_sym, tgt_price)
                        base_qty = pos_sizer.calculate_quantity(primary_sym, base_p, account.portfolio)
                        qty = round(base_qty * float(hedge_ratio), 4)

                    if qty > 0:
                        order_rec = order_mgr.create_order(
                            symbol=tgt_sym,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            quantity=qty,
                            timestamp=snapshot.timestamp,
                            strategy_name=session.strategy,
                            provider=session.provider,
                            decision_source=decision_src,
                            model_version=model_ver,
                            jev_mode=jev_mode,
                        )
                        b_order = Order(
                            order_id=order_rec.order_id,
                            symbol=tgt_sym,
                            order_type=OrderType.MARKET,
                            side=OrderSide.BUY,
                            quantity=qty,
                            created_at=snapshot.timestamp,
                        )
                        is_valid, reason = risk_mgr.validate_order(b_order, tgt_price, account.portfolio)
                        r_evt = RiskValidationEvent(
                            timestamp=ts_str,
                            event_type="RISK_VALIDATION",
                            session_id=session_id,
                            symbol=tgt_sym,
                            approved=is_valid,
                            reason=reason,
                            requested_qty=qty,
                            approved_qty=qty if is_valid else 0.0,
                        )
                        self._record_event(session_id, r_evt)
                        events.append(r_evt)

                        if is_valid:
                            fill = broker.execute_market_order(b_order, tgt_bar)
                            account.update_fill(fill)
                            order_mgr.record_fill(fill)
                            self.storage.save_order(order_rec)

                            if stop_price is not None:
                                risk_mgr.set_position_stop(tgt_sym, float(stop_price))
                                broker.cancel_orders_for_symbol(tgt_sym, OrderType.STOP_LOSS)
                                stop_order = Order(
                                    symbol=tgt_sym,
                                    order_type=OrderType.STOP_LOSS,
                                    side=OrderSide.SELL,
                                    quantity=qty,
                                    stop_price=float(stop_price),
                                    created_at=snapshot.timestamp,
                                    timestamp=snapshot.timestamp,
                                )
                                broker.submit_order(stop_order)

                            f_evt = FillExecutionEvent(
                                timestamp=ts_str,
                                event_type="ORDER_FILLED",
                                session_id=session_id,
                                order_id=b_order.order_id,
                                symbol=tgt_sym,
                                side="BUY",
                                quantity=fill.quantity,
                                fill_price=fill.fill_price,
                                commission=fill.commission,
                                slippage=fill.slippage,
                            )
                            self._record_event(session_id, f_evt)
                            events.append(f_evt)
                        else:
                            order_mgr.record_rejection(order_rec.order_id, reason or "Risk limit exceeded")
                            self.storage.save_order(order_rec)

            elif sig.signal_type == SignalType.SELL:
                if pos.quantity > 0:
                    # Closing long
                    qty = pos.quantity
                    order_rec = order_mgr.create_order(
                        symbol=tgt_sym,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=qty,
                        timestamp=snapshot.timestamp,
                        strategy_name=session.strategy,
                        provider=session.provider,
                        decision_source=decision_src,
                        model_version=model_ver,
                        jev_mode=jev_mode,
                    )
                    b_order = Order(
                        order_id=order_rec.order_id,
                        symbol=tgt_sym,
                        order_type=OrderType.MARKET,
                        side=OrderSide.SELL,
                        quantity=qty,
                        created_at=snapshot.timestamp,
                    )
                    is_valid, reason = risk_mgr.validate_order(b_order, tgt_price, account.portfolio)
                    r_evt = RiskValidationEvent(
                        timestamp=ts_str,
                        event_type="RISK_VALIDATION",
                        session_id=session_id,
                        symbol=tgt_sym,
                        approved=is_valid,
                        reason=reason,
                        requested_qty=qty,
                        approved_qty=qty if is_valid else 0.0,
                    )
                    self._record_event(session_id, r_evt)
                    events.append(r_evt)

                    if is_valid:
                        fill = broker.execute_market_order(b_order, tgt_bar)
                        account.update_fill(fill)
                        order_mgr.record_fill(fill)
                        self.storage.save_order(order_rec)
                        risk_mgr.clear_position_stop(tgt_sym)
                        broker.cancel_orders_for_symbol(tgt_sym, OrderType.STOP_LOSS)

                        f_evt = FillExecutionEvent(
                            timestamp=ts_str,
                            event_type="ORDER_FILLED",
                            session_id=session_id,
                            order_id=b_order.order_id,
                            symbol=tgt_sym,
                            side="SELL",
                            quantity=fill.quantity,
                            fill_price=fill.fill_price,
                            commission=fill.commission,
                            slippage=fill.slippage,
                        )
                        self._record_event(session_id, f_evt)
                        events.append(f_evt)
                    else:
                        order_mgr.record_rejection(order_rec.order_id, reason or "Risk limit exceeded")
                        self.storage.save_order(order_rec)
                elif account.portfolio.allow_shorting:
                    # Opening short position
                    hedge_ratio = sig.metadata.get("hedge_qty_ratio")
                    if tgt_sym == primary_sym or hedge_ratio is None:
                        qty = pos_sizer.calculate_quantity(tgt_sym, tgt_price, account.portfolio)
                    else:
                        base_p = current_prices.get(primary_sym, tgt_price)
                        base_qty = pos_sizer.calculate_quantity(primary_sym, base_p, account.portfolio)
                        qty = round(base_qty * float(hedge_ratio), 4)

                    if qty > 0:
                        order_rec = order_mgr.create_order(
                            symbol=tgt_sym,
                            side=OrderSide.SELL,
                            order_type=OrderType.MARKET,
                            quantity=qty,
                            timestamp=snapshot.timestamp,
                            strategy_name=session.strategy,
                            provider=session.provider,
                            decision_source=decision_src,
                            model_version=model_ver,
                            jev_mode=jev_mode,
                        )
                        b_order = Order(
                            order_id=order_rec.order_id,
                            symbol=tgt_sym,
                            order_type=OrderType.MARKET,
                            side=OrderSide.SELL,
                            quantity=qty,
                            created_at=snapshot.timestamp,
                        )
                        is_valid, reason = risk_mgr.validate_order(b_order, tgt_price, account.portfolio)
                        r_evt = RiskValidationEvent(
                            timestamp=ts_str,
                            event_type="RISK_VALIDATION",
                            session_id=session_id,
                            symbol=tgt_sym,
                            approved=is_valid,
                            reason=reason,
                            requested_qty=qty,
                            approved_qty=qty if is_valid else 0.0,
                        )
                        self._record_event(session_id, r_evt)
                        events.append(r_evt)

                        if is_valid:
                            fill = broker.execute_market_order(b_order, tgt_bar)
                            account.update_fill(fill)
                            order_mgr.record_fill(fill)
                            self.storage.save_order(order_rec)

                            if stop_price is not None:
                                risk_mgr.set_position_stop(tgt_sym, float(stop_price))
                                broker.cancel_orders_for_symbol(tgt_sym, OrderType.STOP_LOSS)
                                stop_order = Order(
                                    symbol=tgt_sym,
                                    order_type=OrderType.STOP_LOSS,
                                    side=OrderSide.BUY,
                                    quantity=qty,
                                    stop_price=float(stop_price),
                                    created_at=snapshot.timestamp,
                                    timestamp=snapshot.timestamp,
                                )
                                broker.submit_order(stop_order)

                            f_evt = FillExecutionEvent(
                                timestamp=ts_str,
                                event_type="ORDER_FILLED",
                                session_id=session_id,
                                order_id=b_order.order_id,
                                symbol=tgt_sym,
                                side="SELL",
                                quantity=fill.quantity,
                                fill_price=fill.fill_price,
                                commission=fill.commission,
                                slippage=fill.slippage,
                            )
                            self._record_event(session_id, f_evt)
                            events.append(f_evt)
                        else:
                            order_mgr.record_rejection(order_rec.order_id, reason or "Risk limit exceeded")
                            self.storage.save_order(order_rec)

        # 9. Update portfolio equity and account metrics
        account.record_bar_equity(current_prices, snapshot.timestamp)
        tot_eq = account.get_total_equity(current_prices)
        cash_val = account.get_cash()
        realized_pnl = account.get_realized_pnl()
        unrealized_pnl = account.get_unrealized_pnl(current_prices)
        exposure = account.get_exposure(current_prices)

        session.current_equity = tot_eq
        session.cash = cash_val
        session.realized_pnl = realized_pnl
        session.unrealized_pnl = unrealized_pnl
        session.current_exposure = exposure

        pos_dict = {
            p["symbol"]: p for p in account.get_positions_summary(current_prices)
        }
        port_evt = PortfolioUpdateEvent(
            timestamp=ts_str,
            event_type="PORTFOLIO_SNAPSHOT",
            session_id=session_id,
            total_equity=tot_eq,
            cash=cash_val,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            current_exposure=exposure,
            positions=pos_dict,
        )
        self._record_event(session_id, port_evt)
        events.append(port_evt)

        # Persist session to disk
        self.storage.save_session(session)

        return events

    def _record_event(self, session_id: str, event: PaperEvent) -> None:
        d = event.to_dict()
        if session_id not in self.recent_events:
            self.recent_events[session_id] = []
        self.recent_events[session_id].append(d)
        if len(self.recent_events[session_id]) > 500:
            self.recent_events[session_id].pop(0)

        # Persist to SQLite
        try:
            self.storage.save_event(session_id, event.timestamp, event.event_type, d)
        except Exception as e:
            logger.warning(f"Could not persist event: {e}")

    async def _broadcast(self, session_id: str, event: PaperEvent) -> None:
        subscribers = self.subscribers.get(session_id, set())
        if not subscribers:
            return

        payload = event.to_dict()
        dead = set()
        for ws in subscribers:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await asyncio.wait_for(ws.send_json(payload), timeout=0.1)
                else:
                    dead.add(ws)
            except Exception:
                dead.add(ws)

        for d in dead:
            subscribers.discard(d)

    def register_websocket(self, session_id: str, ws: WebSocket) -> None:
        if session_id not in self.subscribers:
            self.subscribers[session_id] = set()
        self.subscribers[session_id].add(ws)

    def unregister_websocket(self, session_id: str, ws: WebSocket) -> None:
        if session_id in self.subscribers:
            self.subscribers[session_id].discard(ws)

    def get_session(self, session_id: str) -> Optional[PaperTradingSession]:
        return self.sessions.get(session_id) or self.storage.load_session(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        # Return all in-memory or persisted sessions
        out = [s.to_dict() for s in self.sessions.values()]
        known_ids = {s["session_id"] for s in out}
        from_db = self.storage.list_sessions(limit=50)
        for row in from_db:
            if row["session_id"] not in known_ids:
                out.append(row)
        return sorted(out, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_orders(self, session_id: str) -> List[Dict[str, Any]]:
        if session_id in self.order_managers:
            return [o.to_dict() for o in self.order_managers[session_id].orders.values()]
        return self.storage.load_orders(session_id)

    def get_positions(self, session_id: str) -> List[Dict[str, Any]]:
        account = self.accounts.get(session_id)
        if not account:
            return []
        provider = self.providers.get(session_id)
        current_prices = {}
        if provider:
            if hasattr(provider, "latest_snapshot") and provider.latest_snapshot() is not None:
                last_snap = provider.latest_snapshot()
                current_prices = {s: b.close for s, b in last_snap.bars.items()}
            elif getattr(provider, "current_index", 0) > 0 and hasattr(provider, "snapshots"):
                last_snap = provider.snapshots[provider.current_index - 1]
                current_prices = {s: b.close for s, b in last_snap.bars.items()}
        return account.get_positions_summary(current_prices)

    def get_events(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        mem = self.recent_events.get(session_id, [])
        if mem:
            return mem[-limit:]
        return self.storage.load_events(session_id, limit=limit)

    def export_results(self, session_id: str) -> Dict[str, Any]:
        session = self._get_required_session(session_id)
        account = self.accounts.get(session_id)
        orders = self.get_orders(session_id)
        events = self.get_events(session_id, limit=500)

        equity_curve = []
        trades = []
        if account:
            equity_curve = [
                {
                    "timestamp": ep.timestamp.isoformat() if hasattr(ep.timestamp, "isoformat") else str(ep.timestamp),
                    "equity": ep.total_equity,
                    "cash": ep.cash,
                    "realized_pnl": ep.realized_pnl,
                    "unrealized_pnl": ep.unrealized_pnl,
                }
                for ep in account.portfolio.equity_history
            ]
            raw_trades = account.get_completed_trades()
            order_map = {o.get("order_id"): o for o in orders if isinstance(o, dict) and "order_id" in o}
            for tr in raw_trades:
                tr_dict = dict(tr)
                oid = tr_dict.get("order_id")
                matched_order = order_map.get(oid) if oid else None
                if matched_order:
                    tr_dict["decision_source"] = matched_order.get("decision_source", session.decision_source or "RULE_BASED")
                    tr_dict["model_version"] = matched_order.get("model_version")
                    tr_dict["jev_mode"] = matched_order.get("jev_mode", "NONE")
                else:
                    tr_dict.setdefault("decision_source", session.decision_source or "RULE_BASED")
                    tr_dict.setdefault("model_version", None)
                    tr_dict.setdefault("jev_mode", "NONE")
                trades.append(tr_dict)

        return {
            "session": session.to_dict(),
            "summary": {
                "initial_capital": session.initial_capital,
                "current_equity": session.current_equity,
                "net_profit": round(session.current_equity - session.initial_capital, 2),
                "return_pct": round(((session.current_equity - session.initial_capital) / session.initial_capital) * 100, 2),
                "realized_pnl": session.realized_pnl,
                "unrealized_pnl": session.unrealized_pnl,
                "total_trades": len(trades),
                "total_orders": len(orders),
                "total_bars_replayed": session.current_bar_index,
                "status": session.status.value,
            },
            "equity_curve": equity_curve,
            "trades": trades,
            "orders": orders,
            "events_sample": events[-50:],
        }

    def _get_required_session(self, session_id: str) -> PaperTradingSession:
        sess = self.get_session(session_id)
        if not sess:
            raise KeyError(f"Session '{session_id}' not found.")
        return sess


# Global shared singleton instance for the application
paper_service = PaperTradingService()
