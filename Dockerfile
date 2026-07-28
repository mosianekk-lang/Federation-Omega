FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    SUPERIOR_LOGIC_DB=/tmp/superior_logic.db

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY superior_logic ./superior_logic

CMD ["sh", "-c", "uvicorn superior_logic.service:app --host 0.0.0.0 --port ${PORT}"]
