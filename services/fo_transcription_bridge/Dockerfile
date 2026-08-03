FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app.py.gz.b64 transcript.py ./
RUN python - <<'PYCODE'
import base64, gzip
from pathlib import Path
Path('app.py').write_bytes(gzip.decompress(base64.b64decode(Path('app.py.gz.b64').read_text().strip())))
PYCODE

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD exec gunicorn --bind :${PORT} --workers 1 --threads 8 --timeout 1800 app:app
