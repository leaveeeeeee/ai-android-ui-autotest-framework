FROM python:3.13-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REPORTS_ROOT=/app/artifacts/reports

RUN apt-get update && \
    apt-get install -y --no-install-recommends android-tools-adb && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY config ./config
COPY docs ./docs
COPY examples ./examples
COPY tests ./tests
COPY framework ./framework
COPY scripts ./scripts
COPY assets ./assets

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install . && \
    adduser --disabled-password --gecos "" --uid 10001 appuser && \
    chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "pytest", "tests", "-m", "not device"]
