function csv(name: string): Set<string> {
  return new Set((process.env[name] ?? "").split(",").map(v => v.trim()).filter(Boolean));
}

export const config = {
  port: Number(process.env.PORT ?? "8080"),
  mcpPath: process.env.MCP_PATH ?? "/mcp",
  approvalToken: process.env.FEDERATION_APPROVAL_TOKEN ?? "",
  defaultProject: process.env.GOOGLE_CLOUD_PROJECT ?? "",
  impersonateServiceAccount: process.env.GOOGLE_IMPERSONATE_SERVICE_ACCOUNT ?? "",
  readImpersonateServiceAccount: process.env.GOOGLE_READ_IMPERSONATE_SERVICE_ACCOUNT ?? process.env.GOOGLE_IMPERSONATE_SERVICE_ACCOUNT ?? "",
  mutationImpersonateServiceAccount: process.env.GOOGLE_MUTATION_IMPERSONATE_SERVICE_ACCOUNT ?? process.env.GOOGLE_IMPERSONATE_SERVICE_ACCOUNT ?? "",
  auditBucket: process.env.AUDIT_GCS_BUCKET ?? "",
  allowedProjects: csv("ALLOWED_PROJECTS"),
  allowedServices: csv("ALLOWED_SERVICES"),
  allowedScriptIds: csv("ALLOWED_SCRIPT_IDS"),
  allowedRegions: csv("ALLOWED_REGIONS"),
  allowedCloudRunServices: csv("ALLOWED_CLOUD_RUN_SERVICES"),
  allowedArtifactRepositories: csv("ALLOWED_ARTIFACT_REPOSITORIES"),
  googleRequestTimeoutMs: Number(process.env.GOOGLE_REQUEST_TIMEOUT_MS ?? "30000"),
};

function assertIdentifier(kind: string, value: string): void {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$/.test(value)) {
    throw new Error(`${kind}_INVALID: ${value}`);
  }
}

export function assertAllowedProject(project: string): void {
  assertIdentifier("PROJECT", project);
  if (!config.allowedProjects.has(project)) {
    throw new Error(`PROJECT_NOT_ALLOWLISTED: ${project}`);
  }
}

export function assertAllowedService(service: string): void {
  assertIdentifier("SERVICE", service);
  if (!config.allowedServices.has(service)) {
    throw new Error(`SERVICE_NOT_ALLOWLISTED: ${service}`);
  }
}

export function assertAllowedScript(scriptId: string): void {
  assertIdentifier("SCRIPT", scriptId);
  if (!config.allowedScriptIds.has(scriptId)) {
    throw new Error(`SCRIPT_NOT_ALLOWLISTED: ${scriptId}`);
  }
}

export function assertAllowedRegion(region: string): void {
  assertIdentifier("REGION", region);
  if (!config.allowedRegions.has(region)) {
    throw new Error(`REGION_NOT_ALLOWLISTED: ${region}`);
  }
}

export function assertAllowedCloudRunService(service: string): void {
  assertIdentifier("CLOUD_RUN_SERVICE", service);
  if (!config.allowedCloudRunServices.has(service)) {
    throw new Error(`CLOUD_RUN_SERVICE_NOT_ALLOWLISTED: ${service}`);
  }
}

export function assertAllowedArtifactRepository(repository: string): void {
  assertIdentifier("ARTIFACT_REPOSITORY", repository);
  if (!config.allowedArtifactRepositories.has(repository)) {
    throw new Error(`ARTIFACT_REPOSITORY_NOT_ALLOWLISTED: ${repository}`);
  }
}

export function assertApproval(token: string): void {
  if (!config.approvalToken || token !== config.approvalToken) {
    throw new Error("APPROVAL_TOKEN_INVALID");
  }
}
