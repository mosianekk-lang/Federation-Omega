import crypto from "node:crypto";
import {
  assertAllowedArtifactRepository,
  assertAllowedCloudRunService,
  assertAllowedProject,
  assertAllowedRegion,
} from "./config.js";

export type GoogleRead = <T>(
  url: string,
  init?: RequestInit
) => Promise<{status: number; body: T}>;

const defaultGoogleRead: GoogleRead = async <T>(url: string, init?: RequestInit) => {
  const {googleJson} = await import("./google.js");
  return googleJson<T>(url, init);
};

type JsonObject = Record<string, unknown>;

export type LineageOptions = {
  project: string;
  region: string;
  service: string;
  buildRegion?: string;
  buildId?: string;
  auditStartTime?: string;
  rollback?: {revision: string; buildId?: string};
};

export type TrafficTarget = {
  revision: string;
  percent: number;
  tag: string;
};

export type RevisionLineage = {
  revision: string;
  imageDigest: string;
  artifactUri: string;
  buildId: string;
  buildStatus: string;
  source: JsonObject;
  sourceHash: string;
  sourceVerification: JsonObject;
  sourceVerificationHash: string;
  deployer: string;
  auditTimestamp: string;
  auditMethod: string;
  auditResource: string;
  runtimeServiceAccount: string;
  buildServiceAccount: string;
  trafficPercent: number;
  trafficTags: string[];
};

export type LineageJoin = {
  attestationMode: "SERVING" | "ROLLBACK";
  projectId: string;
  projectNumber: string;
  region: string;
  service: string;
  revision: string;
  imageDigest: string;
  artifactUri: string;
  buildId: string;
  buildStatus: string;
  source: JsonObject;
  sourceHash: string;
  sourceVerification: JsonObject;
  sourceVerificationHash: string;
  deployer: string;
  auditTimestamp: string;
  auditMethod: string;
  auditResource: string;
  runtimeServiceAccount: string;
  buildServiceAccount: string;
  iamPolicyHash: string;
  iamEtag: string;
  iamPrivate: boolean;
  publicIamMembers: string[];
  traffic: TrafficTarget[];
  revisionLineages: RevisionLineage[];
};

export type LineagePass = {
  capturedAt: string;
  join: LineageJoin;
  issues: string[];
  contradictions: string[];
  evidenceHashes: Record<string, string>;
};

export type LineageComparison = {
  pass1: LineagePass;
  pass2: LineagePass;
  pass1JoinHash: string;
  pass2JoinHash: string;
  identifiersMatch: boolean;
  issues: string[];
  contradictions: string[];
};

type ProjectIdentity = {
  input: string;
  projectId: string;
  projectNumber: string;
};

type AuditEvidence = {
  principal: string;
  timestamp: string;
  method: string;
  resource: string;
};

type SourceVerificationResult = {
  evidence: JsonObject;
  evidenceHash: string;
  issues: string[];
};

function object(value: unknown, label: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`SEMANTIC_SCHEMA_INVALID:${label}`);
  }
  return value as JsonObject;
}

function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function string(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value as JsonObject)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function sha256(value: unknown): string {
  return crypto.createHash("sha256").update(canonical(value)).digest("hex");
}

function segment(value: string): string {
  return encodeURIComponent(value);
}

function assertResourceName(body: unknown, expected: string, label: string): JsonObject {
  const record = object(body, label);
  if (record.name !== expected) {
    throw new Error(`SEMANTIC_${label}_NAME_MISMATCH: expected ${expected}, got ${string(record.name) || "MISSING"}`);
  }
  return record;
}

function revisionId(value: string): string {
  const candidate = value.split("/").filter(Boolean).at(-1) ?? "";
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$/.test(candidate)) {
    throw new Error(`REVISION_INVALID: ${value}`);
  }
  return candidate;
}

export function parseArtifactImage(image: string): {
  location: string;
  project: string;
  repository: string;
  dockerImage: string;
  digest: string;
  uri: string;
} {
  const match = /^(?<location>[a-z0-9-]+)-docker\.pkg\.dev\/(?<project>[A-Za-z0-9._-]+)\/(?<repository>[A-Za-z0-9._-]+)\/(?<dockerImage>.+)@(?<digest>sha256:[0-9a-f]{64})$/.exec(image);
  if (!match?.groups) throw new Error(`IMAGE_NOT_IMMUTABLE_ARTIFACT_REGISTRY_URI: ${image}`);
  return {
    location: match.groups.location,
    project: match.groups.project,
    repository: match.groups.repository,
    dockerImage: `${match.groups.dockerImage}@${match.groups.digest}`,
    digest: match.groups.digest,
    uri: image,
  };
}

export async function cloudRunService(
  project: string, region: string, service: string, read: GoogleRead = defaultGoogleRead
) {
  assertAllowedProject(project);
  assertAllowedRegion(region);
  assertAllowedCloudRunService(service);
  const expected = `projects/${project}/locations/${region}/services/${service}`;
  const {body} = await read<JsonObject>(`https://run.googleapis.com/v2/${expected}`);
  return assertResourceName(body, expected, "CLOUD_RUN_SERVICE");
}

export async function cloudRunRevision(
  project: string, region: string, service: string, revision: string,
  read: GoogleRead = defaultGoogleRead
) {
  assertAllowedProject(project);
  assertAllowedRegion(region);
  assertAllowedCloudRunService(service);
  const id = revisionId(revision);
  const expected = `projects/${project}/locations/${region}/services/${service}/revisions/${id}`;
  const {body} = await read<JsonObject>(`https://run.googleapis.com/v2/${expected}`);
  return assertResourceName(body, expected, "CLOUD_RUN_REVISION");
}

export async function artifactDockerImage(
  project: string, location: string, repository: string, dockerImage: string,
  read: GoogleRead = defaultGoogleRead
) {
  assertAllowedProject(project);
  assertAllowedRegion(location);
  assertAllowedArtifactRepository(repository);
  if (!/.+@sha256:[0-9a-f]{64}$/.test(dockerImage)) {
    throw new Error(`DOCKER_IMAGE_DIGEST_REQUIRED: ${dockerImage}`);
  }
  const name = `projects/${project}/locations/${location}/repositories/${repository}/dockerImages/${dockerImage}`;
  const {body} = await read<JsonObject>(
    `https://artifactregistry.googleapis.com/v1/projects/${segment(project)}/locations/${segment(location)}/repositories/${segment(repository)}/dockerImages/${segment(dockerImage)}`
  );
  const record = object(body, "ARTIFACT_DOCKER_IMAGE");
  const resourceName = string(record.name);
  const uri = string(record.uri);
  if (resourceName !== name && !uri.endsWith(dockerImage)) {
    throw new Error(`SEMANTIC_ARTIFACT_DIGEST_MISMATCH: ${resourceName || uri || "MISSING"}`);
  }
  return record;
}

export async function cloudBuildInfo(
  project: string, region: string, buildId: string, read: GoogleRead = defaultGoogleRead
) {
  assertAllowedProject(project);
  assertAllowedRegion(region);
  const id = revisionId(buildId);
  const {body} = await read<JsonObject>(
    `https://cloudbuild.googleapis.com/v1/projects/${segment(project)}/locations/${segment(region)}/builds/${segment(id)}`
  );
  const record = object(body, "CLOUD_BUILD");
  if (string(record.id) !== id) {
    throw new Error(`SEMANTIC_CLOUD_BUILD_ID_MISMATCH: expected ${id}, got ${string(record.id) || "MISSING"}`);
  }
  return record;
}

export async function cloudBuildList(
  project: string, region: string, pageSize = 100, pageToken = "",
  read: GoogleRead = defaultGoogleRead
) {
  assertAllowedProject(project);
  assertAllowedRegion(region);
  const bounded = Math.max(1, Math.min(Math.trunc(pageSize), 100));
  const query = new URLSearchParams({pageSize: String(bounded)});
  if (pageToken) query.set("pageToken", pageToken);
  const {body} = await read<JsonObject>(
    `https://cloudbuild.googleapis.com/v1/projects/${segment(project)}/locations/${segment(region)}/builds?${query}`
  );
  const record = object(body, "CLOUD_BUILD_LIST");
  if (!Array.isArray(record.builds)) throw new Error("SEMANTIC_CLOUD_BUILD_LIST_BUILDS_MISSING");
  return record;
}

export async function cloudRunServiceIamPolicy(
  project: string, region: string, service: string, read: GoogleRead = defaultGoogleRead
) {
  assertAllowedProject(project);
  assertAllowedRegion(region);
  assertAllowedCloudRunService(service);
  const resource = `projects/${project}/locations/${region}/services/${service}`;
  const {body} = await read<JsonObject>(`https://run.googleapis.com/v2/${resource}:getIamPolicy`);
  const record = object(body, "CLOUD_RUN_IAM_POLICY");
  if (!Array.isArray(record.bindings)) throw new Error("SEMANTIC_IAM_BINDINGS_MISSING");
  return record;
}

function validatedStartTime(value?: string): string {
  if (!value) return new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString();
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) throw new Error(`AUDIT_START_TIME_INVALID: ${value}`);
  return parsed.toISOString();
}

export async function deploymentAuditEvents(
  project: string, region: string, service: string, startTime?: string,
  pageSize = 50, read: GoogleRead = defaultGoogleRead
) {
  assertAllowedProject(project);
  assertAllowedRegion(region);
  assertAllowedCloudRunService(service);
  const bounded = Math.max(1, Math.min(Math.trunc(pageSize), 100));
  const filter = [
    'logName:"cloudaudit.googleapis.com%2Factivity"',
    'protoPayload.serviceName="run.googleapis.com"',
    `(resource.labels.service_name="${service}" OR protoPayload.resourceName:"/services/${service}")`,
    `(resource.labels.location="${region}" OR protoPayload.resourceName:"/locations/${region}/")`,
    `timestamp>="${validatedStartTime(startTime)}"`,
  ].join(" AND ");
  const {body} = await read<JsonObject>("https://logging.googleapis.com/v2/entries:list", {
    method: "POST",
    body: JSON.stringify({
      resourceNames: [`projects/${project}`],
      filter,
      orderBy: "timestamp desc",
      pageSize: bounded,
    }),
  });
  const record = object(body, "CLOUD_RUN_DEPLOYMENT_AUDIT");
  if (!Array.isArray(record.entries)) throw new Error("SEMANTIC_AUDIT_ENTRIES_MISSING");
  return record;
}

async function projectResource(
  project: string, read: GoogleRead
): Promise<{record: JsonObject; identity: ProjectIdentity}> {
  // A numeric alias cannot be checked against an ID-only allowlist until CRM
  // resolves it. Non-numeric IDs remain fail-before-read. The canonical ID is
  // always checked immediately after this single read.
  if (/^\d+$/.test(project)) {
    if (!/^\d{6,30}$/.test(project)) throw new Error(`PROJECT_INVALID: ${project}`);
  } else {
    assertAllowedProject(project);
  }
  const {body} = await read<JsonObject>(
    `https://cloudresourcemanager.googleapis.com/v3/projects/${segment(project)}`
  );
  const record = object(body, "PROJECT");
  const projectId = string(record.projectId);
  const projectNumber = string(record.name).split("/").at(-1) ?? "";
  if (!projectId || !/^\d+$/.test(projectNumber)) {
    throw new Error("SEMANTIC_PROJECT_IDENTITY_INCOMPLETE");
  }
  if (project !== projectId && project !== projectNumber) {
    throw new Error(
      `SEMANTIC_PROJECT_ID_MISMATCH: input ${project}, provider ${projectId}/${projectNumber}`
    );
  }
  // The canonical ID, as well as the caller-supplied alias, must remain in policy.
  assertAllowedProject(projectId);
  return {record, identity: {input: project, projectId, projectNumber}};
}

function revisionImage(revision: JsonObject): string {
  const first = object(array(revision.containers)[0], "REVISION_CONTAINER");
  return string(first.image);
}

function buildHasDigest(build: JsonObject, digest: string): boolean {
  const results = build.results && typeof build.results === "object"
    ? build.results as JsonObject : {};
  return array(results.images).some(value => {
    const image = value && typeof value === "object" ? value as JsonObject : {};
    return string(image.digest) === digest || string(image.name).endsWith(`@${digest}`);
  });
}

function selectBuildByDigest(builds: unknown[], digest: string): JsonObject | undefined {
  return builds.map(value => object(value, "CLOUD_BUILD_ITEM"))
    .find(build => buildHasDigest(build, digest));
}

function sourceIdentity(build: JsonObject): JsonObject {
  const provenance = build.sourceProvenance && typeof build.sourceProvenance === "object"
    ? build.sourceProvenance as JsonObject : {};
  for (const key of ["resolvedStorageSource", "resolvedRepoSource", "resolvedConnectedRepository"]) {
    const value = provenance[key];
    if (value && typeof value === "object") {
      const identity: JsonObject = {[key]: value};
      if (provenance.fileHashes && typeof provenance.fileHashes === "object") {
        identity.fileHashes = provenance.fileHashes;
      }
      return identity;
    }
  }
  const source = build.source;
  return source && typeof source === "object" ? {declaredSource: source} : {};
}

function sourceIdentityIsImmutable(source: JsonObject): boolean {
  const storage = source.resolvedStorageSource;
  if (storage && typeof storage === "object") {
    const value = storage as JsonObject;
    return Boolean(string(value.bucket) && string(value.object) && string(value.generation));
  }
  const repo = source.resolvedRepoSource;
  if (repo && typeof repo === "object") return Boolean(string((repo as JsonObject).commitSha));
  const connected = source.resolvedConnectedRepository;
  if (connected && typeof connected === "object") {
    const value = connected as JsonObject;
    return Boolean(string(value.commitSha) || string(value.revision));
  }
  return false;
}

function optionalObject(value: unknown): JsonObject | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as JsonObject : undefined;
}

function declaredFieldMatches(
  declared: JsonObject, observed: JsonObject, field: string
): boolean {
  const expected = string(declared[field]);
  return !expected || expected === string(observed[field]);
}

async function verifySourceIdentity(
  source: JsonObject, read: GoogleRead, revision: string
): Promise<SourceVerificationResult> {
  const storage = optionalObject(source.resolvedStorageSource);
  if (storage) {
    const bucket = string(storage.bucket);
    const objectName = string(storage.object);
    const generation = string(storage.generation);
    if (!bucket || !objectName || !generation) {
      return {
        evidence: {},
        evidenceHash: "",
        issues: [`SOURCE_STORAGE_IDENTITY_INCOMPLETE:${revision}`],
      };
    }
    const query = new URLSearchParams({
      generation,
      fields: "bucket,name,generation,md5Hash,crc32c,size,etag",
    });
    let metadata: JsonObject;
    try {
      const {body} = await read<JsonObject>(
        `https://storage.googleapis.com/storage/v1/b/${segment(bucket)}/o/${segment(objectName)}?${query}`
      );
      metadata = object(body, "SOURCE_STORAGE_OBJECT_METADATA");
    } catch {
      return {
        evidence: {},
        evidenceHash: "",
        issues: [`SOURCE_VERIFICATION_READ_FAILED:${revision}`],
      };
    }
    const evidence: JsonObject = {
      provider: "google-cloud-storage",
      requested: {bucket, name: objectName, generation},
      observed: {
        bucket: string(metadata.bucket),
        name: string(metadata.name),
        generation: string(metadata.generation),
        md5Hash: string(metadata.md5Hash),
        crc32c: string(metadata.crc32c),
        size: string(metadata.size),
        etag: string(metadata.etag),
      },
    };
    const observed = evidence.observed as JsonObject;
    const issues: string[] = [];
    if (string(observed.bucket) !== bucket || string(observed.name) !== objectName ||
      string(observed.generation) !== generation) {
      issues.push(`SOURCE_STORAGE_GENERATION_MISMATCH:${revision}`);
    }
    if (!string(observed.md5Hash) || !string(observed.crc32c)) {
      issues.push(`SOURCE_STORAGE_CHECKSUM_MISSING:${revision}`);
    }
    if (!string(observed.size)) issues.push(`SOURCE_STORAGE_SIZE_MISSING:${revision}`);
    for (const field of ["md5Hash", "crc32c", "size"]) {
      if (!declaredFieldMatches(storage, observed, field)) {
        issues.push(`SOURCE_STORAGE_${field.toUpperCase()}_MISMATCH:${revision}`);
      }
    }
    return {
      evidence,
      evidenceHash: issues.length ? "" : sha256(evidence),
      issues,
    };
  }

  const repoKey = source.resolvedRepoSource
    ? "resolvedRepoSource" : source.resolvedConnectedRepository
      ? "resolvedConnectedRepository" : "";
  const repo = repoKey ? optionalObject(source[repoKey]) : undefined;
  if (repo) {
    const commit = string(repo.commitSha) || string(repo.revision);
    const issues: string[] = [];
    if (!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i.test(commit)) {
      issues.push(`SOURCE_REPO_EXACT_COMMIT_MISSING:${revision}`);
    }
    const verification = optionalObject(repo.verification) ??
      optionalObject(repo.commitVerification) ??
      optionalObject(source.providerVerification) ??
      optionalObject(source.fileHashes);
    if (!verification || !Object.keys(verification).length) {
      issues.push(`SOURCE_REPO_PROVIDER_VERIFICATION_MISSING:${revision}`);
    }
    const evidence: JsonObject = verification ? {
      provider: "repository-provider",
      sourceType: repoKey,
      commit,
      verification,
    } : {};
    return {
      evidence,
      evidenceHash: issues.length ? "" : sha256(evidence),
      issues,
    };
  }

  return {
    evidence: {},
    evidenceHash: "",
    issues: [`SOURCE_INDEPENDENT_VERIFICATION_MISSING:${revision}`],
  };
}

function valueReferencesRevision(value: unknown, revision: string): boolean {
  if (typeof value === "string") {
    if (value === revision) return true;
    const marker = `/revisions/${revision}`;
    return value.endsWith(marker) || value.includes(`${marker}/`) ||
      value.includes(`${marker}?`) || value.includes(`${marker}:`);
  }
  if (Array.isArray(value)) return value.some(item => valueReferencesRevision(item, revision));
  if (value && typeof value === "object") {
    return Object.values(value as JsonObject)
      .some(item => valueReferencesRevision(item, revision));
  }
  return false;
}

function auditForRevision(audit: JsonObject, revision: string): AuditEvidence | undefined {
  for (const value of array(audit.entries)) {
    const entry = object(value, "AUDIT_ENTRY");
    if (!valueReferencesRevision(entry, revision)) continue;
    const proto = entry.protoPayload && typeof entry.protoPayload === "object"
      ? entry.protoPayload as JsonObject : {};
    const auth = proto.authenticationInfo && typeof proto.authenticationInfo === "object"
      ? proto.authenticationInfo as JsonObject : {};
    const principal = string(auth.principalEmail);
    if (principal) {
      return {
        principal,
        timestamp: string(entry.timestamp),
        method: string(proto.methodName),
        resource: string(proto.resourceName),
      };
    }
  }
  return undefined;
}

function trafficIdentity(service: JsonObject, requireServing: boolean): {
  traffic: TrafficTarget[];
  serving: Array<{revision: string; percent: number; tags: string[]}>;
  issues: string[];
  contradictions: string[];
} {
  const issues: string[] = [];
  const contradictions: string[] = [];
  const values = array(service.trafficStatuses);
  if (!values.length) {
    if (requireServing) contradictions.push("SERVING_TRAFFIC_STATUS_MISSING");
    else issues.push("TRAFFIC_STATUS_MISSING");
  }
  const traffic: TrafficTarget[] = [];
  for (const value of values) {
    const target = object(value, "TRAFFIC_STATUS");
    const rawRevision = string(target.revision);
    const percent = typeof target.percent === "number"
      ? target.percent : Number(target.percent ?? Number.NaN);
    if (!Number.isFinite(percent) || percent < 0 || percent > 100) {
      contradictions.push(`TRAFFIC_PERCENT_INVALID:${rawRevision || "MISSING"}`);
      continue;
    }
    if (!rawRevision) {
      contradictions.push("TRAFFIC_REVISION_MISSING");
      continue;
    }
    try {
      traffic.push({revision: revisionId(rawRevision), percent, tag: string(target.tag)});
    } catch {
      contradictions.push(`TRAFFIC_REVISION_INVALID:${rawRevision}`);
    }
  }
  traffic.sort((a, b) => `${a.revision}:${a.tag}`.localeCompare(`${b.revision}:${b.tag}`));
  const grouped = new Map<string, {percent: number; tags: string[]}>();
  for (const target of traffic.filter(item => item.percent > 0)) {
    const current = grouped.get(target.revision) ?? {percent: 0, tags: []};
    current.percent += target.percent;
    if (target.tag) current.tags.push(target.tag);
    grouped.set(target.revision, current);
  }
  const total = [...grouped.values()].reduce((sum, item) => sum + item.percent, 0);
  if (traffic.length && Math.abs(total - 100) > 0.000001) {
    contradictions.push(`SERVING_TRAFFIC_TOTAL_NOT_100:${total}`);
  }
  if (requireServing && !grouped.size) contradictions.push("POSITIVE_TRAFFIC_REVISION_MISSING");
  const serving = [...grouped.entries()].map(([revision, value]) => ({
    revision,
    percent: value.percent,
    tags: [...new Set(value.tags)].sort(),
  })).sort((a, b) => a.revision.localeCompare(b.revision));
  return {traffic, serving, issues, contradictions};
}

function iamPosture(iam: JsonObject): {privateAccess: boolean; publicMembers: string[]} {
  const publicMembers: string[] = [];
  for (const value of array(iam.bindings)) {
    const binding = object(value, "IAM_BINDING");
    const role = string(binding.role) || "MISSING_ROLE";
    for (const member of array(binding.members).map(string)) {
      if (member === "allUsers" || member === "allAuthenticatedUsers") {
        publicMembers.push(`${role}:${member}`);
      }
    }
  }
  return {privateAccess: publicMembers.length === 0, publicMembers: [...new Set(publicMembers)].sort()};
}

function projectReferenceMatches(value: string, identity: ProjectIdentity): boolean {
  return value === identity.projectId || value === identity.projectNumber;
}

function buildProjectContradiction(build: JsonObject, identity: ProjectIdentity): string | undefined {
  const direct = string(build.projectId);
  if (direct && !projectReferenceMatches(direct, identity)) {
    return `BUILD_PROJECT_MISMATCH:${direct}`;
  }
  const nameProject = /^projects\/([^/]+)/.exec(string(build.name))?.[1] ?? "";
  if (nameProject && !projectReferenceMatches(nameProject, identity)) {
    return `BUILD_PROJECT_MISMATCH:${nameProject}`;
  }
  return undefined;
}

function blankRevisionLineage(
  revision: string, percent: number, tags: string[]
): RevisionLineage {
  return {
    revision,
    imageDigest: "",
    artifactUri: "",
    buildId: "",
    buildStatus: "",
    source: {},
    sourceHash: sha256({}),
    sourceVerification: {},
    sourceVerificationHash: "",
    deployer: "",
    auditTimestamp: "",
    auditMethod: "",
    auditResource: "",
    runtimeServiceAccount: "",
    buildServiceAccount: "",
    trafficPercent: percent,
    trafficTags: [...tags].sort(),
  };
}

async function collectRevisionLineage(
  options: LineageOptions,
  identity: ProjectIdentity,
  service: JsonObject,
  target: {revision: string; percent: number; tags: string[]},
  builds: JsonObject[],
  exactBuild: boolean,
  audit: JsonObject,
  read: GoogleRead,
  issues: string[],
  contradictions: string[],
  revisionEvidence: JsonObject[],
  artifactEvidence: JsonObject[]
): Promise<RevisionLineage> {
  const id = revisionId(target.revision);
  let revision: JsonObject;
  try {
    revision = await cloudRunRevision(
      identity.projectId, options.region, options.service, id, read
    );
    revisionEvidence.push(revision);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (!message.startsWith("SEMANTIC_") && !message.startsWith("REVISION_")) throw error;
    contradictions.push(`REVISION_PROVIDER_CONTRADICTION:${id}:${message}`);
    return blankRevisionLineage(id, target.percent, target.tags);
  }

  let parsedImage: ReturnType<typeof parseArtifactImage>;
  try {
    parsedImage = parseArtifactImage(revisionImage(revision));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    contradictions.push(`REVISION_IMAGE_CONTRADICTION:${id}:${message}`);
    return blankRevisionLineage(id, target.percent, target.tags);
  }
  if (!projectReferenceMatches(parsedImage.project, identity)) {
    contradictions.push(`IMAGE_PROJECT_MISMATCH:${id}:${parsedImage.project}`);
  }

  let artifact: JsonObject = {};
  if (projectReferenceMatches(parsedImage.project, identity)) {
    try {
      artifact = await artifactDockerImage(
        identity.projectId,
        parsedImage.location,
        parsedImage.repository,
        parsedImage.dockerImage,
        read
      );
      artifactEvidence.push(artifact);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.startsWith("SEMANTIC_")) throw error;
      contradictions.push(`ARTIFACT_PROVIDER_CONTRADICTION:${id}:${message}`);
    }
  }

  const build = exactBuild ? builds[0] : selectBuildByDigest(builds, parsedImage.digest);
  if (!build) issues.push(`BUILD_NOT_FOUND_FOR_DIGEST_IN_BOUNDED_READ:${id}`);
  if (build && !buildHasDigest(build, parsedImage.digest)) {
    contradictions.push(`BUILD_DIGEST_MISMATCH:${id}`);
  }
  if (build && string(build.status) !== "SUCCESS") {
    contradictions.push(`BUILD_STATUS_NOT_SUCCESS:${id}:${string(build.status) || "MISSING"}`);
  }
  if (build) {
    const projectMismatch = buildProjectContradiction(build, identity);
    if (projectMismatch) contradictions.push(`${projectMismatch}:${id}`);
  }

  const source = build ? sourceIdentity(build) : {};
  if (!Object.keys(source).length) issues.push(`SOURCE_PROVENANCE_MISSING:${id}`);
  else if (!sourceIdentityIsImmutable(source)) {
    issues.push(`SOURCE_IDENTITY_NOT_IMMUTABLE:${id}`);
  }
  const sourceVerification = await verifySourceIdentity(source, read, id);
  issues.push(...sourceVerification.issues);
  const runtimeServiceAccount = string(revision.serviceAccount) || string(
    service.template && typeof service.template === "object"
      ? (service.template as JsonObject).serviceAccount : ""
  );
  if (!runtimeServiceAccount) issues.push(`RUNTIME_SERVICE_ACCOUNT_MISSING:${id}`);
  if (build && !string(build.serviceAccount)) {
    issues.push(`BUILD_SERVICE_ACCOUNT_MISSING:${id}`);
  }

  const auditEvidence = auditForRevision(audit, id);
  if (!auditEvidence) issues.push(`REVISION_SPECIFIC_AUDIT_EVIDENCE_MISSING:${id}`);
  const artifactUri = string(artifact.uri) || parsedImage.uri;
  if (!artifactUri.endsWith(`@${parsedImage.digest}`)) {
    contradictions.push(`ARTIFACT_URI_DIGEST_MISMATCH:${id}`);
  }
  return {
    revision: revisionId(string(revision.name)),
    imageDigest: parsedImage.digest,
    artifactUri,
    buildId: build ? string(build.id) : "",
    buildStatus: build ? string(build.status) : "",
    source,
    sourceHash: sha256(source),
    sourceVerification: sourceVerification.evidence,
    sourceVerificationHash: sourceVerification.evidenceHash,
    deployer: auditEvidence?.principal ?? "",
    auditTimestamp: auditEvidence?.timestamp ?? "",
    auditMethod: auditEvidence?.method ?? "",
    auditResource: auditEvidence?.resource ?? "",
    runtimeServiceAccount,
    buildServiceAccount: build ? string(build.serviceAccount) : "",
    trafficPercent: target.percent,
    trafficTags: [...target.tags].sort(),
  };
}

async function collectPass(
  options: LineageOptions,
  read: GoogleRead,
  revisionOverride?: string,
  buildIdOverride?: string
): Promise<LineagePass> {
  const {record: project, identity} = await projectResource(options.project, read);
  const service = await cloudRunService(
    identity.projectId, options.region, options.service, read
  );
  const mode = revisionOverride ? "ROLLBACK" as const : "SERVING" as const;
  const parsedTraffic = trafficIdentity(service, mode === "SERVING");
  const issues = [...parsedTraffic.issues];
  const contradictions = [...parsedTraffic.contradictions];
  if (service.reconciling === true) issues.push("SERVICE_RECONCILING");

  const targets = revisionOverride
    ? [{
      revision: revisionId(revisionOverride),
      percent: parsedTraffic.traffic
        .filter(item => item.revision === revisionId(revisionOverride))
        .reduce((sum, item) => sum + item.percent, 0),
      tags: parsedTraffic.traffic
        .filter(item => item.revision === revisionId(revisionOverride) && item.tag)
        .map(item => item.tag),
    }]
    : parsedTraffic.serving;

  const buildRegion = options.buildRegion ?? options.region;
  // A rollback without its own build ID must discover the build by the rollback
  // revision's digest; inheriting the current deployment's build would mis-bind proof.
  const requestedBuildId = mode === "ROLLBACK" ? buildIdOverride : options.buildId;
  let buildEvidence: JsonObject = {};
  let builds: JsonObject[] = [];
  if (targets.length && requestedBuildId) {
    const build = await cloudBuildInfo(
      identity.projectId, buildRegion, requestedBuildId, read
    );
    buildEvidence = build;
    builds = [build];
  } else if (targets.length) {
    const list = await cloudBuildList(identity.projectId, buildRegion, 100, "", read);
    buildEvidence = list;
    builds = array(list.builds).map(value => object(value, "CLOUD_BUILD_ITEM"));
  }

  const audit = await deploymentAuditEvents(
    identity.projectId, options.region, options.service, options.auditStartTime, 50, read
  );
  const iam = await cloudRunServiceIamPolicy(
    identity.projectId, options.region, options.service, read
  );
  const serviceIamPosture = iamPosture(iam);
  if (!serviceIamPosture.privateAccess) {
    contradictions.push(...serviceIamPosture.publicMembers.map(
      member => `PUBLIC_CLOUD_RUN_IAM_BINDING:${member}`
    ));
  }
  const revisionEvidence: JsonObject[] = [];
  const artifactEvidence: JsonObject[] = [];
  const revisionLineages: RevisionLineage[] = [];
  for (const target of targets) {
    revisionLineages.push(await collectRevisionLineage(
      options,
      identity,
      service,
      target,
      builds,
      Boolean(requestedBuildId),
      audit,
      read,
      issues,
      contradictions,
      revisionEvidence,
      artifactEvidence
    ));
  }
  for (const lineage of revisionLineages) {
    if (!lineage.sourceVerificationHash) {
      issues.push(`SOURCE_VERIFICATION_EVIDENCE_HASH_MISSING:${lineage.revision || "UNKNOWN"}`);
    }
  }
  revisionLineages.sort((a, b) => a.revision.localeCompare(b.revision));
  const primary = [...revisionLineages].sort((a, b) =>
    b.trafficPercent - a.trafficPercent || a.revision.localeCompare(b.revision)
  )[0] ?? blankRevisionLineage("", 0, []);
  const iamPolicyHash = sha256(iam);
  const join: LineageJoin = {
    attestationMode: mode,
    projectId: identity.projectId,
    projectNumber: identity.projectNumber,
    region: options.region,
    service: options.service,
    revision: primary.revision,
    imageDigest: primary.imageDigest,
    artifactUri: primary.artifactUri,
    buildId: primary.buildId,
    buildStatus: primary.buildStatus,
    source: primary.source,
    sourceHash: primary.sourceHash,
    sourceVerification: primary.sourceVerification,
    sourceVerificationHash: primary.sourceVerificationHash,
    deployer: primary.deployer,
    auditTimestamp: primary.auditTimestamp,
    auditMethod: primary.auditMethod,
    auditResource: primary.auditResource,
    runtimeServiceAccount: primary.runtimeServiceAccount,
    buildServiceAccount: primary.buildServiceAccount,
    iamPolicyHash,
    iamEtag: string(iam.etag),
    iamPrivate: serviceIamPosture.privateAccess,
    publicIamMembers: serviceIamPosture.publicMembers,
    traffic: parsedTraffic.traffic,
    revisionLineages,
  };
  return {
    capturedAt: new Date().toISOString(),
    join,
    issues: [...new Set([...issues, ...contradictions])].sort(),
    contradictions: [...new Set(contradictions)].sort(),
    evidenceHashes: {
      project: sha256(project),
      service: sha256(service),
      revision: sha256(revisionEvidence),
      artifact: sha256(artifactEvidence),
      build: sha256(buildEvidence),
      sourceVerification: revisionLineages.every(item => item.sourceVerificationHash)
        ? sha256(revisionLineages.map(item => ({
          revision: item.revision,
          hash: item.sourceVerificationHash,
        }))) : "",
      audit: sha256(audit),
      iam: iamPolicyHash,
    },
  };
}

function compare(pass1: LineagePass, pass2: LineagePass): LineageComparison {
  const pass1JoinHash = sha256(pass1.join);
  const pass2JoinHash = sha256(pass2.join);
  const issues = [...new Set([...pass1.issues, ...pass2.issues])].sort();
  const contradictions = [...new Set([
    ...pass1.contradictions,
    ...pass2.contradictions,
  ])].sort();
  if (pass1JoinHash !== pass2JoinHash) {
    issues.push("INDEPENDENT_READ_IDENTIFIER_MISMATCH");
    contradictions.push("INDEPENDENT_READ_IDENTIFIER_MISMATCH");
  }
  return {
    pass1,
    pass2,
    pass1JoinHash,
    pass2JoinHash,
    identifiersMatch: pass1JoinHash === pass2JoinHash,
    issues: [...new Set(issues)].sort(),
    contradictions: [...new Set(contradictions)].sort(),
  };
}

export async function deploymentLineageAttest(
  options: LineageOptions, read: GoogleRead = defaultGoogleRead
) {
  const currentPass1 = await collectPass(options, read);
  const currentPass2 = await collectPass(options, read);
  const current = compare(currentPass1, currentPass2);
  let rollback: LineageComparison | undefined;
  if (options.rollback) {
    const rollbackPass1 = await collectPass(
      options, read, options.rollback.revision, options.rollback.buildId
    );
    const rollbackPass2 = await collectPass(
      options, read, options.rollback.revision, options.rollback.buildId
    );
    rollback = compare(rollbackPass1, rollbackPass2);
  }
  const issues = [...new Set([...current.issues, ...(rollback?.issues ?? [])])].sort();
  const contradictions = [...new Set([
    ...current.contradictions,
    ...(rollback?.contradictions ?? []),
  ])].sort();
  const state = contradictions.length ? "MISMATCH" : issues.length ? "PARTIAL" : "ATTESTED";
  return {
    attestationId: crypto.randomUUID(),
    generatedAt: new Date().toISOString(),
    state,
    proofBoundary: state === "ATTESTED"
      ? "provider_identifiers_matched_across_two_independent_reads"
      : "fail_closed_no_promotion",
    current,
    rollback,
    issues,
    contradictions,
  };
}
