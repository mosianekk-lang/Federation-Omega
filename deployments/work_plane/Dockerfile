FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
RUN pip install --no-cache-dir google-auth==2.40.3 requests==2.32.5
COPY federation /app/federation
COPY respawn /app/respawn
USER 65532:65532
CMD ["python","-m","respawn.work_plane_cloud_service_v1"]
