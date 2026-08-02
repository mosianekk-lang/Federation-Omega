const REQUIRED_KEYS = [
  "HEARTBEAT_BACKEND_URL",
  "HEARTBEAT_BACKEND_AUDIENCE",
  "HEARTBEAT_INTERNAL_AUTH_VALUE",
  "MCP_RESOURCE_URL",
  "OAUTH_ISSUER",
  "OAUTH_JWKS_URI",
  "OAUTH_JWT_ALGORITHMS",
] as const;

const ALLOWED_JWT_ALGORITHMS = new Set(["RS256", "PS256", "ES256"]);

export const HEARTBEAT_READ_SCOPE = "heartbeat:read";
export const HEARTBEAT_EMIT_SCOPE = "heartbeat:emit";

export interface GatewayConfig {
  readonly port: number;
  readonly backendUrl: URL;
  readonly backendAudience: string;
  readonly internalAuthValue: string;
  readonly resourceUrl: URL;
  readonly resourceMetadataUrl: URL;
  readonly oauthIssuer: string;
  readonly oauthJwksUri: URL;
  readonly oauthAlgorithms: readonly string[];
  readonly backendTimeoutMs: number;
  readonly maxBackendResponseBytes: number;
}

function required(env: NodeJS.ProcessEnv, key: (typeof REQUIRED_KEYS)[number]): string {
  const value = env[key]?.trim();
  if (!value) throw new Error(`Missing required configuration: ${key}`);
  return value;
}

function httpsUrl(raw: string, key: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`${key} must be an absolute URL`);
  }
  if (parsed.protocol !== "https:") throw new Error(`${key} must use https`);
  if (parsed.username || parsed.password || parsed.hash) {
    throw new Error(`${key} must not contain credentials or a fragment`);
  }
  return parsed;
}

function serviceOrigin(raw: string, key: string): string {
  const parsed = httpsUrl(raw, key);
  if (parsed.search) throw new Error(`${key} must not contain a query`);
  if (parsed.pathname !== "/") {
    throw new Error(`${key} must identify the service origin without a path`);
  }
  return parsed.origin;
}

function positiveInteger(raw: string | undefined, fallback: number, key: string): number {
  if (raw === undefined || raw.trim() === "") return fallback;
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new Error(`${key} must be a positive integer`);
  }
  return parsed;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): GatewayConfig {
  for (const key of REQUIRED_KEYS) required(env, key);

  const backendOrigin = serviceOrigin(required(env, "HEARTBEAT_BACKEND_URL"), "HEARTBEAT_BACKEND_URL");
  const backendAudience = serviceOrigin(
    required(env, "HEARTBEAT_BACKEND_AUDIENCE"),
    "HEARTBEAT_BACKEND_AUDIENCE",
  );
  if (backendAudience !== backendOrigin) {
    throw new Error("HEARTBEAT_BACKEND_AUDIENCE must exactly match the normalized HEARTBEAT_BACKEND_URL origin");
  }
  const backendUrl = new URL(backendOrigin);

  const resourceUrl = httpsUrl(required(env, "MCP_RESOURCE_URL"), "MCP_RESOURCE_URL");
  if (!resourceUrl.pathname.endsWith("/mcp")) {
    throw new Error("MCP_RESOURCE_URL must identify the public /mcp endpoint");
  }

  const issuerUrl = httpsUrl(required(env, "OAUTH_ISSUER"), "OAUTH_ISSUER");
  if (issuerUrl.search) throw new Error("OAUTH_ISSUER must not contain a query");
  const oauthIssuer = issuerUrl.href.replace(/\/$/, "");

  const oauthJwksUri = httpsUrl(required(env, "OAUTH_JWKS_URI"), "OAUTH_JWKS_URI");
  const algorithms = required(env, "OAUTH_JWT_ALGORITHMS")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (algorithms.length === 0 || algorithms.some((value) => !ALLOWED_JWT_ALGORITHMS.has(value))) {
    throw new Error("OAUTH_JWT_ALGORITHMS must be a comma-separated subset of RS256, PS256, ES256");
  }

  const internalAuthValue = required(env, "HEARTBEAT_INTERNAL_AUTH_VALUE");
  if (internalAuthValue.length < 32) {
    throw new Error("HEARTBEAT_INTERNAL_AUTH_VALUE must contain at least 32 characters");
  }

  const metadataUrl = new URL(resourceUrl);
  metadataUrl.pathname = "/.well-known/oauth-protected-resource/mcp";
  metadataUrl.search = "";

  return Object.freeze({
    port: positiveInteger(env.PORT, 8080, "PORT"),
    backendUrl,
    backendAudience,
    internalAuthValue,
    resourceUrl,
    resourceMetadataUrl: metadataUrl,
    oauthIssuer,
    oauthJwksUri,
    oauthAlgorithms: Object.freeze([...new Set(algorithms)]),
    backendTimeoutMs: positiveInteger(env.HEARTBEAT_BACKEND_TIMEOUT_MS, 10_000, "HEARTBEAT_BACKEND_TIMEOUT_MS"),
    maxBackendResponseBytes: positiveInteger(
      env.HEARTBEAT_MAX_BACKEND_RESPONSE_BYTES,
      2_000_000,
      "HEARTBEAT_MAX_BACKEND_RESPONSE_BYTES",
    ),
  });
}
