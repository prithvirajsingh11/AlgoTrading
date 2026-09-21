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
        position_sizer: Optional[BasePositionSizer] = None,
        risk_manager: Optional[RiskManager] = None,
        broker: Optional[SimulatedBroker] = None,
    ):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.broker = broker or SimulatedBroker(
            commission_fixed=commission_fixed,
            commission_percent=commission_percent,
            slippage_bps=slippage_bps,
        )
        self.risk_manager = risk_manager or RiskManager(
            max_position_pct=max_position_pct,
            max_drawdown_limit=max_drawdown_limit,
            allow_shorting=False,
        )
        self.position_sizer = position_sizer or PercentEquitySizer(percent_equity=0.20)
        self.portfolio = Portfolio(initial_cash=initial_capital)

    def run(self, df: pd.DataFrame, strategy: BaseStrategy) -> BacktestResult:
        """Executes event-driven backtest over historical OHLCV data."""
        # 1. Clean & validate historical dataset
        cleaned_df = clean_and_validate(df, strict=True)
        bars: List[OHLCVBar] = CSVDataLoader.to_bars(cleaned_df)

        strategy.reset()

        # 2. Chronological event loop
        for i, bar in enumerate(bars):
            current_prices = {self.symbol: bar.close}

            # A. Process any pending limit or stop orders from prior bars
            fills = self.broker.process_pending_orders(bar)
            for fill in fills:
                self.portfolio.update_fill(fill)

            # B. Check active position stop-losses via RiskManager
            stop_orders = self.risk_manager.check_position_stops(
                portfolio=self.portfolio,
                current_prices=current_prices,
                timestamp=bar.timestamp,
            )
            for stop_order in stop_orders:
                stop_fill = self.broker.execute_market_order(stop_order, bar)
                self.portfolio.update_fill(stop_fill)

            # C. Strict slice of historical data up to and including current bar
            historical_slice = cleaned_df.iloc[: i + 1]

            # D. Strategy evaluation
            signal: Optional[SignalEvent] = strategy.generate_signal(bar, historical_slice)

            # E. Handle generated signals
            if signal is not None:
                if signal.signal_type == SignalType.BUY:
                    stop_price = signal.stop_loss_price or signal.metadata.get("stop_loss")
                    if hasattr(self.position_sizer, "calculate_quantity") and "stop_loss_price" in self.position_sizer.calculate_quantity.__code__.co_varnames:
                        qty = self.position_sizer.calculate_quantity(
                            symbol=self.symbol,
                            price=bar.close,
                            portfolio=self.portfolio,
                            stop_loss_price=stop_price,
                        )
                    else:
                        qty = self.position_sizer.calculate_quantity(
                            symbol=self.symbol,
                            price=bar.close,
                            portfolio=self.portfolio,
                        )

                    if qty > 0:
                        order = Order(
                            symbol=self.symbol,
                            order_type=OrderType.MARKET,
                            side=OrderSide.BUY,
                            quantity=qty,
                            created_at=bar.timestamp,
                        )
                        is_valid, reason = self.risk_manager.validate_order(
                            order=order,
                            current_price=bar.close,
                            portfolio=self.portfolio,
                        )
                        if is_valid:
                            fill = self.broker.execute_market_order(order, bar)
                            self.portfolio.update_fill(fill)
                            if stop_price is not None:
                                self.risk_manager.set_position_stop(self.symbol, float(stop_price))

                elif signal.signal_type == SignalType.SELL:
                    pos = self.portfolio.get_position(self.symbol)
                    if pos.quantity > 0:
                        order = Order(
                            symbol=self.symbol,
                            order_type=OrderType.MARKET,
                            side=OrderSide.SELL,
                            quantity=pos.quantity,
                            created_at=bar.timestamp,
                        )
                        is_valid, reason = self.risk_manager.validate_order(
                            order=order,
                            current_price=bar.close,
                            portfolio=self.portfolio,
                        )
                        if is_valid:
                            fill = self.broker.execute_market_order(order, bar)
                            self.portfolio.update_fill(fill)
                            self.risk_manager.clear_position_stop(self.symbol)

            # E. Mark-to-market at bar close
            self.portfolio.mark_to_market(bar.timestamp, current_prices)

        # 3. Compile performance metrics
        metrics = calculate_performance_metrics(
            equity_history=self.portfolio.equity_history,
            trades=self.trades,
            initial_capital=self.initial_capital,
        )

        return BacktestResult(
            strategy_name=strategy.name,
            symbol=self.symbol,
            parameters=strategy.parameters,
            metrics=metrics,
            equity_curve=[pt.to_dict() for pt in self.portfolio.equity_history],
            trades=[t.to_dict() for t in self.portfolio.trades],
        )

    @property
    def trades(self) -> list:
        return self.portfolio.trades
