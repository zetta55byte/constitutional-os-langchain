# Changelog

All notable changes to CARE are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.2.0] — 2026-04-07

Security hardening release. Addresses AI-powered attacker threat model:
reduce what they can see, reduce how fast they can probe,
increase how much you see when they try.

### Added

**`care/security/` — new security layer**
- `rate_limiter.py` — per-IP sliding window rate limiting (60 req/min per route, configurable).
  Anomaly detection: chain probe pattern (`/curvature`→`/escape-route`→`/recommend`→`/apply`
  in a short window), all-endpoint burst pattern. Exponential lockdown on repeated anomalies.
- `audit_log.py` — immutable append-only audit log. Three backends: `file` (append-only JSONL,
  fsync on every write), `redis` (Redis Streams with maxlen cap), `memory` (tests only).
  Records IP, route, method, payload SHA-256 hash (never raw payload), decision, anomaly flags,
  membrane flags, latency. Survives process compromise.
- `input_validator.py` — typed input validation. Lab mode (size/depth limits only) and prod mode
  (strict: reject unknown top-level shapes, require `_type` field). NaN/Inf rejection. Configurable
  max payload size (64KB default), max nesting depth, max key count, max string length.
- `canary.py` — CARE watching CARE. Background task encodes CARE's own runtime state
  (anomaly rate, unique IPs, error rate, endpoint entropy, lockdown count) as a vector,
  runs it through the full CARE pipeline, and alerts when risk R(x) shifts >25% from baseline
  or severity escalates. Fires configurable alert callback.

**`care/membranes/lockdown.py` — security membrane extensions**
- System-wide lockdown mode: freeze all delta application until manual operator review.
  Engages automatically when rate limiter locks an IP.
- Speed membrane: block deltas arriving faster than human typing speed (<2s interval).
  Automated scripts submit in milliseconds; humans take seconds.
- HMAC attestation membrane: require signed token for high-impact actions
  (`quarantine`, `segment_network`, `disable_capability`).

**`care/api/server.py` — hardened server**
- HTTP middleware: payload size check before parsing, rate limit check, audit log on every request.
- Background canary task running on configurable interval (default 60s).
- `/security/status` — operator visibility: rate limiter stats, locked IPs, canary snapshot,
  audit log tail, runtime counters.
- `/security/lockdown/release` — manual lockdown release after operator review.
- Input validation wired into every endpoint via `_pipeline()`.

**Tests**
- 25 new security tests across `TestRateLimiter`, `TestAuditLog`, `TestInputValidator`,
  `TestLockdownMembrane`, `TestSecurityAPI`.
- `autouse` fixture resets rate limiter state between every test.
- Total: **80/80 passing**.

### Changed
- `care/api/server.py` — all endpoints now validate input before processing.
- `care/api/server.py` — `/apply` checks security membranes before any delta application.

### Configuration (new environment variables)
| Variable | Default | Description |
|---|---|---|
| `CARE_AUDIT_BACKEND` | `file` | `file` \| `redis` \| `memory` |
| `CARE_AUDIT_FILE` | `/tmp/care_audit.jsonl` | Audit log file path |
| `CARE_AUDIT_REDIS_URL` | `redis://localhost:6379` | Redis URL for audit backend |
| `CARE_VALIDATION_MODE` | `lab` | `lab` \| `prod` |
| `CARE_MAX_PAYLOAD_BYTES` | `65536` | Max request payload size |
| `CARE_LOCKDOWN_ENABLED` | `true` | Enable lockdown membrane |
| `CARE_MIN_DELTA_INTERVAL` | `2.0` | Min seconds between deltas (speed membrane) |
| `CARE_ATTESTATION_SECRET` | `` | HMAC secret for high-impact delta attestation |
| `CARE_CANARY_ENABLED` | `true` | Enable self-monitoring canary |
| `CARE_CANARY_INTERVAL` | `60` | Canary check interval (seconds) |
| `CARE_CANARY_RISK_DELTA` | `0.25` | Risk delta threshold for canary alert |

---

## [0.1.0] — 2026-04-06


Initial release.

### Added

**Core pipeline**
- `state_encoder.py` — raw infrastructure state → numerical vector x ∈ ℝⁿ
  - Supports dict, list, scalar, and string inputs
  - Flattens nested dicts; caps at configurable `max_state_dim`
- `risk_potential.py` — three built-in risk potentials:
  - `QuadraticRisk` — R(x) = ‖x‖² (baseline / debug)
  - `PrivilegeRisk` — weighted quadratic, privileged dims penalised 5×
  - `BlastRadiusRisk` — quadratic form with connectivity coupling matrix
  - Registry + `register_potential()` for custom potentials
- `curvature.py` — exact ∇R and H(x) via three selectable backends:
  - `numpy` (finite differences, always available)
  - `jax` (forward-over-reverse AD)
  - `jax-xla` (hcderiv one-pass XLA, requires `hcderiv[jax]>=0.4.0`)
  - `CurvatureResult` dataclass with gradient, Hessian, eigenvalues, eigenvectors
- `ridge.py` — UAG Theorem 4 implementation:
  - Softest / stiffest eigenvector identification
  - Kramers escape proxy: ∝ exp(−2ΔR / |λ_min|)
  - Severity classification: `safe` / `watch` / `critical`
  - `RidgeAnalysis` dataclass
- `recommend.py` — 5-rule hardening engine:
  - Rule 1: Critical severity → quarantine
  - Rule 2: Negative eigenvalues → network segmentation
  - Rule 3: Soft direction in high-risk dims → privilege reduction
  - Rule 4: High gradient component → rate limiting
  - Rule 5: High overall risk → MFA enforcement
  - `HardeningAction` dataclass with UAG theorem links

**API layer** (`care/api/`)
- FastAPI server with 7 endpoints: `/health`, `/encode`, `/risk`, `/curvature`,
  `/escape-route`, `/recommend`, `/apply`
- Pydantic v2 request/response schemas
- CORS middleware enabled
- Dry-run mode for `/apply` when Constitutional OS not configured

**Adapters** (`care/adapters/`)
- `aws_iam.py` — IAM feature encoder (8 security dimensions) + boto3 live fetch stub
- `k8s.py` — Kubernetes security posture encoder (8 dims) + kubernetes-client stub
- `constitutional_os.py` — delta proposal, membrane checking, apply/rollback
  - Checksum-verified deltas
  - Quarantine auto-blocked (requires human approval)
  - Full rollback support

**Membrane layer** (`care/membranes/`)
- `policies.py` — 3 built-in membrane policies + extensible rule framework:
  - `NO_AUTO_QUARANTINE`
  - `NO_SILENT_PRIVILEGE_ESCALATION`
  - `REQUIRE_REASON`
- `deltas.py` — `Delta` dataclass with UUID, timestamp, checksum, reversible flag
  - In-memory audit log (swap for Redis/Postgres in production)
  - `rollback()` generates inverse delta

**Visualisation** (`care/viz/`)
- `eigenvalue_spectrum()` — bar chart coloured by stability (green/amber/red)
- `risk_over_time()` — line chart of R(x) across snapshots
- `curvature_basin_2d()` — 2D contour of risk potential over a grid
- `before_after()` — side-by-side eigenvalue comparison showing hardening effect

**Examples**
- `examples/iam_demo/iam_state.json` — sample AWS IAM state
- `examples/iam_demo/run_demo.py` — full demo with `--local` and API modes
- `examples/configs/demo_config.yaml` — environment variable reference

**Configuration**
- All settings via environment variables / `.env` file
- `CARE_CURVATURE_BACKEND`, `CARE_COS_ENABLED`, `CARE_COS_ENDPOINT`,
  `CARE_SOFT_LAMBDA`, `CARE_HIGH_RISK`, `CARE_MAX_STATE_DIM`

**Packaging**
- `pyproject.toml` with optional extras: `[viz]`, `[jax]`, `[hcderiv]`, `[dev]`, `[all]`
- Entry point: `care-server`

### Theoretical basis
- Unified Attractor Grammar, Byte (2026). DOI: 10.5281/zenodo.19394700
- hcderiv v0.4.0, Byte (2026). DOI: 10.5281/zenodo.19433812
- Constitutional OS, Byte (2026). Preprint.

---

## Roadmap

### [0.2.0] — planned

- [ ] Real hcderiv integration with `jax-xla` backend end-to-end tests
- [ ] Live AWS IAM adapter with boto3 (full policy graph encoding)
- [ ] Live Kubernetes adapter with kubernetes-python client
- [ ] Persistent audit log (SQLite / Redis backends)
- [ ] `/audit` endpoint to query delta history
- [ ] GitHub Actions CI with test matrix (Python 3.10 / 3.11 / 3.12)

### [0.3.0] — planned

- [ ] Constitutional OS Runtime integration (live delta application)
- [ ] Web UI dashboard (risk timeline + curvature basin viewer)
- [ ] Multi-state trajectory tracking (risk drift over time)
- [ ] curvopt / CAO integration for gradient-based hardening optimisation
- [ ] Dockerfile + docker-compose for reproducible deployment
