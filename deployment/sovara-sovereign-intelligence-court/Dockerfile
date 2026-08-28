FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements-sovara-mcp.txt /app/requirements-sovara-mcp.txt
RUN pip install --no-cache-dir -r /app/requirements-sovara-mcp.txt

COPY ops/sovara_openrouter_code_eval_v1.py /app/ops/sovara_openrouter_code_eval_v1.py
COPY ops/sovara_sovereign_intelligence_court_v2.py /app/ops/sovara_sovereign_intelligence_court_v2.py
COPY ops/sovara_sovereign_mcp_v2.py /app/ops/sovara_sovereign_mcp_v2.py
COPY ops/sovara_gcs_mission_store_v1.py /app/ops/sovara_gcs_mission_store_v1.py
COPY ao_harmonic_v3 /app/ao_harmonic_v3

RUN useradd --create-home --uid 10001 sovara && chown -R sovara:sovara /app
USER sovara

EXPOSE 8080
CMD ["python", "/app/ops/sovara_sovereign_mcp_v2.py"]
