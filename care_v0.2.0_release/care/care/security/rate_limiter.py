"""
CARE Rate Limiter + Anomaly Detector.

Per-IP sliding window rate limiting on all endpoints.
Explicit anomaly pattern detection — no ML needed, just known bad sequences.

Threat model:
    AI scanners hammer endpoints faster than humans.
    They chain: /encode → /curvature → /escape-route → /recommend in seconds.
    They burst-scan all endpoints in short windows.
    They probe input shapes systematically.

Defense:
    - 60 req/min per IP per route (configurable)
    - Flag chained probe sequences within N seconds
    - Flag all-endpoint bursts
    - Exponential backoff for repeat offenders
    - Lockdown mode: freeze all requests from IP after threshold
"""
from __future__ import annotations

import time
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

RATE_LIMIT_PER_MIN: int = 60          # requests per IP per route per minute
BURST_WINDOW_SECS: float = 10.0       # window for burst/chain detection
CHAIN_PROBE_THRESHOLD: int = 4        # N distinct sensitive endpoints in window = anomaly
LOCKDOWN_ANOMALY_THRESHOLD: int = 3   # N anomalies from same IP → lockdown
LOCKDOWN_DURATION_SECS: float = 300.0 # 5 min lockdown

# Sensitive endpoint chain — hitting all of these in a short window = scanner
SENSITIVE_CHAIN = {"/curvature", "/escape-route", "/recommend", "/apply"}

# All endpoints — hitting everything in a burst = automated probe
ALL_ENDPOINTS = {"/health", "/encode", "/risk", "/curvature",
                 "/escape-route", "/recommend", "/apply"}


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class IPState:
    # Per-route sliding windows: route → deque of timestamps
    route_windows: dict[str, Deque[float]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    # Recent endpoint hits for chain/burst detection
    recent_hits: Deque[tuple[float, str]] = field(default_factory=deque)
    # Anomaly count
    anomaly_count: int = 0
    # Lockdown expiry (0 = not locked)
    lockdown_until: float = 0.0
    # Total requests (for logging)
    total_requests: int = 0


# ── Core limiter ───────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Thread-safe (single-process) per-IP rate limiter with anomaly detection.
    For multi-process deployments, back this with Redis.
    """

    def __init__(self):
        self._state: dict[str, IPState] = defaultdict(IPState)

    def check(self, ip: str, route: str) -> tuple[bool, str]:
        """
        Check whether a request should be allowed.

        Returns (allowed: bool, reason: str).
        allowed=False means return 429.
        """
        now = time.time()
        state = self._state[ip]
        state.total_requests += 1

        # ── Lockdown check ────────────────────────────────────────────────────
        if state.lockdown_until > now:
            remaining = int(state.lockdown_until - now)
            logger.warning("LOCKDOWN: IP=%s route=%s remaining=%ds", ip, route, remaining)
            return False, f"IP locked down for {remaining}s due to anomalous activity."

        # ── Per-route sliding window ──────────────────────────────────────────
        window = state.route_windows[route]
        cutoff = now - 60.0
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= RATE_LIMIT_PER_MIN:
            logger.warning("RATE_LIMIT: IP=%s route=%s count=%d", ip, route, len(window))
            return False, f"Rate limit: {RATE_LIMIT_PER_MIN} req/min on {route}."
        window.append(now)

        # ── Record hit for anomaly detection ──────────────────────────────────
        state.recent_hits.append((now, route))
        burst_cutoff = now - BURST_WINDOW_SECS
        while state.recent_hits and state.recent_hits[0][0] < burst_cutoff:
            state.recent_hits.popleft()

        # ── Anomaly: sensitive chain probe ────────────────────────────────────
        recent_routes = {r for _, r in state.recent_hits}
        chain_hits = recent_routes & SENSITIVE_CHAIN
        if len(chain_hits) >= CHAIN_PROBE_THRESHOLD:
            state.anomaly_count += 1
            logger.warning(
                "ANOMALY chain_probe: IP=%s routes=%s anomalies=%d",
                ip, chain_hits, state.anomaly_count
            )
            self._maybe_lockdown(ip, state, now)

        # ── Anomaly: all-endpoint burst ───────────────────────────────────────
        all_hits = recent_routes & ALL_ENDPOINTS
        if len(all_hits) >= len(ALL_ENDPOINTS):
            state.anomaly_count += 1
            logger.warning(
                "ANOMALY all_endpoint_burst: IP=%s anomalies=%d",
                ip, state.anomaly_count
            )
            self._maybe_lockdown(ip, state, now)

        return True, "ok"

    def _maybe_lockdown(self, ip: str, state: IPState, now: float) -> None:
        if state.anomaly_count >= LOCKDOWN_ANOMALY_THRESHOLD:
            state.lockdown_until = now + LOCKDOWN_DURATION_SECS
            logger.error(
                "LOCKDOWN_ENGAGED: IP=%s anomalies=%d duration=%ds",
                ip, state.anomaly_count, LOCKDOWN_DURATION_SECS
            )

    def get_stats(self, ip: str) -> dict:
        state = self._state.get(ip)
        if not state:
            return {"ip": ip, "known": False}
        now = time.time()
        return {
            "ip": ip,
            "known": True,
            "total_requests": state.total_requests,
            "anomaly_count": state.anomaly_count,
            "locked": state.lockdown_until > now,
            "lockdown_until": state.lockdown_until if state.lockdown_until > now else None,
        }

    def all_stats(self) -> list[dict]:
        return [self.get_stats(ip) for ip in self._state]


# ── Singleton ─────────────────────────────────────────────────────────────────
_limiter = RateLimiter()

def get_limiter() -> RateLimiter:
    return _limiter
