"""
CARE configuration — loaded from environment or .env file.
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        level=getattr(logging, level.upper(), logging.INFO),
    )

setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("care")


# ── Settings ─────────────────────────────────────────────────────────────────

@dataclass
class CareSettings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("CARE_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("CARE_PORT", "8000")))
    reload: bool = field(default_factory=lambda: os.getenv("CARE_RELOAD", "false").lower() == "true")

    # Curvature backend: "numpy" | "jax" | "jax-xla"
    curvature_backend: str = field(
        default_factory=lambda: os.getenv("CARE_CURVATURE_BACKEND", "numpy")
    )

    # Constitutional OS
    cos_endpoint: str = field(
        default_factory=lambda: os.getenv("CARE_COS_ENDPOINT", "http://localhost:9000")
    )
    cos_enabled: bool = field(
        default_factory=lambda: os.getenv("CARE_COS_ENABLED", "false").lower() == "true"
    )

    # Risk thresholds
    soft_lambda_threshold: float = field(
        default_factory=lambda: float(os.getenv("CARE_SOFT_LAMBDA", "1.0"))
    )
    high_risk_threshold: float = field(
        default_factory=lambda: float(os.getenv("CARE_HIGH_RISK", "10.0"))
    )

    # Encoder state dimension cap (for safety)
    max_state_dim: int = field(
        default_factory=lambda: int(os.getenv("CARE_MAX_STATE_DIM", "512"))
    )


settings = CareSettings()
