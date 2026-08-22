import crypto from "node:crypto";

export function safeGoogleApiError(status: number, responseText: string): Error {
  let reason = "REQUEST_FAILED";
  try {
    const parsed = JSON.parse(responseText) as {error?: {status?: unknown}};
    if (typeof parsed.error?.status === "string" && /^[A-Z0-9_]{1,80}$/.test(parsed.error.status)) {
      reason = parsed.error.status;
    }
  } catch {
    // Non-JSON bodies remain represented only by their digest.
  }
  const responseHash = crypto.createHash("sha256").update(responseText).digest("hex");
  return new Error(`GOOGLE_API_${status}:${reason}:response_sha256=${responseHash}`);
}
