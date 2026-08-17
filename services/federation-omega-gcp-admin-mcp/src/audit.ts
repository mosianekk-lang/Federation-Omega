import crypto from "node:crypto";
import {config} from "./config.js";

export type AuditRecord = {
  auditId: string;
  timestamp: string;
  action: string;
  inputHash: string;
  status: "DONE" | "FAILED";
  result?: unknown;
  error?: string;
};

export type PersistedAuditRecord = Omit<AuditRecord, "result"> & {
  result?: {
    redacted: true;
    resultHash: string;
    summary: Record<string, unknown>;
  };
};

function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${stable(item)}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? String(value);
}

function sha256(value: unknown): string {
  return crypto.createHash("sha256").update(stable(value)).digest("hex");
}

const SAFE_SUMMARY_KEYS = new Set([
  "status", "state", "proofBoundary", "scriptId", "projectId", "service",
  "revision", "buildId", "sha256", "sourceSha256", "currentSha256",
  "proposedSha256", "desiredSourceSha256", "verifiedSourceSha256",
  "changed", "currentFileCount", "proposedFileCount", "identifiersMatch",
  "backedUpAt", "capturedAt", "generatedAt",
]);

function isSafeScalar(value: unknown): value is string | number | boolean | null {
  return value === null || ["string", "number", "boolean"].includes(typeof value);
}

function sourceFileCount(value: unknown): number | undefined {
  if (!value || typeof value !== "object") return undefined;
  const files = (value as Record<string, unknown>).files;
  return Array.isArray(files) ? files.length : undefined;
}

function resultSummary(result: unknown): Record<string, unknown> {
  if (!result || typeof result !== "object") return {resultType: typeof result};
  const record = result as Record<string, unknown>;
  const summary: Record<string, unknown> = {};
  for (const key of SAFE_SUMMARY_KEYS) {
    const value = record[key];
    if (isSafeScalar(value)) summary[key] = value;
  }

  const directFileCount = sourceFileCount(record);
  if (directFileCount !== undefined) summary.fileCount = directFileCount;
  const contentFileCount = sourceFileCount(record.content);
  if (contentFileCount !== undefined) summary.fileCount = contentFileCount;

  for (const key of ["backup", "verified", "before", "after"] as const) {
    const value = record[key];
    if (!value || typeof value !== "object") continue;
    const nested = value as Record<string, unknown>;
    if (typeof nested.sha256 === "string") summary[`${key}Sha256`] = nested.sha256;
    if (typeof nested.sourceSha256 === "string") {
      summary[`${key}SourceSha256`] = nested.sourceSha256;
    }
    const fileCount = sourceFileCount(nested.content);
    if (fileCount !== undefined) summary[`${key}FileCount`] = fileCount;
  }
  return summary;
}

function safeError(error: string): string {
  const code = error.match(/\b[A-Z][A-Z0-9_]*(?::[A-Za-z0-9_.-]+)?\b/)?.[0]
    ?? "OPERATION_FAILED";
  return `${code} [detail_sha256=${sha256(error)}]`;
}

export function auditRecordForPersistence(record: AuditRecord): PersistedAuditRecord {
  const persisted: PersistedAuditRecord = {
    auditId: record.auditId,
    timestamp: record.timestamp,
    action: record.action,
    inputHash: record.inputHash,
    status: record.status,
  };
  if (record.result !== undefined) {
    persisted.result = {
      redacted: true,
      resultHash: sha256(record.result),
      summary: resultSummary(record.result),
    };
  }
  if (record.error) persisted.error = safeError(record.error);
  return persisted;
}

export async function audit(
  action: string,
  input: unknown,
  operation: () => Promise<unknown>
): Promise<AuditRecord> {
  const record: AuditRecord = {
    auditId: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    action,
    inputHash: crypto.createHash("sha256").update(stable(input)).digest("hex"),
    status: "DONE",
  };
  try {
    record.result = await operation();
  } catch (error) {
    record.status = "FAILED";
    record.error = error instanceof Error ? error.message : String(error);
  }

  const persistedRecord = auditRecordForPersistence(record);
  console.log(JSON.stringify({event: "FEDERATION_OMEGA_ADMIN_AUDIT", ...persistedRecord}));

  if (config.auditBucket) {
    try {
      const {Storage} = await import("@google-cloud/storage");
      const storage = new Storage();
      const name = `federation-omega-audit/${record.timestamp.slice(0,10)}/${record.auditId}.json`;
      await storage.bucket(config.auditBucket).file(name).save(JSON.stringify(persistedRecord, null, 2), {
        contentType: "application/json", resumable: false,
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      console.error(JSON.stringify({event: "FEDERATION_OMEGA_ADMIN_AUDIT_PERSISTENCE_FAILED",
        auditId: record.auditId, action, operationStatus: record.status, error: safeError(detail)}));
    }
  }
  return record;
}
