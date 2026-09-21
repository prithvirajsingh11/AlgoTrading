from __future__ import annotations
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import pandas as pd
from backend.app.data.loader import OHLCVBar, CSVDataLoader
from backend.app.data.cleaner import clean_and_validate

if TYPE_CHECKING:
    from backend.app.strategies.base import BaseStrategy
from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    SignalType,
    SignalEvent,
)
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.portfolio import Portfolio
from backend.app.risk.position_sizing import BasePositionSizer, PercentEquitySizer
from backend.app.risk.risk_manager import RiskManager
from backend.app.risk.metrics import (
    BacktestResult,
    calculate_performance_metrics,
)


class BacktestEngine:
    """Event-driven algorithmic trading backtest engine.

    Strict chronological processing, zero lookahead bias, simulated order execution,
    real-time portfolio accounting, risk controls, and quantitative metrics computation.
    """

    def __init__(
        self,
        symbol: str,
        initial_capital: float = 100_000.0,
        commission_fixed: float = 1.0,
        commission_percent: float = 0.0005,
        slippage_bps: float = 5.0,
        max_position_pct: float = 0.50,
        max_drawdown_limit: float = 0.30,
        allow_shorting: bool = False,
        position_sizer: Optional[BasePositionSizer] = None,
        risk_manager: Optional[RiskManager] = None,
        broker: Optional[SimulatedBroker] = None,
    ):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.allow_shorting = allow_shorting
        self.broker = broker or SimulatedBroker(
            commission_fixed=commission_fixed,
            commission_percent=commission_percent,
            slippage_bps=slippage_bps,
        )
        self.risk_manager = risk_manager or RiskManager(
            max_position_pct=max_position_pct,
            max_drawdown_limit=max_drawdown_limit,
            allow_shorting=allow_shorting,
        )
        if allow_shorting and not self.risk_manager.allow_shorting:
            self.risk_manager.allow_shorting = True

        self.position_sizer = position_sizer or PercentEquitySizer(percent_equity=0.20)
        self.portfolio = Portfolio(initial_cash=initial_capital, allow_shorting=allow_shorting)

    def _calculate_order_qty(
        self,
        symbol: str,
        price: float,
        stop_loss_price: Optional[float] = None,
    ) -> float:
        if (
            hasattr(self.position_sizer, "calculate_quantity")
            and "stop_loss_price" in self.position_sizer.calculate_quantity.__code__.co_varnames
        ):
            return self.position_sizer.calculate_quantity(
                symbol=symbol,
                price=price,
                portfolio=self.portfolio,
                stop_loss_price=stop_loss_price,
            )
        else:
            return self.position_sizer.calculate_quantity(
                symbol=symbol,
                price=price,
                portfolio=self.portfolio,
            )

    def run(
        self,
        df: Union[pd.DataFrame, Dict[str, pd.DataFrame], None] = None,
        strategy: Optional[BaseStrategy] = None,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame], None] = None,
        **kwargs,
    ) -> BacktestResult:
        """Executes event-driven backtest over single or multi-asset historical data."""
        from backend.app.data.cleaner import clean_and_validate, synchronize_pair_datasets
        from backend.app.data.loader import MarketSnapshot

        dataset = df if df is not None else data
        if dataset is None:
            dataset = kwargs.get("data")
        if dataset is None:
            raise ValueError("Must provide historical dataset (df or data).")

        strat = strategy or kwargs.get("strategy")
        if strat is None:
            raise ValueError("Must provide a strategy.")

        strat.reset()

        # 1. Dataset preparation & synchronization
        is_multi = isinstance(dataset, dict)
        if not is_multi:
            cleaned_df = clean_and_validate(dataset, strict=True)
            bars: List[OHLCVBar] = CSVDataLoader.to_bars(cleaned_df, symbol=self.symbol)
            loop_items = bars
            symbols = [self.symbol]
        else:
            data_keys = list(dataset.keys())
            # If strategy specifies symbol and hedge_symbol, align in that order
            strat_sym = getattr(strat, "symbol", data_keys[0])
            strat_hedge = getattr(strat, "hedge_symbol", data_keys[1] if len(data_keys) > 1 else None)
            if strat_hedge and strat_hedge in dataset and strat_sym in dataset:
                symbols = [strat_sym, strat_hedge]
            else:
                symbols = data_keys

            if len(symbols) == 2:
                synced_a, synced_b, snapshots = synchronize_pair_datasets(
                    dataset[symbols[0]], dataset[symbols[1]], symbol_a=symbols[0], symbol_b=symbols[1]
                )
                aligned_data = {symbols[0]: synced_a, symbols[1]: synced_b}
                loop_items = snapshots
            else:
                aligned_data = {}
                common_timestamps = None
                for sym in symbols:
                    c_df = clean_and_validate(dataset[sym], strict=True)
                    aligned_data[sym] = c_df
                    ts_set = set(c_df["timestamp"])
                    common_timestamps = ts_set if common_timestamps is None else common_timestamps.intersection(ts_set)
                common_list = sorted(list(common_timestamps or []))
                for sym in symbols:
                    aligned_data[sym] = (
                        aligned_data[sym][aligned_data[sym]["timestamp"].isin(common_list)]
                        .sort_values(by="timestamp")
                        .reset_index(drop=True)
                    )

                # Construct chronological MarketSnapshots
                timestamps = aligned_data[symbols[0]]["timestamp"]
                bars_by_sym = {sym: CSVDataLoader.to_bars(aligned_data[sym], symbol=sym) for sym in symbols}
                snapshots = []
                for i, ts in enumerate(timestamps):
                    snap_bars = {sym: bars_by_sym[sym][i] for sym in symbols}
                    snapshots.append(MarketSnapshot(timestamp=ts, bars=snap_bars))
                loop_items = snapshots

        # 2. Chronological event loop
        for i, item in enumerate(loop_items):
            if is_multi:
                snapshot: MarketSnapshot = item
                current_prices = {sym: snapshot.bars[sym].close for sym in symbols}
                current_ts = snapshot.timestamp
            else:
                bar: OHLCVBar = item
                current_prices = {self.symbol: bar.close}
                current_ts = bar.timestamp

            # A. Process any pending orders from prior bars
            if is_multi:
                for sym in symbols:
                    fills = self.broker.process_pending_orders(snapshot.bars[sym])
                    for fill in fills:
                        self.portfolio.update_fill(fill)
                        if self.portfolio.get_position(fill.order.symbol).quantity == 0:
                            self.risk_manager.clear_position_stop(fill.order.symbol)
            else:
                fills = self.broker.process_pending_orders(bar)
                for fill in fills:
                    self.portfolio.update_fill(fill)
                    if self.portfolio.get_position(fill.order.symbol).quantity == 0:
                        self.risk_manager.clear_position_stop(fill.order.symbol)

            # B. Check active position stop-losses via RiskManager
            stop_orders = self.risk_manager.check_position_stops(
                portfolio=self.portfolio,
                current_prices=current_prices,
                timestamp=current_ts,
            )
            for stop_order in stop_orders:
                matching_bar = snapshot.bars[stop_order.symbol] if is_multi else bar
                stop_fill = self.broker.execute_market_order(stop_order, matching_bar)
                self.portfolio.update_fill(stop_fill)
                self.broker.cancel_orders_for_symbol(stop_order.symbol, OrderType.STOP_LOSS)

            # C. Strict historical slice up to current bar (zero lookahead bias)
            if is_multi:
                historical_slice = {sym: aligned_data[sym].iloc[: i + 1] for sym in symbols}
            else:
                historical_slice = cleaned_df.iloc[: i + 1]

            # D. Strategy evaluation
            raw_signal = strat.generate_signal(item, historical_slice)
            if isinstance(raw_signal, SignalEvent):
                signals = [raw_signal]
            elif isinstance(raw_signal, list):
                signals = raw_signal
            else:
                signals = []

            # E. Order generation and execution
            for signal in signals:
                target_sym = signal.symbol
                target_bar = snapshot.bars[target_sym] if is_multi else bar
                target_price = target_bar.close
                pos = self.portfolio.get_position(target_sym)
                stop_price = signal.stop_loss_price or signal.metadata.get("stop_loss")

                if signal.signal_type == SignalType.BUY:
                    if pos.quantity < 0:
                        # Covering an existing short position
                        qty = abs(pos.quantity)
                        order = Order(
                            symbol=target_sym,
                            order_type=OrderType.MARKET,
                            side=OrderSide.BUY,
                            quantity=qty,
                            created_at=current_ts,
                        )
                        is_valid, reason = self.risk_manager.validate_order(order, target_price, self.portfolio)
                        if is_valid:
                            fill = self.broker.execute_market_order(order, target_bar)
                            self.portfolio.update_fill(fill)
                            self.risk_manager.clear_position_stop(target_sym)
                            self.broker.cancel_orders_for_symbol(target_sym, OrderType.STOP_LOSS)
                    else:
                        # Opening or adding to long position
                        hedge_qty_ratio = signal.metadata.get("hedge_qty_ratio")
                        if target_sym == self.symbol or hedge_qty_ratio is None:
                            qty = self._calculate_order_qty(target_sym, target_price, stop_price)
                        else:
                            base_price = current_prices.get(self.symbol, target_price)
                            base_qty = self._calculate_order_qty(self.symbol, base_price, None)
                            qty = round(base_qty * float(hedge_qty_ratio), 4)

                        if qty > 0:
                            order = Order(
                                symbol=target_sym,
                                order_type=OrderType.MARKET,
                                side=OrderSide.BUY,
                                quantity=qty,
                                created_at=current_ts,
                            )
                            is_valid, reason = self.risk_manager.validate_order(order, target_price, self.portfolio)
                            if is_valid:
                                fill = self.broker.execute_market_order(order, target_bar)
                                self.portfolio.update_fill(fill)
                                if stop_price is not None:
                                    self.risk_manager.set_position_stop(target_sym, float(stop_price))
                                    self.broker.cancel_orders_for_symbol(target_sym, OrderType.STOP_LOSS)
                                    stop_order = Order(
                                        symbol=target_sym,
                                        order_type=OrderType.STOP_LOSS,
                                        side=OrderSide.SELL,
                                        quantity=qty,
                                        stop_price=float(stop_price),
                                        created_at=current_ts,
                                    )
                                    self.broker.submit_order(stop_order)

                elif signal.signal_type == SignalType.SELL:
                    if pos.quantity > 0:
                        # Closing an existing long position
                        qty = pos.quantity
                        order = Order(
                            symbol=target_sym,
                            order_type=OrderType.MARKET,
                            side=OrderSide.SELL,
                            quantity=qty,
                            created_at=current_ts,
                        )
                        is_valid, reason = self.risk_manager.validate_order(order, target_price, self.portfolio)
                        if is_valid:
                            fill = self.broker.execute_market_order(order, target_bar)
                            self.portfolio.update_fill(fill)
                            self.risk_manager.clear_position_stop(target_sym)
                            self.broker.cancel_orders_for_symbol(target_sym, OrderType.STOP_LOSS)
                    elif self.risk_manager.allow_shorting or self.portfolio.allow_shorting:
                        # Opening or adding to short position
                        hedge_qty_ratio = signal.metadata.get("hedge_qty_ratio")
                        if target_sym == self.symbol or hedge_qty_ratio is None:
                            qty = self._calculate_order_qty(target_sym, target_price, stop_price)
                        else:
                            base_price = current_prices.get(self.symbol, target_price)
                            base_qty = self._calculate_order_qty(self.symbol, base_price, None)
                            qty = round(base_qty * float(hedge_qty_ratio), 4)

                        if qty > 0:
                            order = Order(
                                symbol=target_sym,
                                order_type=OrderType.MARKET,
                                side=OrderSide.SELL,
                                quantity=qty,
                                created_at=current_ts,
                            )
                            is_valid, reason = self.risk_manager.validate_order(order, target_price, self.portfolio)
                            if is_valid:
                                fill = self.broker.execute_market_order(order, target_bar)
                                self.portfolio.update_fill(fill)
                                if stop_price is not None:
                                    self.risk_manager.set_position_stop(target_sym, float(stop_price))
                                    self.broker.cancel_orders_for_symbol(target_sym, OrderType.STOP_LOSS)
                                    stop_order = Order(
                                        symbol=target_sym,
                                        order_type=OrderType.STOP_LOSS,
                                        side=OrderSide.BUY,
                                        quantity=qty,
                                        stop_price=float(stop_price),
                                        created_at=current_ts,
                                    )
                                    self.broker.submit_order(stop_order)

            # F. Mark-to-market at bar close
            self.portfolio.mark_to_market(current_ts, current_prices)

        # 3. Compile performance metrics
        metrics = calculate_performance_metrics(
            equity_history=self.portfolio.equity_history,
            trades=self.trades,
            initial_capital=self.initial_capital,
        )

        return BacktestResult(
            strategy_name=strat.name,
            symbol=self.symbol,
            parameters=strat.parameters,
            metrics=metrics,
            equity_curve=[pt.to_dict() for pt in self.portfolio.equity_history],
            trades=[t.to_dict() for t in self.portfolio.trades],
        )

    @property
    def trades(self) -> list:
        return self.portfolio.trades
