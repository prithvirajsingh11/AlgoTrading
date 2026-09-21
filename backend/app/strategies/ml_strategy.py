"""Machine Learning trading strategy using XGBoost probability inference.

Implements BaseStrategy contract:
MarketSnapshot / OHLCVBar -> FeatureBuilder -> MLPredictor -> Probability -> SignalEvent
Authoritative RiskManager downstream enforces position sizing, limits, and stops.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Union, List
import pandas as pd

from backend.app.strategies.base import BaseStrategy
from backend.app.data.loader import OHLCVBar, MarketSnapshot
from backend.app.backtesting.orders import SignalEvent, SignalType
from backend.app.ml.features import FeatureEngineer, FeatureConfig
from backend.app.ml.artifacts import MLModelArtifact
from backend.app.ml.inference import MLPredictor, MLPrediction


class MLStrategy(BaseStrategy):
    """Trading strategy guided by directional machine learning probabilities."""

    def __init__(self, symbol: str, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(name="MLStrategy", symbol=symbol, parameters=parameters)

        params = self.parameters
        self.buy_threshold: float = float(params.get("buy_threshold", 0.55))
        self.sell_threshold: float = float(params.get("sell_threshold", 0.45))

        if self.buy_threshold <= self.sell_threshold:
            raise ValueError(
                f"buy_threshold ({self.buy_threshold}) must be strictly greater than "
                f"sell_threshold ({self.sell_threshold})."
            )

        # Artifact resolution
        artifact = params.get("artifact")
        artifact_path = params.get("artifact_path")

        if artifact is not None:
            if isinstance(artifact, dict):
                self.artifact = MLModelArtifact.from_dict(artifact)
            else:
                self.artifact = artifact
        elif artifact_path is not None:
            self.artifact = MLModelArtifact.load(artifact_path)
        else:
            self.artifact = None

        fe_cfg = params.get("feature_config")
        if isinstance(fe_cfg, dict):
            self.feature_config = FeatureConfig.from_dict(fe_cfg)
        elif isinstance(fe_cfg, FeatureConfig):
            self.feature_config = fe_cfg
        else:
            self.feature_config = FeatureConfig()

        self.feature_engineer = FeatureEngineer(self.feature_config)
        self.warmup_period: int = self.feature_engineer.warmup_bars

        self.predictor: Optional[MLPredictor] = None
        if self.artifact is not None:
            self.predictor = MLPredictor(self.artifact)

    def set_artifact(self, artifact: MLModelArtifact) -> None:
        """Sets or updates the model artifact for inference."""
        self.artifact = artifact
        self.predictor = MLPredictor(artifact)

    def generate_signal(
        self,
        bar: Union[OHLCVBar, MarketSnapshot],
        history_df: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    ) -> Optional[SignalEvent]:
        """Evaluates historical bar slice up to timestamp t and emits trading signal.

        Strictly avoids lookahead: history_df contains bars strictly up to current bar.
        """
        if self.predictor is None:
            return None

        # Resolve asset dataframe
        if isinstance(history_df, dict):
            df_sym = history_df.get(self.symbol)
            if df_sym is None:
                return None
        else:
            df_sym = history_df

        if len(df_sym) < self.warmup_period:
            return None

        # Extract features for latest bar strictly from history_df
        bar_features = self.feature_engineer.compute_bar_features(df_sym)
        if bar_features.empty:
            return None

        # Resolve timestamp & close price
        if isinstance(bar, MarketSnapshot):
            current_bar = bar.bars.get(self.symbol)
            if current_bar is None:
                return None
            ts = current_bar.timestamp
            price = current_bar.close
        else:
            ts = bar.timestamp
            price = bar.close

        # Model inference
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        try:
            pred: MLPrediction = self.predictor.predict_bar(
                features_df=bar_features,
                timestamp=ts_str,
                symbol=self.symbol,
            )
        except ValueError:
            # Schema mismatch or invalid data -> hold
            return None

        p_up = pred.probability_positive

        # Signal thresholding
        if p_up >= self.buy_threshold:
            return SignalEvent(
                timestamp=ts,
                symbol=self.symbol,
                signal_type=SignalType.BUY,
                strength=p_up,
                metadata={"price": price, "ml_prediction": pred.to_dict()},
            )
        elif p_up <= self.sell_threshold:
            return SignalEvent(
                timestamp=ts,
                symbol=self.symbol,
                signal_type=SignalType.SELL,
                strength=pred.probability_negative,
                metadata={"price": price, "ml_prediction": pred.to_dict()},
            )

        return None

    def reset(self) -> None:
        """Resets any internal runtime state."""
        pass
