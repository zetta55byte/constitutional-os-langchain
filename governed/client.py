import requests
from .config import GOVERNANCE_URL


def governance_check(action: dict) -> dict:
    """Send an action to the Constitutional OS governance substrate."""
    resp = requests.post(GOVERNANCE_URL, json={"action": action})
    resp.raise_for_status()
    return resp.json()
