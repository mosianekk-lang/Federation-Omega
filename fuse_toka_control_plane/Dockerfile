FROM python:3.12-slim
WORKDIR /app
COPY main.py /app/main.py
RUN useradd --create-home fuse && chown -R fuse:fuse /app
USER fuse
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python","/app/main.py"]
