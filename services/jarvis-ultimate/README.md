# JARVIS Ultimate Federation v1.0

A governed interactive intelligence system built on Google ADK 2.0 and the Google GenAI SDK, with a deterministic authority kernel, scientific principles, Federation capability routing, adaptive learning, circuit breaking, browser/CLI interfaces and Cloud Run packaging.

## Truth boundary

The code is a production foundation. It does not inherit ChatGPT connector credentials. Gemini becomes `VERIFIED_LIVE` only when `GEMINI_API_KEY`, `GOOGLE_API_KEY`, or Google ADC is present. Drive, Gmail, Sheets and Calendar remain `ADAPTER_REQUIRED` until their own incremental OAuth/service-account readback passes. Current Federation WIF is known blocked by `invalid_target`; this release does not claim live Cloud Run deployment.

## T20 Alpha–Omega execution governor

`T20-AO-OMEGA-SCIENTIST-1.0` bounds each JARVIS execution attempt to 1,200 seconds without weakening the quality gates:

- 0–12 minutes: execute the highest information- and decision-value independent lanes;
- at 12 minutes: split any remaining monolith and isolate blockers;
- at 15 minutes: stop scope expansion and fan in the material streams;
- at 18 minutes: allow only verification, semantic readback and release;
- at 20 minutes: terminate the attempt and emit an honest terminal receipt.

The three paths are primary delivery, protective assurance, and failure recovery. The six bounded streams are source truth, implementation, testing, adversarial risk, semantic readback, and method learning. A deadline does not convert partial work into completion. External provider latency and approval cannot be forced; unresolved external gates must be reported as a bounded result with an executable next route.

Omega-Scientist may propose a lower target only after the cycle meets every quality gate. Speed gains remain shadow candidates until regression confirms that evidence fidelity, safety, auditability and output quality did not fall.

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
- `GET /v1/execution-policy`
- `POST /v1/chat`
- `POST /v1/plan`
- `POST /v1/authorize`
- `POST /v1/cycle-review`

## Architecture

`interactive surface → JARVIS orchestrator → Formation kernel → T20 Alpha–Omega governor → capability fabric → Gemini/Federation adapter → semantic readback → hash-chained learning → stop/reform`

Only one sovereign executor exists. The 50-horizon twin forecasts and challenges; it cannot grant authority or act independently. Scientific laws, theorems, systems laws, heuristics and kung-fu philosophy are explicitly typed so metaphors cannot masquerade as physics.

## Google access

Use incremental OAuth for personal Workspace data and service accounts for bounded server-to-server work. Each adapter declares exact scopes and remains disabled when a scope is absent. Google tokens belong in Secret Manager or encrypted storage, never GitHub or Drive.

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
