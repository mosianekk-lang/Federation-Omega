FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
RUN addgroup --system jarvis && adduser --system --ingroup jarvis jarvis \
    && mkdir -p /var/lib/jarvis && chown -R jarvis:jarvis /var/lib/jarvis
ENV PORT=8080
ENV JARVIS_STATE_DIR=/var/lib/jarvis
ENV PYTHONUNBUFFERED=1
USER jarvis
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=2))['ok']"]
CMD ["python", "-m", "jarvis.main", "--serve"]
