import assert from "node:assert/strict";
import test from "node:test";

process.env.ALLOWED_PROJECTS = "sov-hybrid-suite";
process.env.ALLOWED_REGIONS = "africa-south1,global";
process.env.ALLOWED_CLOUD_RUN_SERVICES = "architron9";
process.env.ALLOWED_ARTIFACT_REPOSITORIES = "federation-omega";

const {
  cloudBuildList,
  cloudRunService,
  deploymentAuditEvents,
  deploymentLineageAttest,
  parseArtifactImage,
} = await import("../dist/lineage.js");

const digest = `sha256:${"a".repeat(64)}`;
const digestB = `sha256:${"b".repeat(64)}`;
const project = "sov-hybrid-suite";
const projectNumber = "257649435135";
const region = "africa-south1";
const service = "architron9";
const repository = "federation-omega";
const image = `${region}-docker.pkg.dev/${project}/${repository}/architron9@${digest}`;
const storageMd5 = "CY9rzUYh03PK3k6DJie09g==";
const storageCrc32c = "ImIEBA==";

function imageForDigest(value) {
  return `${region}-docker.pkg.dev/${project}/${repository}/architron9@${value}`;
}

function buildFixture(id, value, status = "SUCCESS", sourceProvenance) {
  return {
    id,
    name: `projects/${projectNumber}/locations/${region}/builds/${id}`,
    status,
    serviceAccount: `projects/${projectNumber}/serviceAccounts/builder@${project}.iam.gserviceaccount.com`,
    results: {images: [{name: imageForDigest(value), digest: value}]},
    sourceProvenance: sourceProvenance ?? {
      resolvedStorageSource: {bucket: "source-bucket", object: `${id}.tgz`, generation: "7"},
    },
  };
}

function fixtures({
  driftRevision = false,
  latestReadyRevision = "architron9-00030-zhz",
  trafficStatuses,
  revisionDigests = {},
  exactBuildDigest = digest,
  exactBuildStatus = "SUCCESS",
  exactBuildSourceProvenance,
  listedBuilds = [],
  auditPrincipals = {},
  storageMetadata = {},
  iamMembers = ["serviceAccount:caller@example.com"],
} = {}) {
  let serviceReads = 0;
  const calls = [];
  const seenRevisions = new Set([
    "architron9-00030-zhz",
    "architron9-00031-new",
    "architron9-00029-old",
    latestReadyRevision,
    ...Object.keys(revisionDigests),
    ...(trafficStatuses ?? []).map(target => target.revision),
  ]);
  const read = async (url, init = {}) => {
    calls.push({url, init});
    if (url.includes("cloudresourcemanager.googleapis.com")) {
      return {status: 200, body: {name: "projects/257649435135", projectId: project}};
    }
    if (url === `https://run.googleapis.com/v2/projects/${project}/locations/${region}/services/${service}`) {
      serviceReads += 1;
      const revision = driftRevision && serviceReads > 1
        ? "architron9-00031-new" : latestReadyRevision;
      seenRevisions.add(revision);
      return {status: 200, body: {
        name: `projects/${project}/locations/${region}/services/${service}`,
        latestReadyRevision: `projects/${project}/locations/${region}/services/${service}/revisions/${revision}`,
        latestCreatedRevision: `projects/${project}/locations/${region}/services/${service}/revisions/${revision}`,
        reconciling: false,
        template: {serviceAccount: "architron-runtime@sov-hybrid-suite.iam.gserviceaccount.com"},
        trafficStatuses: trafficStatuses ?? [{revision, percent: 100, tag: ""}],
      }};
    }
    if (url.includes("run.googleapis.com/v2/projects/") && url.includes("/revisions/")) {
      const revision = decodeURIComponent(url.split("/").at(-1));
      const revisionDigest = revisionDigests[revision] ?? digest;
      return {status: 200, body: {
        name: `projects/${project}/locations/${region}/services/${service}/revisions/${revision}`,
        containers: [{image: imageForDigest(revisionDigest)}],
        serviceAccount: "architron-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
      }};
    }
    if (url.includes("artifactregistry.googleapis.com")) {
      const decoded = decodeURIComponent(url);
      const artifactDigest = decoded.includes(digestB) ? digestB : digest;
      return {status: 200, body: {
        name: `projects/${project}/locations/${region}/repositories/${repository}/dockerImages/architron9@${artifactDigest}`,
        uri: imageForDigest(artifactDigest),
      }};
    }
    if (url.includes("cloudbuild.googleapis.com") && url.endsWith("/builds/build-1")) {
      return {status: 200, body: buildFixture(
        "build-1", exactBuildDigest, exactBuildStatus, exactBuildSourceProvenance
      )};
    }
    if (url.includes("cloudbuild.googleapis.com") && url.includes("/builds?")) {
      return {status: 200, body: {builds: listedBuilds}};
    }
    if (url.includes("storage.googleapis.com/storage/v1/b/")) {
      const parsed = new URL(url);
      const objectName = decodeURIComponent(parsed.pathname.split("/o/").at(-1));
      return {status: 200, body: {
        bucket: "source-bucket",
        name: objectName,
        generation: parsed.searchParams.get("generation"),
        md5Hash: storageMd5,
        crc32c: storageCrc32c,
        size: "4096",
        etag: "storage-etag-1",
        ...storageMetadata,
      }};
    }
    if (url === "https://logging.googleapis.com/v2/entries:list") {
      return {status: 200, body: {entries: [...seenRevisions].sort().map(revision => ({
        timestamp: "2026-08-16T00:00:00Z",
        protoPayload: {
          methodName: "google.cloud.run.v2.Services.UpdateService",
          resourceName: `projects/${project}/locations/${region}/services/${service}/revisions/${revision}`,
          authenticationInfo: {
            principalEmail: auditPrincipals[revision] ??
              (revision === "architron9-00029-old" ? "rollback@example.com" : "deployer@example.com"),
          },
        },
      }))}};
    }
    if (url.endsWith(":getIamPolicy")) {
      return {status: 200, body: {etag: "etag-1", bindings: [{role: "roles/run.invoker", members: iamMembers}]}};
    }
    throw new Error(`UNEXPECTED_TEST_URL:${url}`);
  };
  return {read, calls};
}

test("parses only immutable Artifact Registry image identities", () => {
  assert.deepEqual(parseArtifactImage(image), {
    location: region,
    project,
    repository,
    dockerImage: `architron9@${digest}`,
    digest,
    uri: image,
  });
  assert.throws(() => parseArtifactImage(`${region}-docker.pkg.dev/${project}/${repository}/architron9:latest`),
    /IMAGE_NOT_IMMUTABLE_ARTIFACT_REGISTRY_URI/);
});

test("rejects generic health payloads as false Cloud Run capability", async () => {
  const read = async () => ({status: 200, body: {ok: true, component: "architron9"}});
  await assert.rejects(() => cloudRunService(project, region, service, read),
    /SEMANTIC_CLOUD_RUN_SERVICE_NAME_MISMATCH/);
});

test("produces an ATTESTED two-pass provider lineage", async () => {
  const {read, calls} = fixtures();
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.state, "ATTESTED");
  assert.equal(result.current.identifiersMatch, true);
  assert.equal(result.current.pass1.join.projectNumber, "257649435135");
  assert.equal(result.current.pass1.join.imageDigest, digest);
  assert.equal(result.current.pass1.join.buildId, "build-1");
  assert.equal(result.current.pass1.join.buildStatus, "SUCCESS");
  assert.equal(result.current.pass1.join.deployer, "deployer@example.com");
  assert.equal(result.current.pass1.join.attestationMode, "SERVING");
  assert.equal(result.current.pass1.join.revisionLineages.length, 1);
  assert.match(result.current.pass1.join.sourceHash, /^[0-9a-f]{64}$/);
  assert.match(result.current.pass1.join.sourceVerificationHash, /^[0-9a-f]{64}$/);
  assert.match(result.current.pass1.evidenceHashes.sourceVerification, /^[0-9a-f]{64}$/);
  assert.match(result.current.pass1.join.iamPolicyHash, /^[0-9a-f]{64}$/);
  assert.equal(result.current.pass1.join.iamPrivate, true);
  assert.deepEqual(result.current.pass1.join.publicIamMembers, []);
  assert.deepEqual(result.issues, []);
  assert.deepEqual(result.contradictions, []);
  assert.ok(calls.every(call => !["PUT", "PATCH", "DELETE"].includes(call.init.method ?? "GET")));
});

test("fails closed when Cloud Run IAM permits public invocation", async () => {
  const {read} = fixtures({iamMembers: ["allUsers"]});
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.state, "MISMATCH");
  assert.equal(result.current.pass1.join.iamPrivate, false);
  assert.match(result.contradictions.join("\n"), /PUBLIC_CLOUD_RUN_IAM_BINDING:roles\/run\.invoker:allUsers/);
});

test("returns PARTIAL when independent storage metadata lacks checksum evidence", async () => {
  const {read, calls} = fixtures({storageMetadata: {md5Hash: "", crc32c: ""}});
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.current.identifiersMatch, true);
  assert.equal(result.state, "PARTIAL");
  assert.ok(result.issues.includes("SOURCE_STORAGE_CHECKSUM_MISSING:architron9-00030-zhz"));
  assert.ok(result.issues.includes("SOURCE_VERIFICATION_EVIDENCE_HASH_MISSING:architron9-00030-zhz"));
  assert.equal(result.current.pass1.join.sourceVerificationHash, "");
  const storageCalls = calls.filter(call => call.url.includes("storage.googleapis.com"));
  assert.equal(storageCalls.length, 2);
  assert.ok(storageCalls.every(call => call.url.includes("fields=bucket%2Cname%2Cgeneration%2Cmd5Hash%2Ccrc32c%2Csize%2Cetag")));
  assert.ok(storageCalls.every(call => !call.url.includes("alt=media")));
});

test("returns PARTIAL when storage metadata does not match the immutable generation", async () => {
  const {read} = fixtures({storageMetadata: {generation: "8"}});
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.state, "PARTIAL");
  assert.ok(result.issues.includes(
    "SOURCE_STORAGE_GENERATION_MISMATCH:architron9-00030-zhz"
  ));
  assert.equal(result.current.pass1.join.sourceVerificationHash, "");
});

test("returns PARTIAL for an exact repository commit without provider verification", async () => {
  const {read, calls} = fixtures({
    exactBuildSourceProvenance: {
      resolvedRepoSource: {
        projectId: project,
        repoName: "federation-source",
        commitSha: "c".repeat(40),
      },
    },
  });
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.state, "PARTIAL");
  assert.ok(result.issues.includes(
    "SOURCE_REPO_PROVIDER_VERIFICATION_MISSING:architron9-00030-zhz"
  ));
  assert.equal(result.current.pass1.join.sourceVerificationHash, "");
  assert.equal(calls.filter(call => call.url.includes("storage.googleapis.com")).length, 0);
});

test("accepts an exact repository commit with provider-returned verification evidence", async () => {
  const {read} = fixtures({
    exactBuildSourceProvenance: {
      resolvedRepoSource: {
        projectId: project,
        repoName: "federation-source",
        commitSha: "d".repeat(40),
        verification: {verified: true, providerRecordId: "verification-1"},
      },
    },
  });
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.state, "ATTESTED");
  assert.match(result.current.pass1.join.sourceVerificationHash, /^[0-9a-f]{64}$/);
  assert.equal(result.current.pass1.join.sourceVerification.commit, "d".repeat(40));
});

test("canonicalizes an allowlisted project number to the provider project ID", async () => {
  const {read, calls} = fixtures();
  const result = await deploymentLineageAttest({
    project: projectNumber, region, service, buildId: "build-1",
  }, read);
  assert.equal(result.state, "ATTESTED");
  assert.equal(result.current.pass1.join.projectId, project);
  assert.equal(result.current.pass1.join.projectNumber, projectNumber);
  const providerCalls = calls.filter(call => !call.url.includes("cloudresourcemanager.googleapis.com"));
  assert.ok(providerCalls.every(call => !call.url.includes(`/projects/${projectNumber}/`)));
});

test("attests the 100%-serving older revision, not a zero-traffic latestReady revision", async () => {
  const latestReadyRevision = "architron9-00031-canary";
  const servingRevision = "architron9-00030-stable";
  const {read, calls} = fixtures({
    latestReadyRevision,
    trafficStatuses: [
      {revision: latestReadyRevision, percent: 0, tag: "canary"},
      {revision: servingRevision, percent: 100, tag: ""},
    ],
  });
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.state, "ATTESTED");
  assert.equal(result.current.pass1.join.revision, servingRevision);
  assert.deepEqual(
    result.current.pass1.join.revisionLineages.map(item => item.revision),
    [servingRevision]
  );
  const revisionCalls = calls.filter(call => call.url.includes("/revisions/"));
  assert.ok(revisionCalls.every(call => !call.url.endsWith(`/${latestReadyRevision}`)));
});

test("attests every positive target in a split-traffic service", async () => {
  const blue = "architron9-00030-blue";
  const green = "architron9-00031-green";
  const {read} = fixtures({
    latestReadyRevision: green,
    trafficStatuses: [
      {revision: blue, percent: 60, tag: "blue"},
      {revision: green, percent: 40, tag: "green"},
    ],
    revisionDigests: {[blue]: digest, [green]: digestB},
    listedBuilds: [buildFixture("build-blue", digest), buildFixture("build-green", digestB)],
  });
  const result = await deploymentLineageAttest({project, region, service}, read);
  assert.equal(result.state, "ATTESTED");
  assert.deepEqual(
    result.current.pass1.join.revisionLineages.map(item => [
      item.revision, item.trafficPercent, item.buildId,
    ]),
    [[blue, 60, "build-blue"], [green, 40, "build-green"]]
  );
});

test("fails closed when independent reads drift", async () => {
  const {read} = fixtures({driftRevision: true});
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.state, "MISMATCH");
  assert.equal(result.current.identifiersMatch, false);
  assert.ok(result.issues.includes("INDEPENDENT_READ_IDENTIFIER_MISMATCH"));
});

test("returns PARTIAL when bounded build discovery cannot join the digest", async () => {
  const {read} = fixtures();
  const result = await deploymentLineageAttest({project, region, service}, read);
  assert.equal(result.state, "PARTIAL");
  assert.ok(result.issues.some(issue => issue.startsWith("BUILD_NOT_FOUND_FOR_DIGEST_IN_BOUNDED_READ:")));
  assert.ok(result.issues.some(issue => issue.startsWith("SOURCE_PROVENANCE_MISSING:")));
  assert.deepEqual(result.contradictions, []);
});

test("classifies a stable build-to-digest contradiction as MISMATCH", async () => {
  const {read} = fixtures({exactBuildDigest: digestB});
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.current.identifiersMatch, true);
  assert.equal(result.state, "MISMATCH");
  assert.ok(result.contradictions.includes("BUILD_DIGEST_MISMATCH:architron9-00030-zhz"));
});

test("attests an exact rollback revision without provider mutation", async () => {
  const {read, calls} = fixtures();
  const result = await deploymentLineageAttest({
    project, region, service, buildId: "build-1",
    rollback: {revision: "architron9-00029-old", buildId: "build-1"},
  }, read);
  assert.equal(result.state, "ATTESTED");
  assert.equal(result.rollback.identifiersMatch, true);
  assert.equal(result.rollback.pass1.join.revision, "architron9-00029-old");
  assert.equal(result.rollback.pass1.join.attestationMode, "ROLLBACK");
  assert.equal(result.rollback.pass1.join.deployer, "rollback@example.com");
  assert.equal(result.rollback.pass1.join.revisionLineages[0].trafficPercent, 0);
  assert.match(result.rollback.pass1.join.auditResource, /revisions\/architron9-00029-old$/);
  assert.ok(calls.every(call => !["PUT", "PATCH", "DELETE"].includes(call.init.method ?? "GET")));
});

test("discovers rollback build by rollback digest instead of inheriting the current build ID", async () => {
  const {read} = fixtures({listedBuilds: [buildFixture("build-rollback", digest)]});
  const result = await deploymentLineageAttest({
    project, region, service, buildId: "build-1",
    rollback: {revision: "architron9-00029-old"},
  }, read);
  assert.equal(result.state, "ATTESTED");
  assert.equal(result.current.pass1.join.buildId, "build-1");
  assert.equal(result.rollback.pass1.join.buildId, "build-rollback");
  assert.equal(result.rollback.pass1.join.deployer, "rollback@example.com");
});

test("rejects a stable non-100 traffic allocation as MISMATCH", async () => {
  const {read} = fixtures({
    trafficStatuses: [{revision: "architron9-00030-zhz", percent: 90, tag: ""}],
  });
  const result = await deploymentLineageAttest({project, region, service, buildId: "build-1"}, read);
  assert.equal(result.state, "MISMATCH");
  assert.ok(result.contradictions.includes("SERVING_TRAFFIC_TOTAL_NOT_100:90"));
});

test("rejects a non-allowlisted region before any provider call", async () => {
  let called = false;
  const read = async () => { called = true; return {status: 200, body: {}}; };
  await assert.rejects(() => cloudRunService(project, "us-central1", service, read),
    /REGION_NOT_ALLOWLISTED/);
  assert.equal(called, false);
});

test("keeps list and audit reads bounded", async () => {
  const {read, calls} = fixtures();
  await cloudBuildList(project, region, 1000, "", read);
  await deploymentAuditEvents(project, region, service, "2026-01-01T00:00:00Z", 1000, read);
  const buildCall = calls.find(call => call.url.includes("cloudbuild.googleapis.com"));
  assert.match(buildCall.url, /pageSize=100/);
  const auditCall = calls.find(call => call.url.includes("logging.googleapis.com"));
  const body = JSON.parse(auditCall.init.body);
  assert.equal(body.pageSize, 100);
  assert.equal(body.orderBy, "timestamp desc");
});
