# JARVIS Ultimate Federation v1.0

A governed interactive intelligence system built on Google ADK 2.0 and the Google GenAI SDK, with a deterministic authority kernel, scientific principles, Federation capability routing, adaptive learning, circuit breaking, browser/CLI interfaces and Cloud Run packaging.

## Truth boundary

The code is a production foundation. It does not inherit ChatGPT connector credentials. Gemini becomes `VERIFIED_LIVE` only when `GEMINI_API_KEY`, `GOOGLE_API_KEY`, or Google ADC is present. Drive, Gmail, Sheets and Calendar remain `ADAPTER_REQUIRED` until their own incremental OAuth/service-account readback passes. Current Federation WIF is known blocked by `invalid_target`; this release does not claim live Cloud Run deployment.

## Run

```bash
python -m jarvis.main "Map my next objective"
JARVIS_API_TOKEN=local-only python -m jarvis.main --serve --port 8080
```

Open `http://127.0.0.1:8080`. Production must set `JARVIS_API_TOKEN` and use Secret Manager; never commit credentials.

## Interfaces

- `GET /health`
- `GET /v1/capabilities`
- `GET /v1/principles`
- `POST /v1/chat`
- `POST /v1/plan`
- `POST /v1/authorize`

## Architecture

`interactive surface → JARVIS orchestrator → Formation kernel → capability fabric → Gemini/Federation adapter → semantic readback → hash-chained learning → stop/reform`

Only one sovereign executor exists. The 50-horizon twin forecasts and challenges; it cannot grant authority or act independently. Scientific laws, theorems, systems laws, heuristics and kung-fu philosophy are explicitly typed so metaphors cannot masquerade as physics.

## Google access

Use incremental OAuth for personal Workspace data and service accounts for bounded server-to-server work. Each adapter declares exact scopes and remains disabled when a scope is absent. Google tokens belong in Secret Manager or encrypted storage, never GitHub or Drive.

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
