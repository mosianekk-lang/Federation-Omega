FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 cios
COPY evidenceops /app/evidenceops
USER 10001
CMD ["python", "-m", "evidenceops.capital_intelligence_os.verify_release"]
