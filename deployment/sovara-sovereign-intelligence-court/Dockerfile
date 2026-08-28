FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOVARA_STATE_DIR=/var/lib/sovara/sovereign-intelligence-court

WORKDIR /app

COPY requirements-sovara-mcp.txt /app/requirements-sovara-mcp.txt
RUN pip install --no-cache-dir -r /app/requirements-sovara-mcp.txt

COPY ops/sovara_openrouter_code_eval_v1.py /app/sovara_openrouter_code_eval_v1.py
COPY ops/sovara_sovereign_intelligence_court_v2.py /app/sovara_sovereign_intelligence_court_v2.py
COPY ops/sovara_sovereign_mcp_v2.py /app/sovara_sovereign_mcp_v2.py

RUN useradd --create-home --uid 10001 sovara && \
    mkdir -p /var/lib/sovara/sovereign-intelligence-court && \
    chown -R sovara:sovara /var/lib/sovara

USER sovara
EXPOSE 8000

CMD ["python", "/app/sovara_sovereign_mcp_v2.py"]
