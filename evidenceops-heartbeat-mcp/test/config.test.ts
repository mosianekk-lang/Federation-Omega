import assert from "node:assert/strict";
import test from "node:test";
import { loadConfig } from "../src/config.js";

const completeEnv: NodeJS.ProcessEnv = {
  HEARTBEAT_BACKEND_URL: "https://heartbeat-private.example.com",
  HEARTBEAT_BACKEND_AUDIENCE: "https://heartbeat-private.example.com",
  HEARTBEAT_INTERNAL_AUTH_VALUE: "s".repeat(40),
  MCP_RESOURCE_URL: "https://heartbeat-mcp.example.com/mcp",
  OAUTH_ISSUER: "https://identity.example.com",
  OAUTH_JWKS_URI: "https://identity.example.com/.well-known/jwks.json",
  OAUTH_JWT_ALGORITHMS: "RS256",
};

test("configuration fails closed when a required setting is absent", () => {
  const env = { ...completeEnv };
  delete env.OAUTH_JWKS_URI;
  assert.throws(() => loadConfig(env), /OAUTH_JWKS_URI/);
});

test("configuration rejects insecure endpoints and short internal tokens", () => {
  assert.throws(
    () => loadConfig({ ...completeEnv, MCP_RESOURCE_URL: "http://heartbeat-mcp.example.com/mcp" }),
    /must use https/,
  );
  assert.throws(
    () => loadConfig({ ...completeEnv, HEARTBEAT_INTERNAL_AUTH_VALUE: "too-short" }),
    /at least 32/,
  );
});

test("configuration derives protected-resource metadata and retains exact audience URL", () => {
  const config = loadConfig(completeEnv);
  assert.equal(config.backendUrl.href, "https://heartbeat-private.example.com/");
  assert.equal(config.backendAudience, "https://heartbeat-private.example.com");
  assert.equal(config.resourceUrl.href, "https://heartbeat-mcp.example.com/mcp");
  assert.equal(
    config.resourceMetadataUrl.href,
    "https://heartbeat-mcp.example.com/.well-known/oauth-protected-resource/mcp",
  );
  assert.deepEqual(config.oauthAlgorithms, ["RS256"]);
});

test("private backend audience must be the exact normalized HTTPS service origin", () => {
  assert.throws(
    () => loadConfig({
      ...completeEnv,
      HEARTBEAT_BACKEND_AUDIENCE: "https://other-private.example.com",
    }),
    /must exactly match/,
  );
  assert.throws(
    () => loadConfig({
      ...completeEnv,
      HEARTBEAT_BACKEND_AUDIENCE: "https://heartbeat-private.example.com/v1/status",
    }),
    /without a path/,
  );
  assert.throws(
    () => loadConfig({
      ...completeEnv,
      HEARTBEAT_BACKEND_AUDIENCE: "https://user:secret@heartbeat-private.example.com",
    }),
    /must not contain credentials/,
  );
  assert.throws(
    () => loadConfig({
      ...completeEnv,
      HEARTBEAT_BACKEND_AUDIENCE: "http://heartbeat-private.example.com",
    }),
    /must use https/,
  );
  assert.throws(
    () => loadConfig({
      ...completeEnv,
      HEARTBEAT_BACKEND_URL: "https://heartbeat-private.example.com/api",
      HEARTBEAT_BACKEND_AUDIENCE: "https://heartbeat-private.example.com/api",
    }),
    /without a path/,
  );
  assert.throws(
    () => loadConfig({
      ...completeEnv,
      HEARTBEAT_BACKEND_AUDIENCE: "https://heartbeat-private.example.com/?target=other",
    }),
    /must not contain a query/,
  );

  const normalized = loadConfig({
    ...completeEnv,
    HEARTBEAT_BACKEND_URL: "https://HEARTBEAT-private.example.com/",
    HEARTBEAT_BACKEND_AUDIENCE: "https://heartbeat-private.example.com",
  });
  assert.equal(normalized.backendAudience, "https://heartbeat-private.example.com");
});
