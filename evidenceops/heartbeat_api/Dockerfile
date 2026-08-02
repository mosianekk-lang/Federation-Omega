FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY evidenceops/heartbeat_api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN groupadd --system heartbeat && useradd --system --gid heartbeat --home-dir /app heartbeat
COPY --chown=heartbeat:heartbeat evidenceops /app/evidenceops
USER heartbeat
CMD ["sh", "-c", "exec uvicorn evidenceops.heartbeat_api.service:app --host 0.0.0.0 --port ${PORT} --proxy-headers --no-server-header"]
