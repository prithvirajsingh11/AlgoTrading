"""FastAPI REST endpoints for AI decision layer (Phase 8.1)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

from backend.app.core.config import settings
from backend.app.ai.jev_client import JevClient
from backend.app.ai.jev_decision import JevDecisionProvider, DecisionProvider
from backend.app.ai.jev_schema import JevDecision

router = APIRouter(prefix="/ai/jev", tags=["ai"])

# Global provider instance (can be swapped in tests)
_active_provider: Optional[DecisionProvider] = None


def get_decision_provider() -> DecisionProvider:
    global _active_provider
    if _active_provider is not None:
        return _active_provider

    client = JevClient(
        api_key=settings.jev_api_key,
        model=settings.jev_model,
        api_url=settings.jev_api_url,
        timeout_seconds=settings.jev_timeout_seconds,
    )
    _active_provider = JevDecisionProvider(
        client=client,
        min_confidence=settings.jev_min_confidence,
        cache_enabled=True,
        model=settings.jev_model,
    )
    return _active_provider


def set_decision_provider(provider: Optional[DecisionProvider]) -> None:
    global _active_provider
    _active_provider = provider


class JevStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    model: str
    provider_status: str
    timeout_seconds: float
    min_confidence: float


class JevEvaluateRequest(BaseModel):
    context: Dict[str, Any] = Field(..., description="Validated market context dictionary")
    config_hash: Optional[str] = Field("", description="Optional experiment config hash for cache lookup")


@router.get("/status", response_model=JevStatusResponse)
def get_jev_status() -> JevStatusResponse:
    """Returns Jev AI operational status without exposing sensitive credentials."""
    is_configured = bool(settings.jev_api_key and settings.jev_api_key.strip())
    status_str = "ready" if (settings.jev_enabled and is_configured) else ("unconfigured" if not is_configured else "disabled")

    return JevStatusResponse(
        enabled=settings.jev_enabled,
        configured=is_configured,
        model=settings.jev_model,
        provider_status=status_str,
        timeout_seconds=settings.jev_timeout_seconds,
        min_confidence=settings.jev_min_confidence,
    )


@router.post("/evaluate")
def evaluate_context(request: JevEvaluateRequest) -> Dict[str, Any]:
    """Evaluates a validated market context and produces a structured Jev decision."""
    if not request.context:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Market context cannot be empty")

    provider = get_decision_provider()
    decision = provider.evaluate(context=request.context, config_hash=request.config_hash or "")
    return decision.to_dict()
