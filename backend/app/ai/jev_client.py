"""TypeSafe SystemOne Jev API Client.

Direct HTTP client for POST https://api.typesafe.ai/v1/systemone.
Provides deterministic request serialization, safe error handling,
and graceful fallback to NO_ACTION on network or parsing failure.
"""

from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
import logging
from typing import Dict, Any, Optional

from backend.app.ai.jev_schema import (
    JevDecision,
    JevDecisionType,
    JevDecisionRequest,
)
from backend.app.ai.jev_context import compute_context_hash

logger = logging.getLogger(__name__)


class JevClient:
    """HTTP client for TypeSafe SystemOne Jev decision API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "jev-latest",
        api_url: str = "https://api.typesafe.ai/v1/systemone",
        timeout_seconds: float = 5.0,
    ):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def evaluate_state(
        self,
        state: Union[str, Dict[str, Any]],
        timestamp: str = "",
        model: Optional[str] = None,
    ) -> JevDecision:
        """Sends decision request to TypeSafe SystemOne endpoint.
        
        Guaranteed to never raise uncaught exceptions to the caller;
        fails safe with JevDecisionType.NO_ACTION on any error.
        """
        active_model = model or self.model
        t_start = time.perf_counter()

        if isinstance(state, dict):
            context_hash = compute_context_hash(state)
            state_str = json.dumps(state, sort_keys=True, separators=(",", ":"))
        else:
            state_str = str(state)
            import hashlib
            context_hash = hashlib.sha256(state_str.encode("utf-8")).hexdigest()

        if not self.is_configured:
            latency_ms = (time.perf_counter() - t_start) * 1000
            return JevDecision.fallback(
                error="JEV_API_KEY is not configured",
                timestamp=timestamp,
                model=active_model,
                context_hash=context_hash,
                source="FALLBACK",
                latency_ms=latency_ms,
            )

        req_payload = JevDecisionRequest.create(state=state_str, model=active_model)
        payload_bytes = json.dumps(req_payload.to_dict()).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "AlgoTrade-Research/1.0",
        }

        req = urllib.request.Request(
            url=self.api_url,
            data=payload_bytes,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                status_code = response.getcode()
                body = response.read().decode("utf-8")
                latency_ms = (time.perf_counter() - t_start) * 1000

                if status_code != 200:
                    logger.warning("Jev API returned HTTP %s: %s", status_code, body)
                    return JevDecision.fallback(
                        error=f"HTTP {status_code}: {body}",
                        timestamp=timestamp,
                        model=active_model,
                        context_hash=context_hash,
                        source="FALLBACK",
                        latency_ms=latency_ms,
                    )

                data = json.loads(body)
                return self._parse_response(
                    data=data,
                    timestamp=timestamp,
                    model=active_model,
                    context_hash=context_hash,
                    latency_ms=latency_ms,
                )

        except urllib.error.HTTPError as e:
            latency_ms = (time.perf_counter() - t_start) * 1000
            err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            logger.error("Jev HTTP error %s: %s", e.code, err_body)
            return JevDecision.fallback(
                error=f"HTTPError {e.code}: {err_body}",
                timestamp=timestamp,
                model=active_model,
                context_hash=context_hash,
                source="FALLBACK",
                latency_ms=latency_ms,
            )
        except urllib.error.URLError as e:
            latency_ms = (time.perf_counter() - t_start) * 1000
            logger.error("Jev network error: %s", str(e.reason))
            return JevDecision.fallback(
                error=f"URLError: {str(e.reason)}",
                timestamp=timestamp,
                model=active_model,
                context_hash=context_hash,
                source="FALLBACK",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t_start) * 1000
            logger.exception("Unexpected error querying Jev API: %s", str(e))
            return JevDecision.fallback(
                error=f"UnexpectedException: {str(e)}",
                timestamp=timestamp,
                model=active_model,
                context_hash=context_hash,
                source="FALLBACK",
                latency_ms=latency_ms,
            )

    def _parse_response(
        self,
        data: Dict[str, Any],
        timestamp: str,
        model: str,
        context_hash: str,
        latency_ms: float,
    ) -> JevDecision:
        """Parses TypeSafe SystemOne response into strongly-typed JevDecision."""
        try:
            # Handle possible response wrappers
            action_data: Optional[Dict[str, Any]] = None
            if "questions" in data and "trading_action" in data["questions"]:
                action_data = data["questions"]["trading_action"]
            elif "trading_action" in data:
                action_data = data["trading_action"]
            elif "choice" in data:
                action_data = data

            if not action_data or not isinstance(action_data, dict):
                return JevDecision.fallback(
                    error="Malformed response: missing 'trading_action' choice",
                    timestamp=timestamp,
                    model=model,
                    context_hash=context_hash,
                    latency_ms=latency_ms,
                )

            choice_str = str(action_data.get("choice", "")).upper()
            confidence = float(action_data.get("confidence", 0.0))
            raw_probs = action_data.get("probabilities", {})

            # Standardize probabilities dict
            probabilities: Dict[str, float] = {
                "BUY": float(raw_probs.get("BUY", 0.0)),
                "SELL": float(raw_probs.get("SELL", 0.0)),
                "HOLD": float(raw_probs.get("HOLD", 0.0)),
            }

            try:
                decision_type = JevDecisionType(choice_str)
            except ValueError:
                decision_type = JevDecisionType.NO_ACTION

            return JevDecision(
                decision=decision_type,
                confidence=confidence,
                probabilities=probabilities,
                model=model,
                timestamp=timestamp,
                request_metadata=action_data,
                latency_ms=latency_ms,
                context_hash=context_hash,
                source="LIVE_JEV",
                error=None,
            )

        except Exception as e:
            return JevDecision.fallback(
                error=f"ParsingException: {str(e)}",
                timestamp=timestamp,
                model=model,
                context_hash=context_hash,
                latency_ms=latency_ms,
            )
