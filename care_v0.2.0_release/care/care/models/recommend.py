"""
Hardening Recommendation Engine.

Maps curvature analysis → concrete, actionable hardening moves.
These moves are designed to:
  - increase |λ_min| along soft directions  (deepen the safe basin)
  - reduce the Kramers escape proxy         (raise ridge height)
  - enforce Constitutional OS membranes     (block known escape paths)

Action types (extensible):
    reduce_privilege   — remove or downscope an IAM permission
    segment_network    — add a firewall rule or subnet boundary
    rate_limit         — add rate limiting on an API endpoint or model
    add_mfa            — enforce MFA on a user or service account
    disable_capability — restrict a model capability mode
    rotate_credential  — rotate a key/secret before it drifts
    quarantine         — isolate a component pending investigation

Each action carries:
    type, target, from_state, to_state, reason, priority, uag_link
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from care.models.curvature import CurvatureResult
from care.models.ridge import RidgeAnalysis
from care.config import settings

logger = logging.getLogger(__name__)


# ── Action data type ──────────────────────────────────────────────────────────

@dataclass
class HardeningAction:
    action_type: str
    target: str
    from_state: str
    to_state: str
    reason: str
    priority: int                    # 1 = highest
    uag_link: str = ""               # which UAG theorem motivates this
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "reason": self.reason,
            "priority": self.priority,
            "uag_link": self.uag_link,
            "metadata": self.metadata,
        }


# ── Recommendation logic ──────────────────────────────────────────────────────

def recommend_actions(
    result: CurvatureResult,
    ridge: RidgeAnalysis,
    raw_state: Any = None,
) -> list[HardeningAction]:
    """
    Generate prioritised hardening actions from curvature analysis.

    Rule set (applied in order):
    1. Critical severity → immediate quarantine / disable
    2. Negative eigenvalues → the system is already on or past the ridge
    3. Soft direction in first k dimensions → privilege reduction (IAM)
    4. High gradient component → rate-limiting / MFA
    5. High overall risk → general hardening recommendations

    Parameters
    ----------
    result:
        CurvatureResult from curvature_info().
    ridge:
        RidgeAnalysis from analyse_ridge().
    raw_state:
        Original raw state dict (used for target labelling if available).

    Returns
    -------
    List of HardeningAction, sorted by priority (ascending = most urgent first).
    """
    actions: list[HardeningAction] = []
    x = result.x
    vals = result.eigenvalues
    grad = result.gradient
    lam_soft = ridge.softest_eigenvalue
    abs_lam_soft = abs(lam_soft)

    # ── Rule 1: Critical severity → quarantine ────────────────────────────────
    if ridge.severity == "critical":
        actions.append(HardeningAction(
            action_type="quarantine",
            target="system",
            from_state="operational",
            to_state="isolated",
            reason=(
                f"Curvature magnitude |λ_min| = {abs_lam_soft:.4f} is critically low "
                f"({ridge.n_negative} negative eigenvalues detected). "
                "System is near or past a basin boundary."
            ),
            priority=1,
            uag_link="UAG Theorem 4: minimal |λ_min| on ∂B maximises escape probability",
        ))

    # ── Rule 2: Negative eigenvalues → immediate containment ─────────────────
    for lam in ridge.negative_eigenvalues:
        actions.append(HardeningAction(
            action_type="segment_network",
            target="boundary",
            from_state="open",
            to_state="segmented",
            reason=(
                f"Negative eigenvalue λ = {lam:.4f} indicates an unstable direction. "
                "Adding network segmentation to block this escape route."
            ),
            priority=1,
            uag_link="UAG Theorem 3: negative eigenvalue = unstable flow direction",
        ))

    # ── Rule 3: Soft direction in high-risk dimensions → reduce privilege ─────
    soft_dim = ridge.softest_index
    if abs_lam_soft < settings.soft_lambda_threshold:
        target_label = _label_dim(soft_dim, raw_state)
        actions.append(HardeningAction(
            action_type="reduce_privilege",
            target=target_label,
            from_state="elevated",
            to_state="least_privilege",
            reason=(
                f"Dimension {soft_dim} ({target_label}) is the softest direction "
                f"(λ = {lam_soft:.4f}). Privilege reduction increases curvature "
                "along this axis, deepening the safe basin."
            ),
            priority=2,
            uag_link="UAG Theorem 4: increasing |λ_min| raises the basin ridge",
        ))

    # ── Rule 4: High gradient components → rate-limit ────────────────────────
    grad_norm = np.linalg.norm(grad)
    if grad_norm > 0:
        hot_dim = int(np.argmax(np.abs(grad)))
        hot_grad = float(grad[hot_dim])
        if abs(hot_grad) > 0.5 * grad_norm:
            actions.append(HardeningAction(
                action_type="rate_limit",
                target=_label_dim(hot_dim, raw_state),
                from_state="unlimited",
                to_state="rate_limited",
                reason=(
                    f"Dimension {hot_dim} has the largest gradient component "
                    f"(∂R/∂x_{hot_dim} = {hot_grad:.3f}). "
                    "Rate-limiting reduces drift velocity in this direction."
                ),
                priority=3,
                uag_link="UAG Section 3.3: feedback sensitivity → gradient-driven flow",
            ))

    # ── Rule 5: MFA if risk is high ───────────────────────────────────────────
    if result.risk > settings.high_risk_threshold:
        actions.append(HardeningAction(
            action_type="add_mfa",
            target="all_privileged_accounts",
            from_state="password_only",
            to_state="mfa_required",
            reason=(
                f"Overall risk R(x) = {result.risk:.2f} exceeds threshold "
                f"{settings.high_risk_threshold}. MFA raises the effective "
                "ridge height for human-in-the-loop actions."
            ),
            priority=4,
            uag_link="UAG: boundary integrity — raising ridge height stabilises the basin",
        ))

    # Sort by priority
    actions.sort(key=lambda a: a.priority)

    if not actions:
        logger.info("No hardening actions required (severity='%s').", ridge.severity)
    else:
        logger.info(
            "Generated %d hardening action(s) (severity='%s').",
            len(actions), ridge.severity,
        )

    return actions


def _label_dim(dim: int, raw_state: Any) -> str:
    """Best-effort label for a state dimension given the raw state."""
    if isinstance(raw_state, dict):
        keys = sorted(raw_state.keys())
        if dim < len(keys):
            return str(keys[dim])
    return f"dim_{dim}"
