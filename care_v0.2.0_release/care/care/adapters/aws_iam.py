"""
AWS IAM state adapter.

Fetches IAM policy data and encodes it into a CARE state vector.

Real usage requires boto3 and AWS credentials. The stub below works
with a pre-fetched policy dict (e.g. loaded from iam_state.json).

Feature engineering rationale (maps to risk dimensions):
    0  n_users              — more users = larger attack surface
    1  n_admin_users        — admins = high-risk, soft curvature dimension
    2  n_policies           — policy sprawl = harder to audit
    3  n_overpermissioned   — policies with Action:* or Resource:*
    4  n_inactive_keys      — stale credentials = easy escape route
    5  n_mfa_disabled       — MFA off = low ridge height
    6  cross_account_trusts — lateral movement risk
    7  n_roles              — role proliferation
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def encode_iam_state(iam_state: dict[str, Any]) -> np.ndarray:
    """
    Convert an IAM state dict into a CARE feature vector.

    Expected keys (all optional, defaults to 0):
        users, admin_users, policies, overpermissioned_policies,
        inactive_access_keys, mfa_disabled_users, cross_account_trusts, roles
    """
    def g(key: str, default: float = 0.0) -> float:
        return float(iam_state.get(key, default))

    features = np.array([
        g("user_count"),
        g("admin_users"),
        g("policies"),
        g("overpermissioned_policies"),
        g("inactive_access_keys"),
        g("mfa_disabled_users"),
        g("cross_account_trusts"),
        g("roles"),
    ], dtype=float)

    logger.debug("IAM state encoded: %s", features)
    return features


def fetch_iam_state() -> dict[str, Any]:
    """
    Attempt to fetch live IAM state via boto3.
    Falls back gracefully if boto3 is not available.
    """
    try:
        import boto3  # type: ignore[import]
        iam = boto3.client("iam")

        users = iam.list_users()["Users"]
        n_users = len(users)

        # Count admins (simplified: users attached to AdministratorAccess)
        n_admin = 0
        for u in users:
            policies = iam.list_attached_user_policies(UserName=u["UserName"])
            for p in policies["AttachedPolicies"]:
                if "Administrator" in p["PolicyName"]:
                    n_admin += 1

        return {
            "user_count": n_users,
            "admin_users": n_admin,
            "policies": len(iam.list_policies(Scope="Local")["Policies"]),
        }
    except ImportError:
        logger.warning("boto3 not installed. Using empty IAM state.")
        return {}
    except Exception as e:
        logger.warning("AWS IAM fetch failed: %s. Using empty state.", e)
        return {}
