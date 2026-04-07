"""
CARE FastAPI server — hardened v0.2.

Security additions over v0.1:
    - Per-IP rate limiting (60 req/min per route, configurable)
    - Anomaly detection: chain probe + all-endpoint burst patterns
    - Immutable append-only audit log (file/Redis/S3 backends)
    - Input validation with lab/prod modes
    - Lockdown membrane: freeze deltas on anomaly threshold
    - Speed + attestation membranes for high-impact actions
    - CARE canary: self-monitoring background task
    - /security/status endpoint for operator visibility
    - /security/lockdown/release for manual lockdown release

Endpoints:
    GET  /health
    POST /encode
    POST /risk
    POST /curvature
    POST /escape-route
    POST /recommend
    POST /apply
    GET  /security/status
    POST /security/lockdown/release
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from care import __version__
from care.config import settings
from care.api.schemas import (
    StateInput, HealthResponse, EncodeResponse, RiskResponse,
    CurvatureResponse, EscapeRouteResponse, RecommendResponse,
    ApplyResponse, Action,
)
from care.models.state_encoder import encode_state
from care.models.risk_potential import get_potential
from care.models.curvature import curvature_info
from care.models.ridge import analyse_ridge, summarise as ridge_summary
from care.models.recommend import recommend_actions
from care.adapters.constitutional_os import propose_delta, apply_delta
from care.security.rate_limiter import get_limiter
from care.security.audit_log import get_audit_log, make_entry
from care.security.input_validator import (
    validate_request, ValidationError, MAX_PAYLOAD_BYTES
)
from care.security.canary import (
    run_canary_check, get_canary_status, CANARY_INTERVAL_SECS
)
from care.membranes.lockdown import (
    check_all_security_membranes, get_lockdown_status,
    release_lockdown, engage_lockdown, is_locked_down,
)

logger = logging.getLogger(__name__)

# Runtime counters for canary
_endpoint_counts: dict[str, int] = {}
_error_count: int = 0
_total_requests: int = 0

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="CARE — Curvature-Aware Risk Engine",
    description=(
        "Keeps infrastructure inside a safe attractor by computing curvature "
        "on system-state risk surfaces and recommending membrane-level interventions. "
        "Theoretical basis: Unified Attractor Grammar (Byte, 2026), "
        "doi:10.5281/zenodo.19394700."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security middleware ───────────────────────────────────────────────────────

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    global _error_count, _total_requests

    start = time.time()
    route = request.url.path
    method = request.method
    ip = request.client.host if request.client else "unknown"

    _total_requests += 1
    _endpoint_counts[route] = _endpoint_counts.get(route, 0) + 1

    audit = get_audit_log()
    limiter = get_limiter()

    # Payload size check before parsing
    raw_body = await request.body()
    if len(raw_body) > MAX_PAYLOAD_BYTES:
        _error_count += 1
        audit.record(make_entry(
            ip=ip, route=route, method=method, payload=raw_body,
            decision="blocked_payload_too_large", status_code=413,
            anomaly_flags=["oversized_payload"],
        ))
        return JSONResponse(
            status_code=413,
            content={"detail": f"Payload too large (max {MAX_PAYLOAD_BYTES} bytes)."}
        )

    # Rate limit + anomaly check
    allowed, reason = limiter.check(ip, route)
    if not allowed:
        _error_count += 1
        stats = limiter.get_stats(ip)
        if stats.get("locked"):
            engage_lockdown(f"IP {ip} locked down: {reason}")
        audit.record(make_entry(
            ip=ip, route=route, method=method, payload=raw_body,
            decision="rate_limited", status_code=429,
            anomaly_flags=["rate_limit_exceeded"],
        ))
        return JSONResponse(
            status_code=429,
            content={"detail": reason, "retry_after": 60}
        )

    # Rebuild request with consumed body
    async def receive():
        return {"type": "http.request", "body": raw_body}
    request = Request(request.scope, receive)

    response = await call_next(request)
    latency_ms = (time.time() - start) * 1000

    if response.status_code >= 500:
        _error_count += 1

    audit.record(make_entry(
        ip=ip, route=route, method=method, payload=raw_body,
        decision="allowed" if response.status_code < 400 else "rejected",
        status_code=response.status_code,
        latency_ms=latency_ms,
    ))

    return response


# ── Canary background task ────────────────────────────────────────────────────

@app.on_event("startup")
async def start_canary():
    asyncio.create_task(_canary_loop())


async def _canary_loop():
    while True:
        await asyncio.sleep(CANARY_INTERVAL_SECS)
        try:
            limiter = get_limiter()
            run_canary_check(
                rate_limiter_stats=limiter.all_stats(),
                endpoint_counts=dict(_endpoint_counts),
                error_count=_error_count,
                total_requests=_total_requests,
                alert_callback=lambda msg, snap: logger.error("CANARY: %s", msg),
            )
        except Exception as e:
            logger.error("Canary loop error: %s", e)


# ── Pipeline helper ───────────────────────────────────────────────────────────

def _risk_severity(r: float) -> str:
    if r > settings.high_risk_threshold:
        return "high"
    if r > settings.high_risk_threshold / 3:
        return "medium"
    return "low"


def _pipeline(payload: StateInput):
    try:
        validate_request(payload.state, payload.potential, payload.backend)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    potential = get_potential(payload.potential)
    x = encode_state(payload.state)
    result = curvature_info(x, potential, backend=payload.backend)
    ridge = analyse_ridge(result)
    return x, result, ridge, potential


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health():
    return HealthResponse(version=__version__)


@app.post("/encode", response_model=EncodeResponse, tags=["pipeline"])
def encode(payload: StateInput):
    try:
        validate_request(payload.state, payload.potential, payload.backend)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    x = encode_state(payload.state)
    return EncodeResponse(vector=x.tolist(), dim=len(x))


@app.post("/risk", response_model=RiskResponse, tags=["pipeline"])
def risk(payload: StateInput):
    _, result, _, _ = _pipeline(payload)
    return RiskResponse(risk=result.risk, severity_hint=_risk_severity(result.risk))


@app.post("/curvature", response_model=CurvatureResponse, tags=["pipeline"])
def curvature(payload: StateInput):
    _, result, _, _ = _pipeline(payload)
    return CurvatureResponse(
        risk=result.risk,
        gradient=result.gradient.tolist(),
        hessian=result.hessian.tolist(),
        eigenvalues=result.eigenvalues.tolist(),
        backend_used=result.backend_used,
    )


@app.post("/escape-route", response_model=EscapeRouteResponse, tags=["pipeline"])
def escape_route(payload: StateInput):
    _, result, ridge, _ = _pipeline(payload)
    return EscapeRouteResponse(**ridge_summary(ridge))


@app.post("/recommend", response_model=RecommendResponse, tags=["pipeline"])
def recommend(payload: StateInput):
    x, result, ridge, _ = _pipeline(payload)
    actions = recommend_actions(result, ridge, raw_state=payload.state)
    return RecommendResponse(
        actions=[Action(**a.to_dict()) for a in actions],
        n_actions=len(actions),
        severity=ridge.severity,
    )


@app.post("/apply", response_model=ApplyResponse, tags=["pipeline"])
def apply(payload: StateInput):
    # Security membrane check
    test_delta = {"action_type": "apply", "target": "system",
                  "from_state": "current", "to_state": "hardened",
                  "reason": "CARE apply endpoint"}
    mem_ok, mem_reason = check_all_security_membranes(test_delta)
    if not mem_ok:
        raise HTTPException(status_code=503, detail=f"Security membrane blocked: {mem_reason}")

    if not settings.cos_enabled:
        _, result, ridge, _ = _pipeline(payload)
        actions = recommend_actions(result, ridge, raw_state=payload.state)
        return ApplyResponse(
            status="dry_run",
            delta_ids=[str(uuid.uuid4()) for _ in actions],
            message=(
                f"Constitutional OS not enabled. "
                f"{len(actions)} action(s) would be applied. "
                "Set CARE_COS_ENABLED=true to apply."
            ),
        )

    try:
        _, result, ridge, _ = _pipeline(payload)
        actions = recommend_actions(result, ridge, raw_state=payload.state)
        deltas = propose_delta([a.to_dict() for a in actions])
        applied = apply_delta(deltas)
        return ApplyResponse(
            status="accepted",
            delta_ids=[d["id"] for d in applied],
            message=f"Applied {len(applied)} delta(s) via Constitutional OS.",
        )
    except Exception as e:
        logger.exception("Apply failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Security operator endpoints ───────────────────────────────────────────────

@app.get("/security/status", tags=["security"])
def security_status():
    """Operator visibility: rate limiter, lockdown state, canary, audit tail."""
    limiter = get_limiter()
    audit = get_audit_log()
    return {
        "lockdown": get_lockdown_status(),
        "canary": get_canary_status(),
        "rate_limiter": {
            "total_ips_seen": len(limiter.all_stats()),
            "locked_ips": [s for s in limiter.all_stats() if s.get("locked")],
            "top_anomalous": sorted(
                limiter.all_stats(),
                key=lambda s: s.get("anomaly_count", 0), reverse=True
            )[:5],
        },
        "audit_log": {
            "total_entries": audit.count(),
            "recent": audit.tail(10),
        },
        "runtime": {
            "total_requests": _total_requests,
            "error_count": _error_count,
            "endpoint_counts": _endpoint_counts,
        },
    }


@app.post("/security/lockdown/release", tags=["security"])
def lockdown_release():
    """Manually release system lockdown after operator review."""
    if not is_locked_down():
        return {"status": "not_locked", "message": "System was not in lockdown."}
    release_lockdown()
    return {"status": "released", "message": "Lockdown released by operator."}


# ── Dev entrypoint ────────────────────────────────────────────────────────────

def main():
    import uvicorn
    uvicorn.run(
        "care.api.server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
