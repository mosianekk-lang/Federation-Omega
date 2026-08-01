FROM python:3.12-slim
WORKDIR /app
COPY evidenceops/runtime_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY evidenceops/runtime_service/main.py ./main.py
COPY evidenceops/runtime/ACTIVE_SOVEREIGN_TRANSLATOR.json ./ACTIVE_SOVEREIGN_TRANSLATOR.json
ENV EVIDENCEOPS_ACTIVE_MANIFEST=/app/ACTIVE_SOVEREIGN_TRANSLATOR.json
ENV EVIDENCEOPS_STATE_DB=/tmp/evidenceops/state.db
EXPOSE 8080
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8080"]
