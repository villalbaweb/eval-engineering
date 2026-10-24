# Build context is the REPO ROOT (compose sets it): the image needs backend/ and evals/.
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PATH="/app/backend/.venv/bin:$PATH"
WORKDIR /app/backend

# Extra provider/driver packages to bake in, e.g. --build-arg UV_EXTRAS="--extra postgres --extra anthropic"
ARG UV_EXTRAS="--extra postgres"
# 1) dependencies only (cached until pyproject/uv.lock change)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project $UV_EXTRAS
# 2) project
COPY backend/src ./src
RUN uv sync --frozen --no-dev $UV_EXTRAS
# 3) default experiment content (compose bind-mounts ./evals over this in development)
COPY evals /app/evals
ENV EVALS_DIR=/app/evals DATA_DIR=/app/data
VOLUME ["/app/data"]

# --- dev image: adds pytest/ruff/mypy; used by `docker compose --profile test run --rm tests` ---
FROM base AS dev
ARG UV_EXTRAS="--extra postgres"
RUN uv sync --frozen $UV_EXTRAS
COPY backend/tests ./tests

# --- runtime ---
FROM base AS runtime
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
CMD ["uvicorn", "eval_harness.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
