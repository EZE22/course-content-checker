# Shared base: Python, environment settings, and the package installed from source.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install .

# Test stage: adds the tests and the dev extra, and runs pytest by default.
FROM base AS test
COPY tests ./tests
COPY examples ./examples
RUN pip install ".[dev]"
CMD ["pytest"]

# Runtime stage: the default image. Runs as a non-root user with a writable history volume.
FROM base AS runtime
RUN useradd --create-home --shell /usr/sbin/nologin checker \
    && mkdir /data \
    && chown checker:checker /data
ENV CHECKER_DB=/data/history.db
USER checker
ENTRYPOINT ["content-checker"]
CMD ["check", "/config/settings.json"]
