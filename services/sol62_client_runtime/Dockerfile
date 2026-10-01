FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 fuse \
    && mkdir -p /home/fuse/sol62-client-state /home/fuse/sol62-strategy-state /home/fuse/fuse-host-state \
    && chown -R fuse:fuse /home/fuse
COPY services/sol62_client_runtime/requirements.txt /tmp/sol62-requirements.txt
RUN pip install --no-cache-dir -r /tmp/sol62-requirements.txt
COPY . /app
USER fuse
ENV SOL62_CLIENT_HOST=0.0.0.0 \
    SOL62_CLIENT_PORT=8762 \
    SOL62_CLIENT_ROOT=/home/fuse/sol62-client-state \
    SOL62_STRATEGY_ROOT=/home/fuse/sol62-strategy-state \
    FUSE_GENESIS_HOST_ROOT=/home/fuse/fuse-host-state
EXPOSE 8762
CMD ["python","-m","services.sol62_client_runtime"]
