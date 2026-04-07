"""
CARE — Curvature-Aware Risk Engine

Keeps infrastructure inside a safe attractor by computing curvature
on system-state risk surfaces and recommending membrane-level interventions.

Theoretical basis: Unified Attractor Grammar (Byte, 2026)
  Theorem 3 → Hessian eigenstructure = local flow geometry
  Theorem 4 → Min |λ_min| on ∂B = minimum-action escape route

Stack: hcderiv (exact Hessians) + curvopt (CAO) + Constitutional OS (membranes)
"""

__version__ = "0.2.0"
__author__ = "Zetta Byte"
__doi__ = "10.5281/zenodo.19394700"
