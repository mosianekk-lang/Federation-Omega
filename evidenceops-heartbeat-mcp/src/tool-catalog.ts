import { z } from "zod";
import { HEARTBEAT_EMIT_SCOPE, HEARTBEAT_READ_SCOPE } from "./config.js";
import { emitInputSchema } from "./backend.js";

export const TOOL_NAMES = ["heartbeat_status", "search", "fetch", "heartbeat_emit"] as const;
export type ToolName = (typeof TOOL_NAMES)[number];

export const TOOL_POLICIES = Object.freeze({
  heartbeat_status: Object.freeze({ scope: HEARTBEAT_READ_SCOPE, readOnly: true, effectful: false }),
  search: Object.freeze({ scope: HEARTBEAT_READ_SCOPE, readOnly: true, effectful: false }),
  fetch: Object.freeze({ scope: HEARTBEAT_READ_SCOPE, readOnly: true, effectful: false }),
  heartbeat_emit: Object.freeze({ scope: HEARTBEAT_EMIT_SCOPE, readOnly: false, effectful: true }),
}) satisfies Readonly<Record<ToolName, { scope: string; readOnly: boolean; effectful: boolean }>>;

export const searchInputSchema = z.object({
  query: z.string()
    .trim()
    .min(1)
    .max(160)
    .regex(/^[A-Za-z0-9_.:/ -]+$/)
    .regex(/[A-Za-z0-9]/),
}).strict();
export const fetchInputSchema = z.object({
  id: z.string()
    .trim()
    .regex(/^(?:emitter\/[A-Z][A-Z0-9_.:-]{2,63}|heartbeat\/sha256:[a-f0-9]{64})$/),
}).strict();
export { emitInputSchema };

export function requiredScopeForBody(body: unknown): string | undefined {
  if (!body || typeof body !== "object" || Array.isArray(body)) return undefined;
  const candidate = body as { method?: unknown; params?: { name?: unknown } };
  if (candidate.method !== "tools/call" || !candidate.params || typeof candidate.params.name !== "string") {
    return undefined;
  }
  const name = candidate.params.name;
  return Object.prototype.hasOwnProperty.call(TOOL_POLICIES, name)
    ? TOOL_POLICIES[name as ToolName].scope
    : undefined;
}

export function oauthSecurityScheme(scope: string): Readonly<Record<string, unknown>> {
  return Object.freeze({ type: "oauth2", scopes: Object.freeze([scope]) });
}

export function toolMeta(scope: string): Readonly<Record<string, unknown>> {
  const schemes = Object.freeze([oauthSecurityScheme(scope)]);
  return Object.freeze({ securitySchemes: schemes });
}
