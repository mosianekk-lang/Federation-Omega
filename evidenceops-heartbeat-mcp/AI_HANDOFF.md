# AI handoff

Start by reading `README.md`, `FORMATION_SPEC.md`, and the canonical Python
schemas in `evidenceops/heartbeat_api/schemas.py`.

Safe verification order:

1. `npm ci`
2. `npm run check`
3. `npm test`
4. `npm run build`
5. Compare gateway request/response validators with the Python API schemas.

Do not deploy, bind IAM, create secrets, register a ChatGPT app, or change OAuth
configuration without a new proof-gated authorization cycle. Never add a static
production bearer bypass, forward the inbound OAuth token, use
`FO_ADMIN_TOKEN`, or add a second effectful tool. If the MCP SDK changes, first
verify raw `tools/list` still emits top-level and mirrored `securitySchemes`.
