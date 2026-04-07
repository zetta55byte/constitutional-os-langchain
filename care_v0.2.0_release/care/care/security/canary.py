"""
CARE Canary — CARE watching CARE.

Periodically encodes CARE's own deployment state as a vector,
runs it through the risk/curvature pipeline, and alerts on
sudden shifts in the risk landscape.

This is the UAG self-monitor: if the curvature of CARE's own
state changes suddenly, something anomalous is happening —
new IPs, new error modes, new endpoint patterns.

Threat model signals we track:
    - Anomaly rate (requests flagged / total requests)
    - Unique IP count (rapid growth = scanning)
    - Lockdown count (IPs in lockdown)
    - Error rate (5xx responses)
    - Endpoint distribution entropy (flat = scanner, peaked = human)
    - Rate limit hit rate

Alert thresholds trigger on:
    - Risk R(x) increasing > CANARY_RISK_DELTA_THRESHOLD from baseline
    - Severity crossing "safe" → "watch" → "critical"
"""
from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

CANARY_INTERVAL_SECS = float(os.getenv("CARE_CANARY_INTERVAL", "60"))
CANARY_RISK_DELTA_THRESHOLD = float(os.getenv("CARE_CANARY_RISK_DELTA", "0.25"))
CANARY_ENABLED = os.getenv("CARE_CANARY_ENABLED", "true").lower() == "true"


@dataclass
class CanarySnapshot:
    timestamp: float
    risk: float
    severity: str
    anomaly_rate: float
    unique_ips: int
    lockdown_count: int
    error_rate: float
    endpoint_entropy: float
    state_vector: list[float]


@dataclass
class CanaryState:
    snapshots: list[CanarySnapshot] = field(default_factory=list)
    baseline_risk: float | None = None
    alert_count: int = 0
    last_alert: float = 0.0


_canary_state = CanaryState()


def _endpoint_entropy(endpoint_counts: dict[str, int]) -> float:
    """Shannon entropy of endpoint hit distribution. Low = scanner (uniform), high = human."""
    total = sum(endpoint_counts.values())
    if total == 0:
        return 0.0
    probs = [c / total for c in endpoint_counts.values() if c > 0]
    return -sum(p * math.log2(p) for p in probs)


def build_canary_state(
    rate_limiter_stats: list[dict],
    endpoint_counts: dict[str, int],
    error_count: int,
    total_requests: int,
) -> dict:
    """
    Build the CARE self-state dict from runtime metrics.
    This becomes the input to the CARE pipeline.
    """
    n_ips = len(rate_limiter_stats)
    n_anomalies = sum(s.get("anomaly_count", 0) for s in rate_limiter_stats)
    n_locked = sum(1 for s in rate_limiter_stats if s.get("locked", False))
    anomaly_rate = n_anomalies / max(total_requests, 1)
    error_rate = error_count / max(total_requests, 1)
    entropy = _endpoint_entropy(endpoint_counts)

    return {
        "unique_ip_count": n_ips,
        "anomaly_count": n_anomalies,
        "lockdown_count": n_locked,
        "anomaly_rate_pct": int(anomaly_rate * 100),
        "error_rate_pct": int(error_rate * 100),
        "endpoint_entropy_x10": int(entropy * 10),
        "total_requests": total_requests,
        "_type": "generic",  # passes prod-mode validation
    }


def run_canary_check(
    rate_limiter_stats: list[dict],
    endpoint_counts: dict[str, int],
    error_count: int,
    total_requests: int,
    alert_callback: Callable[[str, CanarySnapshot], None] | None = None,
) -> CanarySnapshot | None:
    """
    Run one canary check. Returns the snapshot, fires alert_callback if threshold crossed.
    Call this from a background task on CANARY_INTERVAL_SECS schedule.
    """
    if not CANARY_ENABLED:
        return None

    from care.models.state_encoder import encode_state
    from care.models.risk_potential import get_potential
    from care.models.curvature import curvature_info
    from care.models.ridge import analyse_ridge

    state_dict = build_canary_state(
        rate_limiter_stats, endpoint_counts, error_count, total_requests
    )

    try:
        potential = get_potential("privilege")
        x = encode_state(state_dict, target_dim=8)
        result = curvature_info(x, potential, backend="numpy")
        ridge = analyse_ridge(result)
    except Exception as e:
        logger.error("Canary pipeline failed: %s", e)
        return None

    snapshot = CanarySnapshot(
        timestamp=time.time(),
        risk=result.risk,
        severity=ridge.severity,
        anomaly_rate=state_dict["anomaly_rate_pct"] / 100,
        unique_ips=state_dict["unique_ip_count"],
        lockdown_count=state_dict["lockdown_count"],
        error_rate=state_dict["error_rate_pct"] / 100,
        endpoint_entropy=state_dict["endpoint_entropy_x10"] / 10,
        state_vector=x.tolist(),
    )

    _canary_state.snapshots.append(snapshot)
    # Keep last 1440 snapshots (24h at 1/min)
    if len(_canary_state.snapshots) > 1440:
        _canary_state.snapshots = _canary_state.snapshots[-1440:]

    # Set baseline on first run
    if _canary_state.baseline_risk is None:
        _canary_state.baseline_risk = snapshot.risk
        logger.info("Canary baseline set: risk=%.2f severity=%s", snapshot.risk, snapshot.severity)
        return snapshot

    # Alert on risk delta or severity escalation
    risk_delta = (snapshot.risk - _canary_state.baseline_risk) / max(_canary_state.baseline_risk, 1)
    severity_escalated = (
        snapshot.severity == "critical" or
        (snapshot.severity == "watch" and _canary_state.snapshots[-2].severity == "safe"
         if len(_canary_state.snapshots) >= 2 else False)
    )

    if risk_delta > CANARY_RISK_DELTA_THRESHOLD or severity_escalated:
        _canary_state.alert_count += 1
        _canary_state.last_alert = time.time()
        msg = (
            f"CANARY ALERT: risk={snapshot.risk:.1f} "
            f"(+{risk_delta*100:.0f}% from baseline) "
            f"severity={snapshot.severity} "
            f"anomaly_rate={snapshot.anomaly_rate:.1%} "
            f"locked_ips={snapshot.lockdown_count}"
        )
        logger.error(msg)
        if alert_callback:
            alert_callback(msg, snapshot)

    else:
        logger.debug(
            "Canary OK: risk=%.2f severity=%s ips=%d",
            snapshot.risk, snapshot.severity, snapshot.unique_ips
        )

    return snapshot


def get_canary_status() -> dict:
    s = _canary_state
    latest = s.snapshots[-1] if s.snapshots else None
    return {
        "enabled": CANARY_ENABLED,
        "alert_count": s.alert_count,
        "last_alert": s.last_alert or None,
        "baseline_risk": s.baseline_risk,
        "latest": {
            "risk": latest.risk,
            "severity": latest.severity,
            "anomaly_rate": latest.anomaly_rate,
            "unique_ips": latest.unique_ips,
            "lockdown_count": latest.lockdown_count,
        } if latest else None,
        "snapshot_count": len(s.snapshots),
    }
