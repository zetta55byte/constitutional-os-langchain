"""
Risk Potential Module — R(x): ℝⁿ → ℝ.

The risk potential defines the energy landscape that CARE navigates.
A high value of R(x) indicates a risky system state; the "safe attractor"
is a local minimum of R.

Three built-in potentials are provided:
    "quadratic"   — R(x) = ||x||²                       (debug / baseline)
    "privilege"   — weights first k dimensions higher    (IAM hardening)
    "blast_radius"— asymmetric: off-diagonal coupling    (network segmentation)

Swap in your own by subclassing RiskPotential or passing a callable.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)


# ── Abstract base ─────────────────────────────────────────────────────────────

class RiskPotential(ABC):
    """Abstract risk potential. Subclass and implement __call__."""

    @abstractmethod
    def __call__(self, x: np.ndarray) -> float:
        ...

    def name(self) -> str:
        return self.__class__.__name__


# ── Built-in potentials ───────────────────────────────────────────────────────

class QuadraticRisk(RiskPotential):
    """R(x) = ||x||² — simplest possible potential, Hessian = 2I."""

    def __call__(self, x: np.ndarray) -> float:
        return float(np.dot(x, x))


class PrivilegeRisk(RiskPotential):
    """
    R(x) = w · x² — weighted quadratic, where weights encode privilege levels.

    The first `n_privileged` dimensions are penalised more heavily,
    representing high-privilege accounts or services.
    """

    def __init__(self, n_privileged: int = 4, privilege_weight: float = 5.0):
        self.n_privileged = n_privileged
        self.privilege_weight = privilege_weight

    def __call__(self, x: np.ndarray) -> float:
        w = np.ones_like(x)
        w[:self.n_privileged] = self.privilege_weight
        return float(np.dot(w, x ** 2))


class BlastRadiusRisk(RiskPotential):
    """
    R(x) = x^T A x + b^T x — quadratic form with coupling matrix A.

    A represents connectivity: high off-diagonal entries = high blast radius
    if one component is compromised.
    Positive definiteness guaranteed by A = W^T W + ε I.
    """

    def __init__(self, coupling_scale: float = 0.3, seed: int = 42):
        self._coupling_scale = coupling_scale
        self._seed = seed
        self._A_cache: dict[int, np.ndarray] = {}

    def _A(self, n: int) -> np.ndarray:
        if n not in self._A_cache:
            rng = np.random.default_rng(self._seed)
            W = rng.standard_normal((n, n)) * self._coupling_scale
            self._A_cache[n] = W.T @ W + np.eye(n) * 0.1
        return self._A_cache[n]

    def __call__(self, x: np.ndarray) -> float:
        A = self._A(len(x))
        return float(x @ A @ x)


# ── Registry and factory ──────────────────────────────────────────────────────

_REGISTRY: dict[str, RiskPotential] = {
    "quadratic":    QuadraticRisk(),
    "privilege":    PrivilegeRisk(),
    "blast_radius": BlastRadiusRisk(),
}


def get_potential(name: str = "quadratic") -> RiskPotential:
    """Return a named built-in risk potential."""
    if name not in _REGISTRY:
        raise ValueError(f"Unknown risk potential '{name}'. Choose from: {list(_REGISTRY)}")
    return _REGISTRY[name]


def register_potential(name: str, potential: RiskPotential | Callable) -> None:
    """Register a custom risk potential under a given name."""
    if callable(potential) and not isinstance(potential, RiskPotential):
        class _Wrapped(RiskPotential):
            def __call__(self, x):
                return float(potential(x))
        _REGISTRY[name] = _Wrapped()
    else:
        _REGISTRY[name] = potential  # type: ignore[assignment]
    logger.info("Registered custom risk potential '%s'.", name)


# ── Convenience function ──────────────────────────────────────────────────────

def risk_potential(x: np.ndarray, potential_name: str = "quadratic") -> float:
    """Evaluate the named risk potential at state vector x."""
    return get_potential(potential_name)(x)
