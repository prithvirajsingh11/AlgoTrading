"""DecisionProvider interface, JevDecisionProvider implementation, caching, and test mocks."""

from __future__ import annotations
from abc import ABC, abstractmethod
import hashlib
import json
import time
from typing import Dict, Any, Optional, List, Union

from backend.app.ai.jev_schema import JevDecision, JevDecisionType
from backend.app.ai.jev_client import JevClient
from backend.app.ai.jev_context import compute_context_hash


class DecisionProvider(ABC):
    """Abstract interface for algorithmic trading decision providers."""

    @abstractmethod
    def evaluate(self, context: Dict[str, Any], config_hash: str = "") -> JevDecision:
        """Evaluates supplied market context and produces a structured decision."""
        pass


class DecisionCache:
    """Thread-safe in-memory decision cache for reproducible backtesting experiments."""

    def __init__(self):
        self._cache: Dict[str, JevDecision] = {}

    @staticmethod
    def make_key(config_hash: str, model: str, timestamp: str, symbol: str, context_hash: str) -> str:
        raw_key = f"{config_hash}_{model}_{timestamp}_{symbol}_{context_hash}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[JevDecision]:
        cached = self._cache.get(key)
        if cached is not None:
            # Return copy with source marked as CACHED_JEV
            d_dict = cached.to_dict()
            d_dict["source"] = "CACHED_JEV"
            return JevDecision.from_dict(d_dict)
        return None

    def set(self, key: str, decision: JevDecision) -> None:
        self._cache[key] = decision

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


class JevDecisionProvider(DecisionProvider):
    """Production decision provider delegating to TypeSafe SystemOne Jev."""

    def __init__(
        self,
        client: Optional[JevClient] = None,
        min_confidence: float = 0.60,
        cache: Optional[DecisionCache] = None,
        cache_enabled: bool = True,
        model: str = "jev-latest",
    ):
        self.client = client or JevClient(model=model)
        self.min_confidence = min_confidence
        self.cache = cache if cache is not None else (DecisionCache() if cache_enabled else None)
        self.cache_enabled = cache_enabled
        self.model = model

    def evaluate(self, context: Dict[str, Any], config_hash: str = "") -> JevDecision:
        timestamp = str(context.get("timestamp", ""))
        symbol = str(context.get("symbol", ""))
        context_hash = compute_context_hash(context)

        # Check cache if enabled
        cache_key = None
        if self.cache_enabled and self.cache is not None:
            cache_key = self.cache.make_key(
                config_hash=config_hash,
                model=self.model,
                timestamp=timestamp,
                symbol=symbol,
                context_hash=context_hash,
            )
            cached_decision = self.cache.get(cache_key)
            if cached_decision is not None:
                return cached_decision

        # Query live Jev client
        decision = self.client.evaluate_state(
            state=context,
            timestamp=timestamp,
            model=self.model,
        )

        # Apply confidence policy
        if decision.decision in (JevDecisionType.BUY, JevDecisionType.SELL):
            if decision.confidence < self.min_confidence:
                # Demote low-confidence actionable decisions to HOLD
                demoted = JevDecision(
                    decision=JevDecisionType.HOLD,
                    confidence=decision.confidence,
                    probabilities=decision.probabilities,
                    model=decision.model,
                    timestamp=decision.timestamp,
                    request_metadata={
                        **decision.request_metadata,
                        "confidence_filter": f"Original {decision.decision.value} demoted to HOLD (confidence {decision.confidence:.4f} < min {self.min_confidence})",
                    },
                    latency_ms=decision.latency_ms,
                    context_hash=context_hash,
                    source=decision.source,
                    error=decision.error,
                )
                decision = demoted

        # Cache valid decisions
        if self.cache_enabled and self.cache is not None and cache_key is not None:
            self.cache.set(cache_key, decision)

        return decision


class MockDecisionProvider(DecisionProvider):
    """Deterministic mock provider for offline tests and simulations."""

    def __init__(
        self,
        default_decision: JevDecisionType = JevDecisionType.BUY,
        confidence: float = 0.85,
        probabilities: Optional[Dict[str, float]] = None,
        latency_ms: float = 12.0,
        model: str = "mock-jev",
        fail_with_error: Optional[str] = None,
    ):
        self.default_decision = default_decision
        self.confidence = confidence
        self.probabilities = probabilities or {"BUY": 0.85, "SELL": 0.10, "HOLD": 0.05}
        self.latency_ms = latency_ms
        self.model = model
        self.fail_with_error = fail_with_error
        self.call_count = 0
        self.recorded_contexts: List[Dict[str, Any]] = []

    def evaluate(self, context: Dict[str, Any], config_hash: str = "") -> JevDecision:
        self.call_count += 1
        self.recorded_contexts.append(context)
        timestamp = str(context.get("timestamp", ""))
        context_hash = compute_context_hash(context)

        if self.fail_with_error:
            return JevDecision.fallback(
                error=self.fail_with_error,
                timestamp=timestamp,
                model=self.model,
                context_hash=context_hash,
                source="MOCK",
                latency_ms=self.latency_ms,
            )

        return JevDecision(
            decision=self.default_decision,
            confidence=self.confidence,
            probabilities=self.probabilities,
            model=self.model,
            timestamp=timestamp,
            request_metadata={"mock": True},
            latency_ms=self.latency_ms,
            context_hash=context_hash,
            source="MOCK",
            error=None,
        )
