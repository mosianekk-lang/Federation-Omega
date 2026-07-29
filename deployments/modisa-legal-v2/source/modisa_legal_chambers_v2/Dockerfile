FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8421
WORKDIR /app
RUN groupadd --system modisa && useradd --system --gid modisa --home /app modisa
COPY pyproject.toml README.md ./
COPY modisa_v2 ./modisa_v2
COPY main.py agent.py ./
RUN pip install --no-cache-dir .
RUN mkdir -p /app/state /app/data /app/evidence_vault /app/backups && chown -R modisa:modisa /app
USER modisa
EXPOSE 8421
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT','8421') + '/health', timeout=4)"
CMD ["python", "main.py"]
