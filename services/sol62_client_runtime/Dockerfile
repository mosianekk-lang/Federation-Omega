FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 fuse
COPY . /app
RUN pip install --no-cache-dir fastapi uvicorn pydantic
USER fuse
ENV PYTHONUNBUFFERED=1 SOL62_CLIENT_HOST=0.0.0.0 SOL62_CLIENT_PORT=8762
EXPOSE 8762
CMD ["python","-m","services.sol62_client_runtime"]
