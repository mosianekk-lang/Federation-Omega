import crypto from "node:crypto";
import {
  assertAllowedProject, assertAllowedScript, assertAllowedService, assertApproval
} from "./config.js";
import {googleJson} from "./google.js";

export type Operation = {name?: string; done?: boolean; error?: unknown; response?: unknown};
type GoogleRequestInit = RequestInit & {googleAuthMode?: "read" | "mutation"};
export type GoogleCall = <T>(
  url: string, init?: GoogleRequestInit
) => Promise<{status: number; body: T}>;
const defaultGoogleCall = googleJson as GoogleCall;

function sha256(value: unknown): string {
  return crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

export function sourceSha256(content: {files: unknown[]}): string {
  return sha256({files: content.files});
}

function operationErrorCode(error: unknown): string {
  if (!error || typeof error !== "object") return "UNKNOWN";
  const record = error as Record<string, unknown>;
  const candidate = record.code ?? record.status ?? record.reason;
  return ["string", "number"].includes(typeof candidate)
    ? String(candidate).replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 80)
    : "UNKNOWN";
}

export function assertTerminalOperationSucceeded(operation: Operation): Operation {
  if (operation.done !== true) throw new Error("OPERATION_NOT_TERMINAL");
  if (operation.error !== undefined && operation.error !== null) {
    throw new Error(`OPERATION_FAILED:${operationErrorCode(operation.error)}`);
  }
  return operation;
}

async function pollOperation(
  name: string, timeoutMs = 180_000, call: GoogleCall = defaultGoogleCall
): Promise<Operation> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const {body} = await call<Operation>(
      `https://serviceusage.googleapis.com/v1/${name}`,
      {googleAuthMode: "mutation"}
    );
    if (body.done) return assertTerminalOperationSucceeded(body);
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
  throw new Error(`OPERATION_TIMEOUT: ${name}`);
}

export async function projectInfo(project: string) {
  assertAllowedProject(project);
  return (await googleJson(
    `https://cloudresourcemanager.googleapis.com/v3/projects/${encodeURIComponent(project)}`
  )).body;
}

export async function serviceStatus(project: string, service: string) {
  assertAllowedProject(project);
  assertAllowedService(service);
  return (await googleJson(
    `https://serviceusage.googleapis.com/v1/projects/${encodeURIComponent(project)}/services/${encodeURIComponent(service)}`
  )).body;
}

export async function enableService(
  project: string, service: string, approvalToken: string,
  call: GoogleCall = defaultGoogleCall
) {
  assertAllowedProject(project);
  assertAllowedService(service);
  assertApproval(approvalToken);
  const {body} = await call<Operation>(
    `https://serviceusage.googleapis.com/v1/projects/${encodeURIComponent(project)}/services/${encodeURIComponent(service)}:enable`,
    {method: "POST", body: "{}", googleAuthMode: "mutation"}
  );
  if (body.done) return assertTerminalOperationSucceeded(body);
  if (!body.name) throw new Error("ENABLE_OPERATION_NAME_MISSING");
  return pollOperation(body.name, 180_000, call);
}

export async function scriptMetadata(scriptId: string) {
  assertAllowedScript(scriptId);
  return (await googleJson(
    `https://script.googleapis.com/v1/projects/${encodeURIComponent(scriptId)}`
  )).body;
}

export async function scriptContent(scriptId: string, call: GoogleCall = defaultGoogleCall) {
  assertAllowedScript(scriptId);
  const content = (await call<{scriptId: string; files: unknown[]}>(
    `https://script.googleapis.com/v1/projects/${encodeURIComponent(scriptId)}/content`
  )).body;
  if (!Array.isArray(content.files)) throw new Error("SCRIPT_CONTENT_FILES_MISSING");
  return content;
}

export async function scriptBackup(scriptId: string, call: GoogleCall = defaultGoogleCall) {
  const content = await scriptContent(scriptId, call);
  const serialized = JSON.stringify(content);
  return {
    scriptId,
    sha256: crypto.createHash("sha256").update(serialized).digest("hex"),
    sourceSha256: sourceSha256(content),
    backedUpAt: new Date().toISOString(),
    content,
  };
}

export async function scriptDryRun(
  scriptId: string, proposedContent: unknown, call: GoogleCall = defaultGoogleCall
) {
  assertAllowedScript(scriptId);
  const current = await scriptContent(scriptId, call);
  const currentJson = JSON.stringify(current);
  const proposedJson = JSON.stringify(proposedContent);
  return {
    scriptId,
    currentSha256: crypto.createHash("sha256").update(currentJson).digest("hex"),
    proposedSha256: crypto.createHash("sha256").update(proposedJson).digest("hex"),
    changed: currentJson !== proposedJson,
    currentFileCount: Array.isArray(current.files) ? current.files.length : 0,
    proposedFileCount: Array.isArray((proposedContent as any)?.files)
      ? (proposedContent as any).files.length : 0,
  };
}

export async function scriptApply(
  scriptId: string,
  expectedCurrentSha256: string,
  proposedContent: {files: unknown[]},
  approvalToken: string,
  call: GoogleCall = defaultGoogleCall
) {
  assertAllowedScript(scriptId);
  assertApproval(approvalToken);
  const backup = await scriptBackup(scriptId, call);
  if (backup.sha256 !== expectedCurrentSha256) {
    throw new Error(`OPTIMISTIC_LOCK_FAILED: expected ${expectedCurrentSha256}, got ${backup.sha256}`);
  }
  const desiredSourceSha256 = sourceSha256(proposedContent);
  const result = (await call(
    `https://script.googleapis.com/v1/projects/${encodeURIComponent(scriptId)}/content`,
    {method: "PUT", body: JSON.stringify(proposedContent), googleAuthMode: "mutation"}
  )).body;
  const verified = await scriptBackup(scriptId, call);
  if (verified.sourceSha256 !== desiredSourceSha256) {
    throw new Error(
      `POST_WRITE_VERIFICATION_FAILED: expected ${desiredSourceSha256}, got ${verified.sourceSha256}`
    );
  }
  return {backup, result, verified, desiredSourceSha256};
}

export async function scriptRollback(
  scriptId: string,
  expectedCurrentSha256: string | undefined,
  backupContent: {files: unknown[]},
  expectedBackupSha256: string | undefined,
  approvalToken: string,
  call: GoogleCall = defaultGoogleCall
) {
  assertAllowedScript(scriptId);
  assertApproval(approvalToken);
  const desiredSourceSha256 = sourceSha256(backupContent);
  const verifiedBackupSha256 = expectedBackupSha256 ?? desiredSourceSha256;
  if (desiredSourceSha256 !== verifiedBackupSha256) {
    throw new Error(
      `BACKUP_HASH_MISMATCH: expected ${verifiedBackupSha256}, got ${desiredSourceSha256}`
    );
  }
  const before = await scriptBackup(scriptId, call);
  if (expectedCurrentSha256 && before.sha256 !== expectedCurrentSha256) {
    throw new Error(
      `OPTIMISTIC_LOCK_FAILED: expected ${expectedCurrentSha256}, got ${before.sha256}`
    );
  }
  const result = (await call(
    `https://script.googleapis.com/v1/projects/${encodeURIComponent(scriptId)}/content`,
    {method: "PUT", body: JSON.stringify(backupContent), googleAuthMode: "mutation"}
  )).body;
  const after = await scriptBackup(scriptId, call);
  if (after.sourceSha256 !== verifiedBackupSha256) {
    throw new Error(
      `ROLLBACK_VERIFICATION_FAILED: expected ${verifiedBackupSha256}, got ${after.sourceSha256}`
    );
  }
  return {before, result, after, desiredSourceSha256,
    compatibilityMode: !expectedCurrentSha256 || !expectedBackupSha256};
}
