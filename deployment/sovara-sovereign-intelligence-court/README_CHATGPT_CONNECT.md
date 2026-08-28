# ChatGPT connection target

After the persistent runtime is deployed and provider-read back, connect ChatGPT to the HTTPS Streamable HTTP MCP endpoint exposed by the SOVARA service.

The single intended user-facing tool is:

`SOVARA — external model review`

which maps to MCP tool `sovara_external_model_review`.

Connection itself is a separate provider/client event and must not be claimed merely because the MCP source exists.
