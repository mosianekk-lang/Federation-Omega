import assert from "node:assert/strict";
import test from "node:test";
import {
  SignJWT,
  createLocalJWKSet,
  exportJWK,
  generateKeyPair,
} from "jose";
import { InvalidTokenError } from "@modelcontextprotocol/sdk/server/auth/errors.js";
import { JwtOAuthVerifier } from "../src/oauth.js";
import { testConfig } from "./helpers.js";

test("JWT verifier enforces signature, issuer, audience, expiry and extracts scopes", async () => {
  const { privateKey, publicKey } = await generateKeyPair("RS256");
  const jwk = await exportJWK(publicKey);
  jwk.kid = "test-key";
  jwk.alg = "RS256";
  const config = testConfig();
  const verifier = new JwtOAuthVerifier(config, createLocalJWKSet({ keys: [jwk] }));
  const token = await new SignJWT({ scope: "heartbeat:read heartbeat:emit", client_id: "chatgpt-client" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(config.oauthIssuer)
    .setAudience(config.resourceUrl.href)
    .setSubject("owner-123")
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(privateKey);

  const auth = await verifier.verifyAccessToken(token);
  assert.equal(auth.clientId, "chatgpt-client");
  assert.deepEqual(auth.scopes, ["heartbeat:emit", "heartbeat:read"]);
  assert.equal(auth.resource?.href, config.resourceUrl.href);

  const wrongAudience = await new SignJWT({ scope: "heartbeat:read" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(config.oauthIssuer)
    .setAudience("https://wrong.example.com/mcp")
    .setSubject("owner-123")
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(privateKey);
  await assert.rejects(() => verifier.verifyAccessToken(wrongAudience), InvalidTokenError);

  const audienceArray = await new SignJWT({ scope: "heartbeat:read" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(config.oauthIssuer)
    .setAudience([config.resourceUrl.href, "https://other.example.com/mcp"])
    .setSubject("owner-123")
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(privateKey);
  await assert.rejects(() => verifier.verifyAccessToken(audienceArray), InvalidTokenError);

  const wrongIssuer = await new SignJWT({ scope: "heartbeat:read" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer("https://wrong-issuer.example.com")
    .setAudience(config.resourceUrl.href)
    .setSubject("owner-123")
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(privateKey);
  await assert.rejects(() => verifier.verifyAccessToken(wrongIssuer), InvalidTokenError);

  const now = Math.floor(Date.now() / 1000);
  const expired = await new SignJWT({ scope: "heartbeat:read" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(config.oauthIssuer)
    .setAudience(config.resourceUrl.href)
    .setSubject("owner-123")
    .setIssuedAt(now - 120)
    .setExpirationTime(now - 60)
    .sign(privateKey);
  await assert.rejects(() => verifier.verifyAccessToken(expired), InvalidTokenError);

  const missingExpiry = await new SignJWT({ scope: "heartbeat:read" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(config.oauthIssuer)
    .setAudience(config.resourceUrl.href)
    .setSubject("owner-123")
    .setIssuedAt()
    .sign(privateKey);
  await assert.rejects(() => verifier.verifyAccessToken(missingExpiry), InvalidTokenError);

  const missingSubject = await new SignJWT({ scope: "heartbeat:read" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(config.oauthIssuer)
    .setAudience(config.resourceUrl.href)
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(privateKey);
  await assert.rejects(() => verifier.verifyAccessToken(missingSubject), InvalidTokenError);

  const attacker = await generateKeyPair("RS256");
  const wrongSignature = await new SignJWT({ scope: "heartbeat:read" })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(config.oauthIssuer)
    .setAudience(config.resourceUrl.href)
    .setSubject("owner-123")
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(attacker.privateKey);
  await assert.rejects(() => verifier.verifyAccessToken(wrongSignature), InvalidTokenError);
});
