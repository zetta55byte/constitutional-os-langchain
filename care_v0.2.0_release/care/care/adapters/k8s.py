"""
Kubernetes state adapter.

Encodes cluster security posture into a CARE state vector.

Feature dimensions:
    0  n_privileged_pods      — pods running as root / privileged
    1  n_exposed_services      — NodePort / LoadBalancer services
    2  n_default_ns_workloads  — workloads in 'default' namespace (bad hygiene)
    3  n_cluster_admin_bindings— ClusterRoleBindings to cluster-admin
    4  n_secrets               — number of secrets (sprawl proxy)
    5  n_host_network_pods     — pods with hostNetwork=true
    6  n_namespaces            — namespace count (segmentation health)
    7  rbac_enabled            — 1.0 if RBAC is on, 0.0 otherwise
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def encode_k8s_state(k8s_state: dict[str, Any]) -> np.ndarray:
    """Convert a K8s security posture dict into a CARE feature vector."""
    def g(key: str, default: float = 0.0) -> float:
        return float(k8s_state.get(key, default))

    features = np.array([
        g("privileged_pods"),
        g("exposed_services"),
        g("default_ns_workloads"),
        g("cluster_admin_bindings"),
        g("secrets_count"),
        g("host_network_pods"),
        g("namespace_count"),
        1.0 - g("rbac_disabled", 0.0),   # 1.0 = RBAC on = good
    ], dtype=float)

    logger.debug("K8s state encoded: %s", features)
    return features


def fetch_k8s_state() -> dict[str, Any]:
    """
    Attempt to fetch live K8s state via the kubernetes Python client.
    Falls back gracefully if the client is not installed.
    """
    try:
        from kubernetes import client, config as k8s_config  # type: ignore[import]
        k8s_config.load_incluster_config()
        v1 = client.CoreV1Api()
        pods = v1.list_pod_for_all_namespaces().items

        n_privileged = sum(
            1 for p in pods
            for c in (p.spec.containers or [])
            if c.security_context and c.security_context.privileged
        )

        return {
            "privileged_pods": n_privileged,
            "secrets_count": len(v1.list_secret_for_all_namespaces().items),
            "namespace_count": len(v1.list_namespace().items),
        }
    except ImportError:
        logger.warning("kubernetes client not installed. Using empty K8s state.")
        return {}
    except Exception as e:
        logger.warning("K8s fetch failed: %s. Using empty state.", e)
        return {}
