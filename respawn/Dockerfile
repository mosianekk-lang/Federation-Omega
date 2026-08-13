FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY bootstrap_service.py federation_manifest.json mcp_server.py ./

RUN useradd --create-home --uid 10001 federation && \
    mkdir -p /data && chown -R federation:federation /app /data

USER federation
ENV FEDERATION_RESPAWN_STATE=/data/runtime_state.json

EXPOSE 8080

CMD ["python", "mcp_server.py"]
