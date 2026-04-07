"""
Curvature Engine — exact ∇R(x) and H(x) = ∇²R(x).

Three backends, selected via settings.curvature_backend:

    "numpy"   — finite differences (always available, O(h²) error)
    "jax"     — forward-over-reverse AD  (requires jax install)
    "jax-xla" — hcderiv one-pass XLA Hessian (requires hcderiv[jax]>=0.4.0)

The public API is identical regardless of backend:
    compute_gradient(x, potential) -> np.ndarray
    compute_hessian(x, potential)  -> np.ndarray
    curvature_info(x, potential)   -> CurvatureResult
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.linalg import eigh

from care.config import settings

logger = logging.getLogger(__name__)


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class CurvatureResult:
    """Full curvature analysis at a point x."""
    x: np.ndarray
    risk: float
    gradient: np.ndarray          # shape (n,)
    hessian: np.ndarray           # shape (n, n)
    eigenvalues: np.ndarray       # shape (n,) ascending
    eigenvectors: np.ndarray      # shape (n, n), columns = eigenvectors
    backend_used: str


# ── Finite-difference fallback ────────────────────────────────────────────────

def _gradient_fd(f: Callable, x: np.ndarray, h: float = 1e-5) -> np.ndarray:
    grad = np.zeros_like(x)
    for i in range(len(x)):
        xp, xm = x.copy(), x.copy()
        xp[i] += h;  xm[i] -= h
        grad[i] = (f(xp) - f(xm)) / (2 * h)
    return grad


def _hessian_fd(f: Callable, x: np.ndarray, h: float = 1e-4) -> np.ndarray:
    n = len(x)
    H = np.zeros((n, n))
    f0 = f(x)
    for i in range(n):
        for j in range(i, n):
            xpp = x.copy(); xpp[i] += h; xpp[j] += h
            xpm = x.copy(); xpm[i] += h; xpm[j] -= h
            xmp = x.copy(); xmp[i] -= h; xmp[j] += h
            xmm = x.copy(); xmm[i] -= h; xmm[j] -= h
            H[i, j] = (f(xpp) - f(xpm) - f(xmp) + f(xmm)) / (4 * h * h)
            H[j, i] = H[i, j]
    return H


# ── JAX backend ───────────────────────────────────────────────────────────────

def _try_jax_hessian(f: Callable, x: np.ndarray, xla: bool = False) -> np.ndarray | None:
    try:
        import jax
        import jax.numpy as jnp
        jx = jnp.array(x)
        if xla:
            try:
                import hcderiv
                H = hcderiv.hessian(f, x, backend="jax-xla")
                return np.array(H)
            except ImportError:
                logger.warning("hcderiv not installed; falling back to JAX AD.")
        H_fn = jax.hessian(lambda v: f(np.array(v)))
        return np.array(H_fn(jx))
    except ImportError:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def compute_gradient(
    x: np.ndarray,
    potential: Callable,
    backend: str | None = None,
) -> np.ndarray:
    """Compute ∇R(x)."""
    b = backend or settings.curvature_backend
    if b in ("jax", "jax-xla"):
        try:
            import jax
            import jax.numpy as jnp
            g = jax.grad(lambda v: potential(np.array(v)))(jnp.array(x))
            return np.array(g)
        except (ImportError, Exception) as e:
            logger.warning("JAX gradient failed (%s); using finite differences.", e)
    return _gradient_fd(potential, x)


def compute_hessian(
    x: np.ndarray,
    potential: Callable,
    backend: str | None = None,
) -> np.ndarray:
    """Compute H(x) = ∇²R(x)."""
    b = backend or settings.curvature_backend
    if b == "jax-xla":
        H = _try_jax_hessian(potential, x, xla=True)
        if H is not None:
            return H
    if b in ("jax", "jax-xla"):
        H = _try_jax_hessian(potential, x, xla=False)
        if H is not None:
            return H
    logger.debug("Using finite-difference Hessian (backend='%s').", b)
    return _hessian_fd(potential, x)


def curvature_info(
    x: np.ndarray,
    potential: Callable,
    backend: str | None = None,
) -> CurvatureResult:
    """
    Full curvature analysis: risk, gradient, Hessian, eigendecomposition.

    This is the main entry point for the CARE risk pipeline.
    Corresponds to Theorem 3 of the UAG: eigenvalues determine stability,
    stiffness, and flow direction at every point in state space.
    """
    b = backend or settings.curvature_backend
    r = float(potential(x))
    grad = compute_gradient(x, potential, backend=b)
    H = compute_hessian(x, potential, backend=b)

    # Enforce symmetry (numerical noise can break it with FD)
    H = (H + H.T) / 2

    # Eigendecomposition — scipy eigh guarantees ascending order for symmetric H
    vals, vecs = eigh(H)

    return CurvatureResult(
        x=x,
        risk=r,
        gradient=grad,
        hessian=H,
        eigenvalues=vals,
        eigenvectors=vecs,
        backend_used=b,
    )
