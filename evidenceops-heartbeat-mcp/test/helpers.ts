import type { GatewayConfig } from "../src/config.js";

export function testConfig(overrides: Partial<GatewayConfig> = {}): GatewayConfig {
  return {
    port: 8080,
    backendUrl: new URL("https://heartbeat-private.example.com"),
    backendAudience: "https://heartbeat-private.example.com",
    internalAuthValue: "x".repeat(48),
    resourceUrl: new URL("https://heartbeat-mcp.example.com/mcp"),
    resourceMetadataUrl: new URL("https://heartbeat-mcp.example.com/.well-known/oauth-protected-resource/mcp"),
    oauthIssuer: "https://identity.example.com",
    oauthJwksUri: new URL("https://identity.example.com/.well-known/jwks.json"),
    oauthAlgorithms: ["RS256"],
    backendTimeoutMs: 5_000,
    maxBackendResponseBytes: 100_000,
    ...overrides,
  };
}
