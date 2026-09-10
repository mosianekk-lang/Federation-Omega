FROM python:3.12.11-slim@sha256:47ae396f09c1303b8653019811a8498470603d7ffefc29cb07c88f1f8cb3d19f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md requirements-relay.lock ./
COPY src ./src
RUN python -m pip install --require-hashes -r requirements-relay.lock \
    && python -m pip install --no-deps .

USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["federation-windows-relay"]
