FROM python:3.12-slim AS test
WORKDIR /app
COPY . /app
RUN python -m compileall -q seb tests
RUN python -m unittest discover -s tests -q

FROM gcr.io/distroless/python3-debian13:nonroot
WORKDIR /app
COPY --from=test --chown=nonroot:nonroot /app /app
ENV PYTHONUNBUFFERED=1 SEB_HOST=0.0.0.0 SEB_PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD ["/usr/bin/python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"]
ENTRYPOINT ["/usr/bin/python3"]
CMD ["-m", "seb.api"]

