FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 \
    GOOGLE_CLOUD_PROJECT=sov-hybrid-suite GOOGLE_CLOUD_LOCATION=global \
    GEMINI_MODEL=gemini-2.5-flash
WORKDIR /app
COPY services/gemini_gateway /app/services/gemini_gateway
USER 65532:65532
CMD ["python", "-m", "services.gemini_gateway.app"]
