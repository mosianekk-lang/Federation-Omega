FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 FC_DB_PATH=/tmp/frontier-convergence.db
WORKDIR /app
COPY frontier_convergence /app/frontier_convergence
USER 65532:65532
CMD ["python", "-m", "frontier_convergence.service"]
