"""TypeSafe SystemOne Jev decision schemas and typed models."""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
import json


class JevDecisionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_ACTION = "NO_ACTION"


@dataclass
class JevQuestionChoice:
    type: str = "choice"
    instructions: str = "Given the supplied market state, which trading action is most appropriate?"
    criteria: Dict[str, str] = field(default_factory=lambda: {
        "BUY": "Conditions favor taking or increasing a long exposure",
        "SELL": "Conditions favor reducing or taking short exposure",
        "HOLD": "Conditions do not justify changing exposure",
    })


@dataclass
class JevDecisionRequest:
    model: str
    state: str
    questions: Dict[str, Any]

    @classmethod
    def create(cls, state: str, model: str = "jev-latest") -> JevDecisionRequest:
        choice_question = JevQuestionChoice()
        return cls(
            model=model,
            state=state,
            questions={
                "trading_action": {
                    "type": choice_question.type,
                    "instructions": choice_question.instructions,
                    "criteria": choice_question.criteria,
                }
            },
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "state": self.state,
            "questions": self.questions,
        }


@dataclass
class JevDecision:
    """Strongly typed decision result returned from Jev decision evaluation."""

    decision: JevDecisionType
    confidence: float
    probabilities: Dict[str, float]
    model: str
    timestamp: str
    request_metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    context_hash: str = ""
    source: str = "LIVE_JEV"  # "LIVE_JEV", "CACHED_JEV", "MOCK", "FALLBACK"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value if isinstance(self.decision, JevDecisionType) else str(self.decision),
            "confidence": round(float(self.confidence), 4),
            "probabilities": {k: round(float(v), 4) for k, v in self.probabilities.items()},
            "model": self.model,
            "timestamp": self.timestamp,
            "request_metadata": self.request_metadata,
            "latency_ms": round(float(self.latency_ms), 2),
            "context_hash": self.context_hash,
            "source": self.source,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JevDecision:
        dec_raw = data.get("decision", "NO_ACTION")
        try:
            decision = JevDecisionType(dec_raw)
        except ValueError:
            decision = JevDecisionType.NO_ACTION

        return cls(
            decision=decision,
            confidence=float(data.get("confidence", 0.0)),
            probabilities=dict(data.get("probabilities", {})),
            model=str(data.get("model", "")),
            timestamp=str(data.get("timestamp", "")),
            request_metadata=dict(data.get("request_metadata", {})),
            latency_ms=float(data.get("latency_ms", 0.0)),
            context_hash=str(data.get("context_hash", "")),
            source=str(data.get("source", "LIVE_JEV")),
            error=data.get("error"),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> JevDecision:
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def fallback(
        cls,
        error: str,
        timestamp: str = "",
        model: str = "jev-latest",
        context_hash: str = "",
        source: str = "FALLBACK",
        latency_ms: float = 0.0,
    ) -> JevDecision:
        """Constructs a deterministic safe fallback decision with NO_ACTION."""
        return cls(
            decision=JevDecisionType.NO_ACTION,
            confidence=0.0,
            probabilities={"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0},
            model=model,
            timestamp=timestamp,
            latency_ms=latency_ms,
            context_hash=context_hash,
            source=source,
            error=error,
        )
