"""
CARE visualisation — curvature spectra, risk basins, before/after comparisons.

All plots return matplotlib Figure objects so they can be saved, displayed
in notebooks, or embedded in the web UI.

Key plots:
    eigenvalue_spectrum(result)    — bar chart of λᵢ, coloured by stability
    risk_over_time(history)        — line chart of R(x) across snapshots
    curvature_basin_2d(potential)  — 2D contour of R over a grid
    before_after(before, after)    — side-by-side eigenvalue comparison
"""
from __future__ import annotations

import logging
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

# Lazy import matplotlib so the package works without it
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    _MPL_AVAILABLE = True
except ImportError:
    _MPL_AVAILABLE = False
    logger.warning("matplotlib not installed; visualisations unavailable.")


def _require_mpl():
    if not _MPL_AVAILABLE:
        raise ImportError("Install matplotlib to use CARE visualisations: pip install matplotlib")


# ── Colour helpers ────────────────────────────────────────────────────────────

_SAFE_COLOR     = "#1D9E75"   # teal  — positive eigenvalue
_SOFT_COLOR     = "#E07B00"   # amber — small |λ|
_UNSTABLE_COLOR = "#C0392B"   # red   — negative eigenvalue


def _eigenvalue_color(lam: float, threshold: float = 0.5) -> str:
    if lam < 0:
        return _UNSTABLE_COLOR
    if abs(lam) < threshold:
        return _SOFT_COLOR
    return _SAFE_COLOR


# ── Plots ─────────────────────────────────────────────────────────────────────

def eigenvalue_spectrum(
    eigenvalues: Sequence[float],
    title: str = "Curvature eigenvalue spectrum",
    threshold: float = 0.5,
) -> "Figure":
    """
    Bar chart of Hessian eigenvalues.
    Green = stable, amber = soft (potential escape), red = unstable.
    """
    _require_mpl()
    vals = list(eigenvalues)
    n = len(vals)
    colors = [_eigenvalue_color(v, threshold) for v in vals]

    fig, ax = plt.subplots(figsize=(max(4, n * 0.6), 3.2))
    ax.bar(range(n), vals, color=colors, edgecolor="white", linewidth=0.5)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="-")
    ax.axhline(threshold, color=_SOFT_COLOR, linewidth=0.8,
               linestyle="--", label=f"|λ| = {threshold} threshold")
    ax.axhline(-threshold, color=_SOFT_COLOR, linewidth=0.8, linestyle="--")
    ax.set_xticks(range(n))
    ax.set_xticklabels([f"λ₍{i}₎" for i in range(n)], fontsize=8)
    ax.set_ylabel("Eigenvalue")
    ax.set_title(title, fontsize=9)
    ax.legend(fontsize=7, framealpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend patches
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=_SAFE_COLOR,     label="Stable (λ > threshold)"),
        Patch(facecolor=_SOFT_COLOR,     label="Soft (|λ| < threshold)"),
        Patch(facecolor=_UNSTABLE_COLOR, label="Unstable (λ < 0)"),
    ]
    ax.legend(handles=legend_elements, fontsize=7, loc="upper right", framealpha=0.8)
    fig.tight_layout(pad=0.5)
    return fig


def risk_over_time(
    risks: Sequence[float],
    labels: Sequence[str] | None = None,
    title: str = "Risk R(x) over time",
) -> "Figure":
    """Line chart of risk values across a sequence of snapshots."""
    _require_mpl()
    fig, ax = plt.subplots(figsize=(5, 2.8))
    x = range(len(risks))
    ax.plot(x, risks, color="#1B6CA8", linewidth=1.8, marker="o", ms=4)
    if labels:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.set_ylabel("Risk R(x)")
    ax.set_title(title, fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def curvature_basin_2d(
    potential_fn,
    x_range: tuple[float, float] = (-3, 3),
    y_range: tuple[float, float] = (-3, 3),
    resolution: int = 120,
    title: str = "Risk potential R(x) — 2D slice",
) -> "Figure":
    """
    2D contour plot of the risk potential over a grid.
    Slices dimensions 0 and 1; all other dims held at 0.
    """
    _require_mpl()
    xs = np.linspace(*x_range, resolution)
    ys = np.linspace(*y_range, resolution)
    X, Y = np.meshgrid(xs, ys)
    Z = np.zeros_like(X)
    for i in range(resolution):
        for j in range(resolution):
            v = np.zeros(max(2, 8))
            v[0], v[1] = X[i, j], Y[i, j]
            try:
                Z[i, j] = float(potential_fn(v))
            except Exception:
                Z[i, j] = 0.0

    fig, ax = plt.subplots(figsize=(4.5, 3.8))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("", ["#E1F5EE", "#1B6CA8"])
    cf = ax.contourf(X, Y, Z, levels=20, cmap=cmap, alpha=0.85)
    ax.contour(X, Y, Z, levels=10, colors="white", linewidths=0.3, alpha=0.5)
    fig.colorbar(cf, ax=ax, label="R(x)", shrink=0.85)
    ax.set_xlabel("x₀");  ax.set_ylabel("x₁")
    ax.set_title(title, fontsize=9)
    fig.tight_layout(pad=0.5)
    return fig


def before_after(
    eigenvalues_before: Sequence[float],
    eigenvalues_after: Sequence[float],
    title: str = "Curvature before / after hardening",
) -> "Figure":
    """Side-by-side eigenvalue spectra showing hardening effect."""
    _require_mpl()
    n = max(len(eigenvalues_before), len(eigenvalues_after))
    b = list(eigenvalues_before) + [0.0] * (n - len(eigenvalues_before))
    a = list(eigenvalues_after)  + [0.0] * (n - len(eigenvalues_after))
    x = np.arange(n)
    w = 0.35

    fig, ax = plt.subplots(figsize=(max(4, n * 0.8), 3.2))
    ax.bar(x - w/2, b, w, color="#C0392B", alpha=0.75, label="Before")
    ax.bar(x + w/2, a, w, color="#1D9E75", alpha=0.75, label="After")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"λ₍{i}₎" for i in range(n)], fontsize=8)
    ax.set_ylabel("Eigenvalue")
    ax.set_title(title, fontsize=9)
    ax.legend(fontsize=7, framealpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig
