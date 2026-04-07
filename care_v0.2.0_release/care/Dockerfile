# ─── Stage 1: builder ──────────────────────────────────────────────────────
# Installs all dependencies into a venv that we copy into the final image.
# Keeps the final layer free of build tools (pip, setuptools, wheel).
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tooling only in this stage
RUN pip install --no-cache-dir pip==24.0 wheel setuptools

# Layer-cache: copy dependency manifests first so this layer is only
# rebuilt when requirements actually change, not when source changes.
COPY requirements.txt pyproject.toml ./
COPY care/__init__.py care/

# Install runtime deps into an isolated venv
RUN python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /venv/bin/pip install --no-cache-dir matplotlib

# Install the package itself (without dev extras)
COPY care/ ./care/
COPY examples/ ./examples/
RUN /venv/bin/pip install --no-cache-dir -e ".[viz]"


# ─── Stage 2: runtime ──────────────────────────────────────────────────────
# Minimal image: no build tools, no pip, no wheel.
# Only the venv, the source, and a non-root user.
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="CARE — Curvature-Aware Risk Engine"
LABEL org.opencontainers.image.description="Attractor-based infrastructure hardening via UAG curvature analysis"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/zetta55byte/care"

# Runtime system deps only: curl for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

WORKDIR /app

# Copy venv and source from builder — nothing else
COPY --from=builder /venv /venv
COPY --from=builder /build/care ./care
COPY --from=builder /build/examples ./examples

# Non-root user: prevents privilege escalation inside the container,
# which is itself a Constitutional OS membrane enforcement at the OS level.
RUN useradd -m -u 1000 -s /bin/bash care && \
    chown -R care:care /app
USER care

# PATH must include the venv so uvicorn is findable
ENV PATH="/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # CARE defaults — all overrideable at runtime
    CARE_HOST=0.0.0.0 \
    CARE_PORT=8000 \
    CARE_CURVATURE_BACKEND=numpy \
    CARE_COS_ENABLED=false \
    CARE_COS_ENDPOINT=http://cos-runtime:9000 \
    CARE_SOFT_LAMBDA=1.0 \
    CARE_HIGH_RISK=10.0 \
    CARE_MAX_STATE_DIM=64 \
    LOG_LEVEL=INFO

EXPOSE 8000

# Healthcheck: fast /health endpoint, tolerates 10s startup
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${CARE_PORT}/health || exit 1

# Entrypoint: uvicorn with one worker per container
# (scale horizontally, not vertically)
ENTRYPOINT ["uvicorn", "care.api.server:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
