FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY federation /app/federation
COPY services/fuse_mobile_gateway /app/services/fuse_mobile_gateway
COPY services/gemini_gateway /app/services/gemini_gateway

USER 65532:65532
CMD ["uvicorn", "services.fuse_mobile_gateway.app:app", "--host", "0.0.0.0", "--port", "8080"]
