FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    SUPERIOR_LOGIC_DB=/tmp/superior_logic.db \
    SUPERIOR_LOGIC_AUTH_MODE=deny_mutations \
    APP_MODULE=superior_logic.secure_service:app

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY superior_logic ./superior_logic
COPY sol_61_runtime ./sol_61_runtime

CMD ["sh", "-c", "uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT}"]
