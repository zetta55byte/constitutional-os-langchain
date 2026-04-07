"""
Ridge & Escape Route Detector.

Implements the UAG Theorem 4 prediction:
    Noise-driven transitions escape saddle points at locations of
    minimal curvature magnitude — the minimum-|λ_min| point on ∂B.

Given the Hessian eigenstructure at the current state x, this module:
  1. Identifies the softest direction (min |λ_i|) — the "easiest escape route"
  2. Approximates the minimum-action escape path direction
  3. Computes a local Kramers-rate proxy for each eigendirection
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from care.models.curvature import CurvatureResult

logger = logging.getLogger(__name__)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class RidgeAnalysis:
    """Ridge geometry analysis at the current state."""
    softest_eigenvalue: float            # λ with smallest |λ|
    softest_eigenvector: np.ndarray      # corresponding direction
    softest_index: int                   # index in eigenvalue array

    stiffest_eigenvalue: float           # λ with largest |λ|
    stiffest_eigenvector: np.ndarray

    negative_eigenvalues: list[float]    # unstable directions
    n_negative: int                      # count of λ < 0

    escape_direction: np.ndarray         # unit vector of most likely escape
    kramers_proxy: float                 # ∝ exp(-ΔR / |λ_min|): higher = easier escape

    # Human-readable severity
    severity: str                        # "safe" | "watch" | "critical"


# ── Core analysis ─────────────────────────────────────────────────────────────

_SOFT_THRESHOLD = 0.5      # |λ| below this is considered "soft"
_CRITICAL_THRESHOLD = 0.1  # |λ| below this is "critical"


def analyse_ridge(result: CurvatureResult, delta_risk: float = 1.0) -> RidgeAnalysis:
    """
    Analyse ridge geometry from a CurvatureResult.

    Parameters
    ----------
    result:
        Output of curvature_info().
    delta_risk:
        ΔR = R(x*) - R(A*): energy difference to the ridge crest.
        Used for Kramers proxy. Defaults to 1.0 (relative units).

    Returns
    -------
    RidgeAnalysis with soft/stiff directions, escape route, and severity.
    """
    vals = result.eigenvalues        # ascending, shape (n,)
    vecs = result.eigenvectors       # columns = eigenvectors

    # Softest direction: min |λ|
    abs_vals = np.abs(vals)
    soft_idx = int(np.argmin(abs_vals))
    soft_val = float(vals[soft_idx])
    soft_vec = vecs[:, soft_idx].copy()

    # Stiffest direction: max |λ|
    stiff_idx = int(np.argmax(abs_vals))
    stiff_val = float(vals[stiff_idx])
    stiff_vec = vecs[:, stiff_idx].copy()

    # Negative eigenvalues (unstable directions)
    neg_vals = [float(v) for v in vals if v < 0]

    # Escape direction: align with softest; if negative, it IS the escape
    # If all positive (pure attractor basin), escape = softest direction
    escape_idx = int(np.argmin(vals))   # most negative or least positive
    escape_dir = vecs[:, escape_idx].copy()
    escape_dir /= np.linalg.norm(escape_dir) + 1e-12

    # Kramers-rate proxy (Eq. A11 in UAG):
    #   S(γ*) ≈ 2 * ΔR / |λ_min|
    # Escape probability ∝ exp(-S/ε) ∝ exp(-2ΔR / (ε * |λ_min|))
    # Here we return a normalised proxy in [0, 1]: higher = easier escape
    kramers = float(np.exp(-2.0 * delta_risk / (abs_vals[soft_idx] + 1e-6)))

    # Severity classification
    min_abs = abs_vals[soft_idx]
    if min_abs < _CRITICAL_THRESHOLD or len(neg_vals) > 0:
        severity = "critical"
    elif min_abs < _SOFT_THRESHOLD:
        severity = "watch"
    else:
        severity = "safe"

    logger.debug(
        "Ridge: soft λ=%.4f  escape_prob≈%.3f  severity=%s  n_neg=%d",
        soft_val, kramers, severity, len(neg_vals),
    )

    return RidgeAnalysis(
        softest_eigenvalue=soft_val,
        softest_eigenvector=soft_vec,
        softest_index=soft_idx,
        stiffest_eigenvalue=stiff_val,
        stiffest_eigenvector=stiff_vec,
        negative_eigenvalues=neg_vals,
        n_negative=len(neg_vals),
        escape_direction=escape_dir,
        kramers_proxy=kramers,
        severity=severity,
    )


def summarise(ridge: RidgeAnalysis) -> dict:
    """JSON-serialisable summary for the API layer."""
    return {
        "softest_eigenvalue": ridge.softest_eigenvalue,
        "softest_eigenvector": ridge.softest_eigenvector.tolist(),
        "stiffest_eigenvalue": ridge.stiffest_eigenvalue,
        "negative_eigenvalues": ridge.negative_eigenvalues,
        "n_negative_directions": ridge.n_negative,
        "escape_direction": ridge.escape_direction.tolist(),
        "kramers_escape_proxy": ridge.kramers_proxy,
        "severity": ridge.severity,
    }
