# AEGIS-Ω v0.3.0 supply-chain control

Production source uses exact direct dependency pins rather than open version ranges.
The locally exercised core pins are FastAPI 0.128.2, Pydantic 2.13.4,
Uvicorn 0.48.0, Setuptools 82.0.1 and pytest 9.0.2. Provider adapters pin
Firestore 2.30.0, Pub/Sub 2.40.0 and Cloud Storage 3.13.1 in the source contract.

This strengthens replayability but does **not** claim a hermetic transitive lock by
itself. The provider canary must record the resolved container image digest and
provider build/run evidence before provider deployment maturity can advance.
