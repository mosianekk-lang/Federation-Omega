import { createPublicKey, timingSafeEqual, verify } from "node:crypto";

export class AuthenticationError extends Error {
  constructor(message, code = "AUTHENTICATION_FAILED") {
    super(message);
    this.name = "AuthenticationError";
    this.code = code;
  }
}

function constantTimeEqual(left, right) {
  const a = Buffer.from(String(left || ""), "utf8");
  const b = Buffer.from(String(right || ""), "utf8");
  return a.length === b.length && timingSafeEqual(a, b);
}

function decodePart(value) {
  return JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
}

function parseBearer(header) {
  const match = /^Bearer\s+(.+)$/i.exec(String(header || ""));
  return match ? match[1].trim() : "";
}

let jwkCache = { expiresAt: 0, keys: [] };

async function googleJwks(fetchImpl = fetch) {
  const now = Date.now();
  if (jwkCache.expiresAt > now && jwkCache.keys.length) return jwkCache.keys;
  const response = await fetchImpl("https://www.googleapis.com/oauth2/v3/certs", { headers: { accept: "application/json" } });
  if (!response.ok) throw new AuthenticationError("Google signing keys unavailable", "OIDC_KEYS_UNAVAILABLE");
  const body = await response.json();
  const cacheControl = response.headers.get("cache-control") || "";
  const maxAge = Number(/max-age=(\d+)/i.exec(cacheControl)?.[1] || 300);
  jwkCache = { expiresAt: now + Math.max(60, maxAge) * 1000, keys: body.keys || [] };
  return jwkCache.keys;
}

export async function verifyGoogleOidc(token, { audience, allowedPrincipals, fetchImpl = fetch, nowSeconds = Math.floor(Date.now() / 1000) }) {
  const parts = String(token || "").split(".");
  if (parts.length !== 3) throw new AuthenticationError("Malformed bearer token", "OIDC_MALFORMED");
  const header = decodePart(parts[0]);
  const claims = decodePart(parts[1]);
  if (header.alg !== "RS256" || !header.kid) throw new AuthenticationError("Unsupported bearer token", "OIDC_UNSUPPORTED");
  if (!["https://accounts.google.com", "accounts.google.com"].includes(claims.iss)) {
    throw new AuthenticationError("Unexpected token issuer", "OIDC_ISSUER_MISMATCH");
  }
  if (claims.aud !== audience) throw new AuthenticationError("Token audience mismatch", "OIDC_AUDIENCE_MISMATCH");
  if (!Number.isFinite(claims.exp) || claims.exp <= nowSeconds) throw new AuthenticationError("Bearer token expired", "OIDC_EXPIRED");
  if (Number.isFinite(claims.iat) && claims.iat > nowSeconds + 60) throw new AuthenticationError("Bearer token issued in the future", "OIDC_IAT_INVALID");
  const principal = String(claims.email || "").toLowerCase();
  if (!principal || !allowedPrincipals.has(principal)) throw new AuthenticationError("Caller principal is not allowlisted", "OIDC_PRINCIPAL_DENIED");
  const keys = await googleJwks(fetchImpl);
  const jwk = keys.find((item) => item.kid === header.kid && item.kty === "RSA");
  if (!jwk) throw new AuthenticationError("Signing key not found", "OIDC_KEY_NOT_FOUND");
  const valid = verify("RSA-SHA256", Buffer.from(`${parts[0]}.${parts[1]}`), createPublicKey({ key: jwk, format: "jwk" }), Buffer.from(parts[2], "base64url"));
  if (!valid) throw new AuthenticationError("Invalid bearer signature", "OIDC_SIGNATURE_INVALID");
  return { mode: "GOOGLE_OIDC", principal, subject: String(claims.sub || "") };
}

export async function authenticate(headers, env = process.env, fetchImpl = fetch) {
  const suppliedAdmin = String(headers["x-fo-admin-token"] || "");
  const configuredAdmin = String(env.ADMIN_TOKEN || "");
  if (configuredAdmin && suppliedAdmin && constantTimeEqual(suppliedAdmin, configuredAdmin)) {
    return { mode: "SECRET_MANAGER_TOKEN", principal: "fo-admin-token" };
  }
  const bearer = parseBearer(headers.authorization);
  const audience = String(env.OPERATOR_AUDIENCE || "").trim();
  const allowedPrincipals = new Set(String(env.OIDC_ALLOWED_PRINCIPALS || "").split(",").map((v) => v.trim().toLowerCase()).filter(Boolean));
  if (bearer && audience && allowedPrincipals.size) {
    return verifyGoogleOidc(bearer, { audience, allowedPrincipals, fetchImpl });
  }
  throw new AuthenticationError("A valid Secret Manager token or allowlisted Google OIDC identity is required", "TRUSTED_IDENTITY_REQUIRED");
}
