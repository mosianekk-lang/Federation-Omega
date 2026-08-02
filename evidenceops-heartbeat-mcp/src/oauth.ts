import type { AuthInfo } from "@modelcontextprotocol/sdk/server/auth/types.js";
import type { OAuthTokenVerifier } from "@modelcontextprotocol/sdk/server/auth/provider.js";
import { InvalidTokenError } from "@modelcontextprotocol/sdk/server/auth/errors.js";
import { createRemoteJWKSet, jwtVerify, type JWTPayload, type JWTVerifyGetKey } from "jose";
import type { GatewayConfig } from "./config.js";

function parseScopes(payload: JWTPayload): string[] {
  const values = new Set<string>();
  if (typeof payload.scope === "string") {
    for (const scope of payload.scope.split(/\s+/)) if (scope) values.add(scope);
  }
  const scp = payload.scp;
  if (Array.isArray(scp)) {
    for (const scope of scp) if (typeof scope === "string" && scope) values.add(scope);
  }
  return [...values].sort();
}

function clientId(payload: JWTPayload): string {
  const candidates = [payload.client_id, payload.azp, payload.sub];
  const value = candidates.find((candidate) => typeof candidate === "string" && candidate.length > 0);
  if (typeof value !== "string") throw new Error("Access token has no client identifier");
  return value;
}

export class JwtOAuthVerifier implements OAuthTokenVerifier {
  private readonly jwks: JWTVerifyGetKey;

  constructor(private readonly config: GatewayConfig, jwks?: JWTVerifyGetKey) {
    this.jwks = jwks ?? createRemoteJWKSet(config.oauthJwksUri, {
        cooldownDuration: 30_000,
        timeoutDuration: 5_000,
      });
  }

  async verifyAccessToken(token: string): Promise<AuthInfo> {
    try {
      const { payload } = await jwtVerify(token, this.jwks, {
        issuer: this.config.oauthIssuer,
        audience: this.config.resourceUrl.href,
        algorithms: [...this.config.oauthAlgorithms],
        clockTolerance: 5,
      });
      if (payload.aud !== this.config.resourceUrl.href) {
        throw new Error("Access token audience must be the exact MCP resource URL");
      }
      if (typeof payload.exp !== "number") throw new Error("Access token has no expiration");
      if (typeof payload.sub !== "string" || payload.sub.length === 0) {
        throw new Error("Access token has no subject");
      }
      return {
        token,
        clientId: clientId(payload),
        scopes: parseScopes(payload),
        expiresAt: payload.exp,
        resource: new URL(this.config.resourceUrl),
        extra: { subject: payload.sub },
      };
    } catch {
      throw new InvalidTokenError("Access token validation failed");
    }
  }
}
