"""
Pydantic v2 schemas for CARE API request/response types.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class StateInput(BaseModel):
    """Raw infrastructure state submitted to any CARE endpoint."""
    state: Any = Field(..., description="Any JSON-serialisable infra state")
    potential: str = Field(
        "quadratic",
        description="Risk potential to use: 'quadratic' | 'privilege' | 'blast_radius'",
    )
    backend: str | None = Field(
        None,
        description="Curvature backend override: 'numpy' | 'jax' | 'jax-xla'",
    )


# ── Responses ─────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class EncodeResponse(BaseModel):
    vector: list[float]
    dim: int


class RiskResponse(BaseModel):
    risk: float
    severity_hint: str    # "low" | "medium" | "high"


class CurvatureResponse(BaseModel):
    risk: float
    gradient: list[float]
    hessian: list[list[float]]
    eigenvalues: list[float]
    backend_used: str


class EscapeRouteResponse(BaseModel):
    softest_eigenvalue: float
    softest_eigenvector: list[float]
    stiffest_eigenvalue: float
    negative_eigenvalues: list[float]
    n_negative_directions: int
    escape_direction: list[float]
    kramers_escape_proxy: float
    severity: str


class Action(BaseModel):
    action_type: str
    target: str
    from_state: str
    to_state: str
    reason: str
    priority: int
    uag_link: str
    metadata: dict[str, Any]


class RecommendResponse(BaseModel):
    actions: list[Action]
    n_actions: int
    severity: str


class ApplyResponse(BaseModel):
    status: Literal["accepted", "rejected", "dry_run"]
    delta_ids: list[str]
    message: str
