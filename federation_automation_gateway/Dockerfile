FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app/federation_automation_gateway
RUN pip install --no-cache-dir -r /app/federation_automation_gateway/requirements.txt
ENV PYTHONPATH=/app
CMD exec gunicorn --chdir /app --bind :${PORT:-8080} --workers 2 --threads 8 --timeout 120 federation_automation_gateway.app:app
