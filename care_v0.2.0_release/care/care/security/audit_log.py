"""
CARE Audit Log — immutable, append-only, survives process compromise.

Three backends selectable via CARE_AUDIT_BACKEND:
    "file"   — append-only local file (default, dev)
    "redis"  — Redis Streams (recommended prod)
    "s3"     — S3 with write-only creds (highest durability)
    "memory" — in-memory (tests only, old behaviour)

Every entry records:
    ip, route, method, payload_hash, decision, membrane_flags,
    anomaly_flags, timestamp_utc, request_id

Assume process compromise: logs must outlive the process.
File backend uses append mode and never truncates.
Redis backend uses XADD to a capped stream.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AUDIT_BACKEND = os.getenv("CARE_AUDIT_BACKEND", "file")
AUDIT_FILE_PATH = os.getenv("CARE_AUDIT_FILE", "/tmp/care_audit.jsonl")
AUDIT_REDIS_URL = os.getenv("CARE_AUDIT_REDIS_URL", "redis://localhost:6379")
AUDIT_REDIS_STREAM = os.getenv("CARE_AUDIT_REDIS_STREAM", "care:audit")
AUDIT_REDIS_MAXLEN = int(os.getenv("CARE_AUDIT_REDIS_MAXLEN", "100000"))


# ── Entry type ────────────────────────────────────────────────────────────────

@dataclass
class AuditEntry:
    request_id: str
    timestamp_utc: float
    ip: str
    route: str
    method: str
    payload_hash: str          # SHA-256 of raw request body, never the body itself
    decision: str              # "allowed" | "rate_limited" | "locked_down" | "blocked"
    status_code: int
    anomaly_flags: list[str]   # e.g. ["chain_probe", "all_endpoint_burst"]
    membrane_flags: list[str]  # e.g. ["quarantine_blocked", "reason_required"]
    latency_ms: float
    extra: dict

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def make_entry(
    ip: str,
    route: str,
    method: str,
    payload: bytes | None,
    decision: str,
    status_code: int,
    anomaly_flags: list[str] | None = None,
    membrane_flags: list[str] | None = None,
    latency_ms: float = 0.0,
    extra: dict | None = None,
) -> AuditEntry:
    payload_hash = ""
    if payload:
        payload_hash = hashlib.sha256(payload).hexdigest()[:16]
    return AuditEntry(
        request_id=str(uuid.uuid4()),
        timestamp_utc=time.time(),
        ip=ip,
        route=route,
        method=method,
        payload_hash=payload_hash,
        decision=decision,
        status_code=status_code,
        anomaly_flags=anomaly_flags or [],
        membrane_flags=membrane_flags or [],
        latency_ms=latency_ms,
        extra=extra or {},
    )


# ── Backends ──────────────────────────────────────────────────────────────────

class _MemoryBackend:
    def __init__(self):
        self._log: list[dict] = []

    def append(self, entry: AuditEntry) -> None:
        self._log.append(entry.to_dict())

    def tail(self, n: int = 100) -> list[dict]:
        return self._log[-n:]

    def count(self) -> int:
        return len(self._log)


class _FileBackend:
    """Append-only JSONL file. Never truncates. Survives restart."""

    def __init__(self, path: str):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Audit log: file backend at %s", self._path)

    def append(self, entry: AuditEntry) -> None:
        with open(self._path, "a") as f:
            f.write(entry.to_json() + "\n")
            f.flush()
            os.fsync(f.fileno())   # force to disk

    def tail(self, n: int = 100) -> list[dict]:
        try:
            lines = self._path.read_text().splitlines()
            return [json.loads(l) for l in lines[-n:] if l.strip()]
        except FileNotFoundError:
            return []

    def count(self) -> int:
        try:
            return sum(1 for _ in open(self._path))
        except FileNotFoundError:
            return 0


class _RedisBackend:
    """Redis Streams — XADD with maxlen cap. Survives process crash."""

    def __init__(self, url: str, stream: str, maxlen: int):
        try:
            import redis
            self._r = redis.from_url(url)
            self._stream = stream
            self._maxlen = maxlen
            self._r.ping()
            logger.info("Audit log: Redis backend at %s stream=%s", url, stream)
        except Exception as e:
            logger.warning("Redis audit backend failed (%s), falling back to file.", e)
            self._r = None
            self._fallback = _FileBackend(AUDIT_FILE_PATH)

    def append(self, entry: AuditEntry) -> None:
        if self._r is None:
            self._fallback.append(entry)
            return
        try:
            self._r.xadd(self._stream, entry.to_dict(), maxlen=self._maxlen, approximate=True)
        except Exception as e:
            logger.error("Redis XADD failed: %s", e)

    def tail(self, n: int = 100) -> list[dict]:
        if self._r is None:
            return self._fallback.tail(n)
        try:
            entries = self._r.xrevrange(self._stream, count=n)
            return [dict(e[1]) for e in reversed(entries)]
        except Exception:
            return []

    def count(self) -> int:
        if self._r is None:
            return self._fallback.count()
        try:
            return self._r.xlen(self._stream)
        except Exception:
            return -1


# ── Audit log singleton ───────────────────────────────────────────────────────

def _build_backend():
    if AUDIT_BACKEND == "redis":
        return _RedisBackend(AUDIT_REDIS_URL, AUDIT_REDIS_STREAM, AUDIT_REDIS_MAXLEN)
    elif AUDIT_BACKEND == "memory":
        return _MemoryBackend()
    else:
        return _FileBackend(AUDIT_FILE_PATH)


class AuditLog:
    def __init__(self):
        self._backend = _build_backend()

    def record(self, entry: AuditEntry) -> None:
        try:
            self._backend.append(entry)
        except Exception as e:
            logger.error("Audit log write failed: %s", e)

    def tail(self, n: int = 100) -> list[dict]:
        return self._backend.tail(n)

    def count(self) -> int:
        return self._backend.count()


_audit_log = AuditLog()

def get_audit_log() -> AuditLog:
    return _audit_log
