# Federation Respawn Runtime — Deployment & ChatGPT Binding

## Target

Deploy `respawn/mcp_server.py` as a remote Streamable HTTP MCP endpoint. The default endpoint is `/mcp` on `$PORT` (8080 in the container).

The source repository remains a quarantined source plane. Do **not** add deployment workflows here unless they are explicitly admitted by the Federation GitHub Airlock. Production deployment belongs in a separate private execution plane or a provider-native deployment process.

## Runtime configuration

Set these values as runtime configuration/secrets rather than committing provider identifiers into this public repository:

- `FEDERATION_DRIVE_FOLDER_ID`
- `FEDERATION_CONTROL_DOC_ID`
- `FEDERATION_SYNC_BUS_SHEET_ID`
- `BUBBLES_BIBLE_ID`
- `LEX_ADVOCATE_BIBLE_ID`
- `FEDERATION_BIBLIOGRAPHY_REGISTRY_ID`
- `FEDERATION_RESPAWN_STATE` (defaults to `/data/runtime_state.json` in the container)

Provider credentials must be supplied through the hosting platform's workload identity / secret mechanism, never committed to source.

## Container build

From the `respawn/` directory:

```bash
docker build -t federation-respawn .
docker run --rm -p 8080:8080 federation-respawn
```

Connect an MCP Inspector or client to:

```text
http://localhost:8080/mcp
```

## Cloud Run-shaped deployment

A compatible container host can run the image as long as it accepts inbound HTTPS and passes `$PORT`.

Example provider-native sequence (illustrative until executed and read back from the provider):

```bash
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/REPOSITORY/federation-respawn .
gcloud run deploy federation-respawn \
  --image REGION-docker.pkg.dev/PROJECT/REPOSITORY/federation-respawn \
  --region REGION \
  --platform managed \
  --set-env-vars FEDERATION_RESPAWN_STATE=/data/runtime_state.json
```

Production state should use a durable store or provider adapter rather than relying on container-local `/data` storage.

## ChatGPT custom app binding

ChatGPT custom MCP apps connect to a **remote MCP server**. Once the runtime has a provider-verified HTTPS URL, create a custom app in ChatGPT developer mode and point it to:

```text
https://YOUR-VERIFIED-HOST/mcp
```

The read-only startup surface is deliberately usable independently of mutation tools:

- `bootstrap_spawn`
- `already_solved`
- `search`
- `fetch`
- `federation_health`

`publish_delta` is a write tool. Its availability depends on the ChatGPT plan/workspace permissions and the app's approved tool snapshot. It must not be represented as available when the client only permits read/fetch actions.

For a Pro account, design the ChatGPT binding around the read/fetch bootstrap path; provider-side writes can continue through authorised connector/automation routes until full MCP write support is available to the account/workspace.

## Deterministic invocation contract

Until ChatGPT exposes a native `chat opened` event to this runtime, use the human-facing invocation as the event source:

- `Load Bubbles`
- `Load Lex Advocate`
- equivalent registered-system load command

The invoked system should call `bootstrap_spawn` before substantive new work, then run `already_solved` for the current objective.

## Proof gates

Do not mark the runtime as deployed until all of the following exist:

1. provider-native service/deployment identifier;
2. provider-reported ready/healthy state;
3. HTTPS `/mcp` reachability;
4. successful MCP initialization/tool-list readback;
5. successful `federation_health` call;
6. successful `bootstrap_spawn` call for at least Bubbles and Lex Advocate;
7. ChatGPT custom-app connection readback, if ChatGPT binding is in scope.

A source commit, Dockerfile, or deployment command is **not** deployment proof.
