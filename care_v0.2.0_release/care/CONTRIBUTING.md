# Contributing to CARE

Thank you for your interest in contributing. CARE is a research-grade
engineering project grounded in the Unified Attractor Grammar — contributions
that extend the theory, improve the engineering, or add real adapter coverage
are all welcome.

---

## Setup

```bash
git clone https://github.com/<your-org>/care
cd care
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the package in editable mode with all dev dependencies
(pytest, ruff, mypy, matplotlib).

---

## Running tests

```bash
pytest
```

Tests live in `tests/`. Add a test for every new module you introduce.
The CI gate requires 100% of existing tests to pass.

---

## Code style

CARE uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
ruff check care/
ruff format care/
```

Line length: 100. Target: Python 3.10+.

Type annotations are required on all public functions and class methods.
`mypy` is run in CI but failures are currently warnings, not blockers.

---

## Pull request guidelines

1. **One concern per PR.** Bug fix, feature, or refactor — not all three.
2. **Tests required.** New modules need at least one test. New endpoints need
   a schema test and a pipeline integration test.
3. **UAG link required for new risk rules.** Every new rule in `recommend.py`
   must include a `uag_link` field citing the relevant theorem.
4. **No secrets.** Never commit credentials, API keys, kubeconfigs, or `.pem`
   files. The `.gitignore` covers common cases but double-check.
5. **Membrane policies are conservative by default.** If you add a new policy
   to `membranes/policies.py`, it should block unless explicitly permitted —
   not permit unless explicitly blocked.

---

## Areas where contributions are especially welcome

| Area | What's needed |
|---|---|
| `adapters/aws_iam.py` | Full IAM policy graph encoding (not just summary stats) |
| `adapters/k8s.py` | RBAC graph, NetworkPolicy coverage, PSA enforcement check |
| `models/risk_potential.py` | Domain-specific potentials (model capability risk, network blast radius) |
| `adapters/constitutional_os.py` | Live COS Runtime integration |
| `viz/plots.py` | Plotly interactive versions of existing matplotlib plots |
| `tests/` | Integration tests for the FastAPI endpoints |

---

## Questions

Open a GitHub Discussion or file an issue with the `question` label.
For security issues, please do not open a public issue — email the maintainer
directly (address in `pyproject.toml`).
