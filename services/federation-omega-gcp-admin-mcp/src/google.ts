import {GoogleAuth, Impersonated} from "google-auth-library";
import {config} from "./config.js";
import {safeGoogleApiError} from "./googleError.js";

export type GoogleAuthMode = "read" | "mutation";
export type GoogleRequestInit = RequestInit & {googleAuthMode?: GoogleAuthMode};

const readScopes = [
  "https://www.googleapis.com/auth/cloud-platform.read-only",
  "https://www.googleapis.com/auth/script.projects.readonly",
];

const mutationScopes = [
  "https://www.googleapis.com/auth/cloud-platform",
  "https://www.googleapis.com/auth/script.projects",
];

export async function accessToken(mode: GoogleAuthMode = "read"): Promise<string> {
  const scopes = mode === "mutation" ? mutationScopes : readScopes;
  const auth = new GoogleAuth({scopes});
  let client = await auth.getClient();

  const targetPrincipal = mode === "mutation"
    ? config.mutationImpersonateServiceAccount
    : config.readImpersonateServiceAccount;
  if (targetPrincipal) {
    client = new Impersonated({
      sourceClient: client,
      targetPrincipal,
      targetScopes: scopes,
      lifetime: 1800,
    });
  }

  const result = await client.getAccessToken();
  const token = typeof result === "string" ? result : result?.token;
  if (!token) throw new Error("NO_GOOGLE_ACCESS_TOKEN");
  return token;
}

export async function googleJson<T>(
  url: string,
  init: GoogleRequestInit = {}
): Promise<{status: number; body: T}> {
  const {googleAuthMode = "read", ...requestInit} = init;
  const token = await accessToken(googleAuthMode);
  const controller = new AbortController();
  const timeoutMs = Number.isFinite(config.googleRequestTimeoutMs)
    ? Math.max(1000, Math.min(config.googleRequestTimeoutMs, 120000)) : 30000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, {
      ...requestInit,
      signal: requestInit.signal ?? controller.signal,
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": "application/json",
        ...(requestInit.headers ?? {}),
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`GOOGLE_API_TIMEOUT: ${url}`);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
  const text = await response.text();
  let body: unknown = {};
  try { body = text ? JSON.parse(text) : {}; } catch { body = {raw: text}; }
  if (!response.ok) {
    throw safeGoogleApiError(response.status, text);
  }
  return {status: response.status, body: body as T};
}
