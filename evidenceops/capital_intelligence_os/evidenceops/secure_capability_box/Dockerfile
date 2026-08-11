FROM python:3.12.11-slim@sha256:27f90d79cc85e9b7b2560063ef44fa0e9eaae7a7c3f5a9f74563065c5477cc24

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY secure_capability_box ./secure_capability_box
RUN pip install --no-cache-dir --requirement requirements.txt .
RUN python -m compileall -q secure_capability_box
USER 65532:65532
CMD ["sh", "-c", "exec uvicorn secure_capability_box.service:app --host 0.0.0.0 --port ${PORT} --proxy-headers --no-server-header"]
