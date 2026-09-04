FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN python -m compileall -q seb tests
ENV PYTHONUNBUFFERED=1 SEB_HOST=0.0.0.0 SEB_PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"
CMD ["python", "-m", "seb.api"]

