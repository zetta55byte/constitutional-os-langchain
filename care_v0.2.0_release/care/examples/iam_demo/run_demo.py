"""
CARE IAM Hardening Demo
=======================
Demonstrates the full CARE pipeline on an AWS IAM state snapshot.

Usage:
    # Start the server first (in another terminal):
    uvicorn care.api.server:app --reload

    # Then run this script:
    python examples/iam_demo/run_demo.py

Or run end-to-end without a server (local mode):
    python examples/iam_demo/run_demo.py --local
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Allow running from project root ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

IAM_STATE_FILE = Path(__file__).parent / "iam_state.json"
BASE_URL = "http://localhost:8000"


# ── Local pipeline (no server needed) ────────────────────────────────────────

def run_local(state: dict) -> None:
    from care.models.state_encoder import encode_state
    from care.models.risk_potential import get_potential
    from care.models.curvature import curvature_info
    from care.models.ridge import analyse_ridge, summarise as ridge_summary
    from care.models.recommend import recommend_actions
    from care.viz.plots import eigenvalue_spectrum, before_after

    print("\n" + "=" * 60)
    print("  CARE — Curvature-Aware Risk Engine  |  IAM Demo (local)")
    print("=" * 60)

    potential = get_potential("privilege")
    x = encode_state(state)
    print(f"\n[1] State encoded: dim={len(x)}, x={x[:6].round(3)}...")

    result = curvature_info(x, potential, backend="numpy")
    print(f"\n[2] Risk R(x) = {result.risk:.4f}")
    print(f"    Gradient norm = {__import__('numpy').linalg.norm(result.gradient):.4f}")
    print(f"    Eigenvalues: {result.eigenvalues[:6].round(4)}")

    ridge = analyse_ridge(result)
    print(f"\n[3] Ridge analysis:")
    print(f"    Softest direction: λ_min = {ridge.softest_eigenvalue:.4f}  (index {ridge.softest_index})")
    print(f"    Kramers escape proxy = {ridge.kramers_proxy:.4f}")
    print(f"    Severity = {ridge.severity.upper()}")
    print(f"    Negative eigenvalues: {ridge.negative_eigenvalues}")

    actions = recommend_actions(result, ridge, raw_state=state)
    print(f"\n[4] Hardening recommendations ({len(actions)} action(s)):")
    for i, a in enumerate(actions, 1):
        print(f"\n    [{i}] {a.action_type.upper()} — {a.target}")
        print(f"        {a.from_state} → {a.to_state}")
        print(f"        Priority: {a.priority}")
        print(f"        Reason: {a.reason[:80]}...")
        print(f"        UAG: {a.uag_link[:70]}...")

    # ── Simulate hardening: reduce admin_users and mfa_disabled ──────────────
    hardened_state = dict(state)
    hardened_state["admin_users"] = max(1, state["admin_users"] - 3)
    hardened_state["mfa_disabled_users"] = 0
    hardened_state["inactive_access_keys"] = 0

    x2 = encode_state(hardened_state)
    result2 = curvature_info(x2, potential, backend="numpy")
    ridge2 = analyse_ridge(result2)

    print(f"\n[5] After hardening simulation:")
    print(f"    Risk: {result.risk:.4f} → {result2.risk:.4f}  ({result2.risk - result.risk:+.4f})")
    print(f"    λ_min: {ridge.softest_eigenvalue:.4f} → {ridge2.softest_eigenvalue:.4f}")
    print(f"    Severity: {ridge.severity} → {ridge2.severity}")

    # ── Save plots ────────────────────────────────────────────────────────────
    out_dir = Path(__file__).parent
    try:
        fig1 = eigenvalue_spectrum(result.eigenvalues[:8], title="Eigenvalue spectrum — before hardening")
        fig1.savefig(out_dir / "eigenvalues_before.png", dpi=150, bbox_inches="tight")

        fig2 = before_after(result.eigenvalues[:8], result2.eigenvalues[:8])
        fig2.savefig(out_dir / "eigenvalues_before_after.png", dpi=150, bbox_inches="tight")

        print(f"\n[6] Plots saved to {out_dir}/")
    except ImportError:
        print("\n[6] matplotlib not installed — skipping plots.")

    print("\n" + "=" * 60)
    print("  Demo complete.")
    print("=" * 60 + "\n")


# ── API mode (server must be running) ─────────────────────────────────────────

def run_api(state: dict) -> None:
    try:
        import httpx
    except ImportError:
        print("httpx not installed. Run: pip install httpx")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  CARE — Curvature-Aware Risk Engine  |  IAM Demo (API)")
    print(f"  Server: {BASE_URL}")
    print("=" * 60)

    payload = {"state": state, "potential": "privilege"}
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    def post(endpoint: str, label: str) -> dict:
        r = client.post(endpoint, json=payload)
        r.raise_for_status()
        data = r.json()
        print(f"\n[{label}] POST {endpoint}")
        print(f"    {json.dumps(data, indent=2)[:300]}...")
        return data

    post("/encode",       "1 Encode")
    post("/risk",         "2 Risk")
    post("/curvature",    "3 Curvature")
    post("/escape-route", "4 Escape route")
    post("/recommend",    "5 Recommend")
    post("/apply",        "6 Apply (dry-run)")

    print("\n" + "=" * 60)
    print("  Demo complete.")
    print("=" * 60 + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CARE IAM demo")
    parser.add_argument("--local", action="store_true",
                        help="Run locally without a server")
    args = parser.parse_args()

    with open(IAM_STATE_FILE) as f:
        state = json.load(f)

    if args.local:
        run_local(state)
    else:
        run_api(state)
