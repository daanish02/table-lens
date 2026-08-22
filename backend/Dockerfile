# Multi-stage build: a heavier "builder" stage resolves dependencies via uv
# into a venv, then only that venv + the app source + the lockfile get
# copied into a lean runtime stage that runs everything through `uv run`,
# same as in dev. Keeps compiler toolchains out of the final image.

FROM python:3.11-slim AS builder

# uv needs a C toolchain available for any dependency that doesn't ship a
# manylinux wheel for this platform; kept only in this stage.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependency layer first so `docker build` can reuse it whenever only
# application code changes below.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

FROM python:3.11-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# uv.lock + pyproject.toml come along so `uv run` can verify the venv
# matches the lockfile at startup, same check it does in dev.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/app /app/app
COPY --chown=app:app pyproject.toml uv.lock ./

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# The logger writes to <two levels up from app/utils/logger.py>/logs — that
# resolves to /app/logs here; must exist and be writable by the non-root user.
RUN mkdir -p /app/logs && chown app:app /app/logs

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD uv run --frozen python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3)" || exit 1

CMD ["uv", "run", "--frozen", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
