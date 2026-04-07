"""
CARE test suite — full pipeline coverage.

Tests are organised by module:
    test_state_encoder    — encoding contract
    test_risk_potential   — all three built-in potentials
    test_curvature        — gradient, Hessian, eigendecomposition
    test_ridge            — UAG Theorem 4 predictions
    test_recommend        — hardening rule engine
    test_deltas           — delta creation, rollback, audit log
    test_policies         — membrane policy enforcement
    test_constitutional_os— propose/apply pipeline
    test_api              — FastAPI endpoint smoke tests
"""
from __future__ import annotations

import json
import numpy as np
import pytest
from fastapi.testclient import TestClient

# ── Fixtures ──────────────────────────────────────────────────────────────────

IAM_STATE = {
    "user_count": 42,
    "admin_users": 5,
    "policies": 17,
    "overpermissioned_policies": 3,
    "inactive_access_keys": 8,
    "mfa_disabled_users": 12,
    "cross_account_trusts": 2,
    "roles": 23,
}

MINIMAL_STATE = {"user_count": 1, "admin_users": 0}
EMPTY_STATE: dict = {}


# ── State encoder ─────────────────────────────────────────────────────────────

class TestStateEncoder:
    def test_dict_returns_float64_array(self):
        from care.models.state_encoder import encode_state
        x = encode_state(IAM_STATE)
        assert isinstance(x, np.ndarray)
        assert x.dtype == np.float64

    def test_empty_dict_returns_zeros(self):
        from care.models.state_encoder import encode_state
        x = encode_state(EMPTY_STATE)
        assert x.dtype == np.float64
        assert len(x) > 0

    def test_none_returns_zeros(self):
        from care.models.state_encoder import encode_state
        x = encode_state(None)
        assert np.all(x == 0.0)

    def test_target_dim_respected(self):
        from care.models.state_encoder import encode_state
        for dim in [4, 16, 32]:
            x = encode_state(IAM_STATE, target_dim=dim)
            assert len(x) == dim

    def test_scalar_input(self):
        from care.models.state_encoder import encode_state
        x = encode_state(42.0)
        assert len(x) > 0

    def test_list_input(self):
        from care.models.state_encoder import encode_state
        x = encode_state([1, 2, 3, 4, 5])
        assert len(x) > 0

    def test_deterministic(self):
        from care.models.state_encoder import encode_state
        x1 = encode_state(IAM_STATE)
        x2 = encode_state(IAM_STATE)
        np.testing.assert_array_equal(x1, x2)


# ── Risk potential ────────────────────────────────────────────────────────────

class TestRiskPotential:
    def _x(self, n=8):
        return np.ones(n) * 2.0

    def test_quadratic_value(self):
        from care.models.risk_potential import QuadraticRisk
        r = QuadraticRisk()
        x = self._x()
        assert abs(r(x) - float(np.dot(x, x))) < 1e-10

    def test_privilege_weights_first_dims(self):
        from care.models.risk_potential import PrivilegeRisk
        r = PrivilegeRisk(n_privileged=2, privilege_weight=10.0)
        x = np.ones(4)
        val = r(x)
        # First 2 dims weight 10, last 2 weight 1: 10*1 + 10*1 + 1*1 + 1*1 = 22
        assert abs(val - 22.0) < 1e-10

    def test_blast_radius_positive_definite(self):
        from care.models.risk_potential import BlastRadiusRisk
        r = BlastRadiusRisk()
        for _ in range(10):
            x = np.random.randn(8)
            assert r(x) >= 0

    def test_registry_and_getter(self):
        from care.models.risk_potential import get_potential
        for name in ["quadratic", "privilege", "blast_radius"]:
            p = get_potential(name)
            assert callable(p)

    def test_custom_potential_registration(self):
        from care.models.risk_potential import register_potential, get_potential
        register_potential("test_const", lambda x: 42.0)
        p = get_potential("test_const")
        assert p(np.zeros(4)) == 42.0

    def test_unknown_potential_raises(self):
        from care.models.risk_potential import get_potential
        with pytest.raises(ValueError, match="Unknown risk potential"):
            get_potential("nonexistent_xyz")


# ── Curvature ─────────────────────────────────────────────────────────────────

class TestCurvature:
    def _setup(self):
        from care.models.state_encoder import encode_state
        from care.models.risk_potential import QuadraticRisk
        x = encode_state(IAM_STATE, target_dim=8)
        pot = QuadraticRisk()
        return x, pot

    def test_gradient_shape(self):
        from care.models.curvature import compute_gradient
        x, pot = self._setup()
        g = compute_gradient(x, pot, backend="numpy")
        assert g.shape == x.shape

    def test_gradient_quadratic_analytic(self):
        from care.models.curvature import compute_gradient
        from care.models.risk_potential import QuadraticRisk
        x = np.array([1.0, 2.0, 3.0])
        g = compute_gradient(x, QuadraticRisk(), backend="numpy")
        np.testing.assert_allclose(g, 2 * x, atol=1e-4)

    def test_hessian_shape(self):
        from care.models.curvature import compute_hessian
        x, pot = self._setup()
        H = compute_hessian(x, pot, backend="numpy")
        assert H.shape == (len(x), len(x))

    def test_hessian_quadratic_is_2I(self):
        from care.models.curvature import compute_hessian
        from care.models.risk_potential import QuadraticRisk
        n = 5
        x = np.random.randn(n)
        H = compute_hessian(x, QuadraticRisk(), backend="numpy")
        np.testing.assert_allclose(H, 2 * np.eye(n), atol=1e-3)

    def test_hessian_symmetric(self):
        from care.models.curvature import compute_hessian
        from care.models.risk_potential import BlastRadiusRisk
        x = np.random.randn(6)
        H = compute_hessian(x, BlastRadiusRisk(), backend="numpy")
        np.testing.assert_allclose(H, H.T, atol=1e-8)

    def test_curvature_info_result(self):
        from care.models.curvature import curvature_info
        x, pot = self._setup()
        result = curvature_info(x, pot, backend="numpy")
        assert result.eigenvalues.shape == x.shape
        assert isinstance(result.risk, float)
        assert result.gradient.shape == x.shape

    def test_eigenvalues_ascending(self):
        from care.models.curvature import curvature_info
        x, pot = self._setup()
        result = curvature_info(x, pot)
        assert np.all(np.diff(result.eigenvalues) >= -1e-10)

    def test_backend_used_recorded(self):
        from care.models.curvature import curvature_info
        x, pot = self._setup()
        r = curvature_info(x, pot, backend="numpy")
        assert r.backend_used == "numpy"


# ── Ridge ─────────────────────────────────────────────────────────────────────

class TestRidge:
    def _result(self, eigenvalues):
        from care.models.curvature import CurvatureResult
        n = len(eigenvalues)
        x = np.ones(n)
        vecs = np.eye(n)
        return CurvatureResult(
            x=x, risk=1.0,
            gradient=np.ones(n),
            hessian=np.diag(eigenvalues),
            eigenvalues=np.array(eigenvalues),
            eigenvectors=vecs,
            backend_used="numpy",
        )

    def test_safe_severity_all_positive(self):
        from care.models.ridge import analyse_ridge
        result = self._result([2.0, 3.0, 4.0])
        ridge = analyse_ridge(result)
        assert ridge.severity == "safe"
        assert ridge.n_negative == 0

    def test_critical_severity_negative_eigenvalue(self):
        from care.models.ridge import analyse_ridge
        result = self._result([-0.5, 1.0, 2.0])
        ridge = analyse_ridge(result)
        assert ridge.severity == "critical"
        assert ridge.n_negative == 1

    def test_watch_severity_soft_lambda(self):
        from care.models.ridge import analyse_ridge
        result = self._result([0.3, 1.0, 2.0])
        ridge = analyse_ridge(result)
        assert ridge.severity == "watch"

    def test_softest_index_correct(self):
        from care.models.ridge import analyse_ridge
        result = self._result([5.0, 0.1, 3.0])
        ridge = analyse_ridge(result)
        # 0.1 is smallest |λ| — sorted ascending, so index 0
        assert abs(ridge.softest_eigenvalue) < 1.0

    def test_kramers_proxy_range(self):
        from care.models.ridge import analyse_ridge
        result = self._result([1.0, 2.0, 3.0])
        ridge = analyse_ridge(result)
        assert 0.0 <= ridge.kramers_proxy <= 1.0

    def test_escape_direction_unit_vector(self):
        from care.models.ridge import analyse_ridge
        result = self._result([0.2, 1.0, 3.0])
        ridge = analyse_ridge(result)
        norm = np.linalg.norm(ridge.escape_direction)
        assert abs(norm - 1.0) < 1e-8

    def test_summarise_serialisable(self):
        from care.models.ridge import analyse_ridge, summarise
        result = self._result([1.0, 2.0])
        ridge = analyse_ridge(result)
        d = summarise(ridge)
        assert "severity" in d
        assert "kramers_escape_proxy" in d
        json.dumps(d)   # must be JSON-serialisable


# ── Recommend ─────────────────────────────────────────────────────────────────

class TestRecommend:
    def _pipeline(self, eigenvalues, risk=5.0):
        from care.models.curvature import CurvatureResult
        from care.models.ridge import analyse_ridge
        n = len(eigenvalues)
        result = CurvatureResult(
            x=np.ones(n) * 2.0, risk=risk,
            gradient=np.ones(n) * 3.0,
            hessian=np.diag(eigenvalues),
            eigenvalues=np.array(sorted(eigenvalues)),
            eigenvectors=np.eye(n),
            backend_used="numpy",
        )
        ridge = analyse_ridge(result)
        return result, ridge

    def test_no_actions_safe_low_risk(self):
        from care.models.recommend import recommend_actions
        result, ridge = self._pipeline([2.0, 3.0, 4.0], risk=1.0)
        actions = recommend_actions(result, ridge)
        assert isinstance(actions, list)

    def test_quarantine_on_critical(self):
        from care.models.recommend import recommend_actions
        result, ridge = self._pipeline([-0.5, 1.0, 2.0], risk=5.0)
        actions = recommend_actions(result, ridge)
        types = [a.action_type for a in actions]
        assert "quarantine" in types

    def test_mfa_on_high_risk(self):
        from care.models.recommend import recommend_actions
        result, ridge = self._pipeline([2.0, 3.0], risk=100.0)
        actions = recommend_actions(result, ridge)
        types = [a.action_type for a in actions]
        assert "add_mfa" in types

    def test_actions_sorted_by_priority(self):
        from care.models.recommend import recommend_actions
        result, ridge = self._pipeline([-0.1, 0.2, 1.0], risk=50.0)
        actions = recommend_actions(result, ridge)
        priorities = [a.priority for a in actions]
        assert priorities == sorted(priorities)

    def test_all_actions_have_uag_link(self):
        from care.models.recommend import recommend_actions
        result, ridge = self._pipeline([-0.1, 0.2, 3.0], risk=50.0)
        for action in recommend_actions(result, ridge):
            assert action.uag_link, f"Action {action.action_type} missing uag_link"

    def test_to_dict_serialisable(self):
        from care.models.recommend import recommend_actions
        result, ridge = self._pipeline([0.2, 1.0], risk=50.0)
        for a in recommend_actions(result, ridge):
            json.dumps(a.to_dict())


# ── Deltas ────────────────────────────────────────────────────────────────────

class TestDeltas:
    def _action(self):
        return {
            "action_type": "reduce_privilege",
            "target": "service_a",
            "from_state": "admin",
            "to_state": "read_only",
            "reason": "test reason",
            "uag_link": "UAG Theorem 4",
        }

    def test_delta_has_uuid(self):
        from care.membranes.deltas import from_action
        d = from_action(self._action())
        assert len(d.id) == 36    # UUID4 format

    def test_delta_has_checksum(self):
        from care.membranes.deltas import from_action
        d = from_action(self._action())
        assert len(d.checksum) == 16

    def test_delta_rollback_swaps_states(self):
        from care.membranes.deltas import from_action
        d = from_action(self._action())
        r = d.rollback()
        assert r.from_state == "read_only"
        assert r.to_state == "admin"

    def test_delta_to_dict_serialisable(self):
        from care.membranes.deltas import from_action
        d = from_action(self._action())
        json.dumps(d.to_dict())

    def test_audit_log_records(self):
        from care.membranes.deltas import from_action, record, get_log
        d = from_action(self._action())
        record(d)
        log = get_log()
        assert any(entry["id"] == d.id for entry in log)


# ── Membrane policies ─────────────────────────────────────────────────────────

class TestPolicies:
    def _delta(self, action_type="reduce_privilege", reason="test"):
        return {"action_type": action_type, "from_state": "x", "to_state": "y", "reason": reason}

    def test_normal_action_passes(self):
        from care.membranes.policies import check_all
        allowed, msg = check_all(self._delta())
        assert allowed is True

    def test_quarantine_blocked_by_default(self):
        from care.membranes.policies import check_all
        allowed, msg = check_all(self._delta(action_type="quarantine"))
        assert allowed is False
        assert "quarantine" in msg.lower()

    def test_empty_reason_blocked(self):
        from care.membranes.policies import check_all
        allowed, msg = check_all(self._delta(reason=""))
        assert allowed is False

    def test_privilege_escalation_blocked(self):
        from care.membranes.policies import check_all
        d = {"action_type": "grant_privilege", "from_state": "read_only",
             "to_state": "admin", "reason": "test"}
        allowed, msg = check_all(d)
        assert allowed is False


# ── Constitutional OS adapter ─────────────────────────────────────────────────

class TestConstitutionalOS:
    def _actions(self):
        return [{
            "action_type": "rate_limit",
            "target": "api_endpoint",
            "from_state": "unlimited",
            "to_state": "rate_limited",
            "reason": "soft curvature detected",
            "uag_link": "UAG Theorem 4",
        }]

    def test_propose_returns_deltas(self):
        from care.adapters.constitutional_os import propose_delta
        deltas = propose_delta(self._actions())
        assert len(deltas) == 1
        assert "id" in deltas[0]
        assert "checksum" in deltas[0]

    def test_quarantine_blocked_by_membrane(self):
        from care.adapters.constitutional_os import propose_delta
        actions = [{"action_type": "quarantine", "target": "x",
                    "from_state": "a", "to_state": "b", "reason": "test"}]
        deltas = propose_delta(actions)
        assert deltas[0]["membrane_allowed"] is False

    def test_apply_stub_marks_applied(self):
        from care.adapters.constitutional_os import propose_delta, apply_delta
        deltas = propose_delta(self._actions())
        applied = apply_delta(deltas)
        assert len(applied) == 1
        assert applied[0]["status"] in ("applied_stub", "applied")


# ── FastAPI endpoints ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from care.api.server import app
    return TestClient(app)


PAYLOAD = {"state": IAM_STATE, "potential": "privilege"}


class TestAPI:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_encode(self, client):
        r = client.post("/encode", json=PAYLOAD)
        assert r.status_code == 200
        d = r.json()
        assert "vector" in d
        assert d["dim"] > 0

    def test_risk(self, client):
        r = client.post("/risk", json=PAYLOAD)
        assert r.status_code == 200
        d = r.json()
        assert "risk" in d
        assert isinstance(d["risk"], float)
        assert d["severity_hint"] in ("low", "medium", "high")

    def test_curvature(self, client):
        r = client.post("/curvature", json=PAYLOAD)
        assert r.status_code == 200
        d = r.json()
        assert "hessian" in d
        assert "eigenvalues" in d
        assert "gradient" in d

    def test_escape_route(self, client):
        r = client.post("/escape-route", json=PAYLOAD)
        assert r.status_code == 200
        d = r.json()
        assert "severity" in d
        assert "kramers_escape_proxy" in d
        assert d["severity"] in ("safe", "watch", "critical")

    def test_recommend(self, client):
        r = client.post("/recommend", json=PAYLOAD)
        assert r.status_code == 200
        d = r.json()
        assert "actions" in d
        assert isinstance(d["actions"], list)
        assert "severity" in d

    def test_apply_dry_run(self, client):
        r = client.post("/apply", json=PAYLOAD)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] in ("dry_run", "accepted")
        assert isinstance(d["delta_ids"], list)

    def test_all_potentials_accepted(self, client):
        for potential in ["quadratic", "privilege", "blast_radius"]:
            r = client.post("/risk", json={"state": IAM_STATE, "potential": potential})
            assert r.status_code == 200, f"Failed for potential={potential}"

    def test_empty_state_handled(self, client):
        r = client.post("/risk", json={"state": {}, "potential": "quadratic"})
        assert r.status_code == 200


# ── Security tests ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter between every test — prevents cross-test rate limit triggers."""
    from care.security import rate_limiter as rl
    rl._limiter = rl.RateLimiter()
    yield
    rl._limiter = rl.RateLimiter()


class TestRateLimiter:
    def test_allows_normal_request(self):
        from care.security.rate_limiter import RateLimiter
        rl = RateLimiter()
        allowed, reason = rl.check("10.0.0.1", "/risk")
        assert allowed is True

    def test_blocks_after_limit(self):
        from care.security.rate_limiter import RateLimiter, RATE_LIMIT_PER_MIN
        rl = RateLimiter()
        for _ in range(RATE_LIMIT_PER_MIN):
            rl.check("10.0.0.2", "/risk")
        allowed, reason = rl.check("10.0.0.2", "/risk")
        assert allowed is False
        assert "Rate limit" in reason

    def test_different_routes_independent(self):
        from care.security.rate_limiter import RateLimiter, RATE_LIMIT_PER_MIN
        rl = RateLimiter()
        for _ in range(RATE_LIMIT_PER_MIN):
            rl.check("10.0.0.3", "/risk")
        # /curvature is a different route — should still be allowed
        allowed, _ = rl.check("10.0.0.3", "/curvature")
        assert allowed is True

    def test_anomaly_chain_probe_detection(self):
        from care.security.rate_limiter import RateLimiter, SENSITIVE_CHAIN
        rl = RateLimiter()
        ip = "10.0.0.4"
        for route in SENSITIVE_CHAIN:
            rl.check(ip, route)
        stats = rl.get_stats(ip)
        assert stats["anomaly_count"] >= 1

    def test_lockdown_after_repeated_anomalies(self):
        from care.security.rate_limiter import RateLimiter, SENSITIVE_CHAIN, LOCKDOWN_ANOMALY_THRESHOLD
        rl = RateLimiter()
        ip = "10.0.0.5"
        import time
        for _ in range(LOCKDOWN_ANOMALY_THRESHOLD + 1):
            for route in SENSITIVE_CHAIN:
                rl.check(ip, route)
        stats = rl.get_stats(ip)
        assert stats["locked"] is True

    def test_get_stats_unknown_ip(self):
        from care.security.rate_limiter import RateLimiter
        rl = RateLimiter()
        stats = rl.get_stats("99.99.99.99")
        assert stats["known"] is False


class TestAuditLog:
    def test_memory_backend_records(self):
        from care.security.audit_log import AuditLog, _MemoryBackend, make_entry
        log = AuditLog()
        log._backend = _MemoryBackend()
        entry = make_entry("1.2.3.4", "/risk", "POST", b'{}', "allowed", 200)
        log.record(entry)
        assert log.count() == 1

    def test_file_backend_appends(self, tmp_path):
        from care.security.audit_log import _FileBackend, make_entry
        fb = _FileBackend(str(tmp_path / "audit.jsonl"))
        e1 = make_entry("1.2.3.4", "/risk", "POST", b'{}', "allowed", 200)
        e2 = make_entry("1.2.3.4", "/curvature", "POST", b'{}', "allowed", 200)
        fb.append(e1)
        fb.append(e2)
        assert fb.count() == 2
        tail = fb.tail(5)
        assert len(tail) == 2

    def test_entry_has_required_fields(self):
        from care.security.audit_log import make_entry
        e = make_entry("1.2.3.4", "/risk", "POST", b'{"state":{}}', "allowed", 200)
        d = e.to_dict()
        for field in ["request_id", "timestamp_utc", "ip", "route", "decision",
                      "payload_hash", "status_code"]:
            assert field in d

    def test_payload_hash_not_payload(self):
        """Audit log must never store raw payload — only hash."""
        from care.security.audit_log import make_entry
        sensitive = b'{"admin_password": "hunter2"}'
        e = make_entry("1.2.3.4", "/apply", "POST", sensitive, "allowed", 200)
        d = e.to_dict()
        assert "hunter2" not in str(d)
        assert len(d["payload_hash"]) == 16  # truncated SHA-256


class TestInputValidator:
    def test_valid_request_passes(self):
        from care.security.input_validator import validate_request
        validate_request({"user_count": 5}, "privilege", None)

    def test_oversized_payload_detected(self):
        from care.security.input_validator import validate_payload_size, MAX_PAYLOAD_BYTES, ValidationError
        with pytest.raises(ValidationError):
            validate_payload_size(b"x" * (MAX_PAYLOAD_BYTES + 1))

    def test_nan_rejected(self):
        from care.security.input_validator import validate_state, ValidationError
        with pytest.raises(ValidationError, match="NaN"):
            validate_state({"value": float("nan")})

    def test_inf_rejected(self):
        from care.security.input_validator import validate_state, ValidationError
        with pytest.raises(ValidationError, match="Inf"):
            validate_state({"value": float("inf")})

    def test_invalid_potential_rejected(self):
        from care.security.input_validator import validate_potential, ValidationError
        with pytest.raises(ValidationError):
            validate_potential("evil_potential")

    def test_invalid_backend_rejected(self):
        from care.security.input_validator import validate_backend, ValidationError
        with pytest.raises(ValidationError):
            validate_backend("cuda_magic")

    def test_deep_nesting_rejected(self):
        from care.security.input_validator import validate_state, ValidationError, MAX_STATE_DEPTH
        deep = {}
        current = deep
        for _ in range(MAX_STATE_DEPTH + 2):
            current["x"] = {}
            current = current["x"]
        with pytest.raises(ValidationError, match="nesting"):
            validate_state(deep)


class TestLockdownMembrane:
    def setup_method(self):
        from care.membranes import lockdown
        lockdown._lockdown_active = False
        lockdown._lockdown_reason = ""
        lockdown._last_delta_time = 0.0

    def teardown_method(self):
        from care.membranes import lockdown
        lockdown._lockdown_active = False
        lockdown._last_delta_time = 0.0

    def test_normal_delta_passes(self):
        from care.membranes.lockdown import check_lockdown_membrane
        ok, msg = check_lockdown_membrane({"action_type": "rate_limit"})
        assert ok is True

    def test_lockdown_blocks_all(self):
        from care.membranes.lockdown import engage_lockdown, check_lockdown_membrane
        engage_lockdown("test lockdown")
        ok, msg = check_lockdown_membrane({"action_type": "rate_limit"})
        assert ok is False
        assert "lockdown" in msg.lower()

    def test_release_allows_again(self):
        from care.membranes.lockdown import engage_lockdown, release_lockdown, check_lockdown_membrane
        engage_lockdown("test")
        release_lockdown()
        ok, _ = check_lockdown_membrane({"action_type": "rate_limit"})
        assert ok is True

    def test_speed_membrane_blocks_fast_delta(self):
        import time
        from care.membranes.lockdown import check_speed_membrane
        from care.membranes import lockdown
        lockdown._last_delta_time = time.time()  # simulate very recent delta
        ok, msg = check_speed_membrane({"action_type": "rate_limit"})
        assert ok is False
        assert "fast" in msg.lower()

    def test_attestation_not_required_for_low_impact(self):
        from care.membranes.lockdown import check_attestation_membrane
        ok, msg = check_attestation_membrane({"action_type": "add_mfa"})
        assert ok is True


class TestSecurityAPI:
    def test_security_status_endpoint(self, client):
        r = client.get("/security/status")
        assert r.status_code == 200
        d = r.json()
        assert "lockdown" in d
        assert "canary" in d
        assert "rate_limiter" in d
        assert "audit_log" in d

    def test_lockdown_release_when_not_locked(self, client):
        r = client.post("/security/lockdown/release")
        assert r.status_code == 200
        assert r.json()["status"] == "not_locked"

    def test_oversized_payload_returns_413(self, client):
        from care.security.input_validator import MAX_PAYLOAD_BYTES
        big_state = {"data": "x" * (MAX_PAYLOAD_BYTES + 100)}
        import json
        r = client.post(
            "/risk",
            content=json.dumps({"state": big_state, "potential": "quadratic"}),
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 413
