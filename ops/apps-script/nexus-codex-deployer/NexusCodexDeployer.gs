/**
 * NEXUS-CODEX v3.1.1 one-shot deployment adapter.
 *
 * Contract:
 * - Reads one immutable Drive file ID.
 * - Verifies the exact SHA-256 before and after Cloud Storage staging.
 * - Reuses a matching regional Cloud Build instead of creating duplicates.
 * - Deploys a tagged Cloud Run revision at zero traffic.
 * - Promotes only after identity, readiness, and HTTP canary checks.
 * - Preserves the prior revision traffic map for rollback.
 *
 * This module never stores or logs an OAuth token or application secret.
 */

const NEXUS_CODEX_DEPLOYER_V1 = Object.freeze({
  contract: 'NEXUS_CODEX_HASH_LOCKED_DEPLOYER_V1',
  release: 'v3.1.1',
  projectId: 'sov-hybrid-suite',
  projectNumber: '257649435135',
  region: 'africa-south1',
  service: 'nexus-codex-runtime',
  runtimeServiceAccount:
      'fo-automation-agent@sov-hybrid-suite.iam.gserviceaccount.com',
  artifactDriveFileId: '1_r1qlRHeEcF7Xl-BSJpfWUWIRYs4C_Pm',
  artifactName: 'nexus-codex-runtime-v3.1.1.zip',
  artifactSize: 28998,
  artifactSha256:
      'fabbdf9ec89c1ea4468515ba1659cc0019719c5bc5747084795148a354dc1518',
  bucket: 'run-sources-sov-hybrid-suite-africa-south1',
  objectName:
      'nexus-codex/v3.1.1/' +
      'fabbdf9ec89c1ea4468515ba1659cc0019719c5bc5747084795148a354dc1518/' +
      'nexus-codex-runtime-v3.1.1.zip',
  buildTag: 'nexus-codex-v311',
  revisionTag: 'nexus-v311',
  releaseLabel: 'v3-1-1',
  releaseShaLabel: 'fabbdf9ec89c1ea4',
  stateKey:
      'NEXUS_CODEX_DEPLOYER_V1_' +
      'fabbdf9ec89c1ea4468515ba1659cc001',
  buildTimeout: '1200s',
  canaryPaths: Object.freeze(['/health', '/'])
});

const NEXUS_CODEX_TERMINAL_BUILD_STATES_V1 = Object.freeze([
  'SUCCESS',
  'FAILURE',
  'INTERNAL_ERROR',
  'TIMEOUT',
  'CANCELLED',
  'EXPIRED'
]);

/**
 * Read-only plan. Safe to call before any source installation or deployment.
 */
function nexusCodexPlanV1() {
  nexusAssertTargetV1_(NEXUS_CODEX_DEPLOYER_V1);
  return {
    ok: true,
    contract: NEXUS_CODEX_DEPLOYER_V1.contract,
    release: NEXUS_CODEX_DEPLOYER_V1.release,
    target: nexusTargetIdentityV1_(NEXUS_CODEX_DEPLOYER_V1),
    artifact: {
      driveFileId: NEXUS_CODEX_DEPLOYER_V1.artifactDriveFileId,
      name: NEXUS_CODEX_DEPLOYER_V1.artifactName,
      size: NEXUS_CODEX_DEPLOYER_V1.artifactSize,
      sha256: NEXUS_CODEX_DEPLOYER_V1.artifactSha256,
      bucket: NEXUS_CODEX_DEPLOYER_V1.bucket,
      objectName: NEXUS_CODEX_DEPLOYER_V1.objectName
    },
    releasePolicy: {
      initialTrafficPercent: 0,
      taggedCanary: NEXUS_CODEX_DEPLOYER_V1.revisionTag,
      promoteAfterCanaryOnly: true,
      rollbackTrafficCapturedBeforeDeploy: true,
      recurringTriggerRequired: false
    },
    requiredScopes: [
      'https://www.googleapis.com/auth/drive.readonly',
      'https://www.googleapis.com/auth/cloud-platform',
      'https://www.googleapis.com/auth/script.external_request'
    ],
    manualUserTasks: [],
    ownerActionRequired: false
  };
}

/**
 * One-shot stage and submit. A script lock prevents concurrent submissions.
 * Re-running is safe: a matching state record or regional build is reused.
 */
function nexusCodexStageAndSubmitV1() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    return nexusCodexStageAndSubmitLockedV1_();
  } finally {
    lock.releaseLock();
  }
}

function nexusCodexStageAndSubmitLockedV1_() {
  const cfg = NEXUS_CODEX_DEPLOYER_V1;
  nexusAssertTargetV1_(cfg);

  const artifact = nexusReadAndVerifyDriveArtifactV1_(cfg);
  const props = PropertiesService.getScriptProperties();
  const priorState = nexusReadStateV1_(props, cfg.stateKey);

  if (priorState && nexusStateMatchesReleaseV1_(priorState, cfg) &&
      priorState.buildId) {
    const priorBuild = nexusGetBuildV1_(cfg, priorState.buildId);
    if (priorBuild && priorBuild.id) {
      return nexusSubmissionReceiptV1_(
          'REUSED_RECORDED_BUILD',
          artifact,
          priorState,
          priorBuild);
    }
  }

  const baseline = nexusReadServiceBaselineV1_(cfg);
  const staged = nexusStageVerifiedObjectV1_(cfg, artifact);
  const matchingBuild = nexusFindMatchingBuildV1_(cfg);
  if (matchingBuild) {
    const recoveredState = nexusMakeStateV1_(
        cfg,
        artifact,
        staged,
        baseline,
        matchingBuild,
        'REUSED_DISCOVERED_BUILD');
    nexusWriteStateV1_(props, cfg.stateKey, recoveredState);
    return nexusSubmissionReceiptV1_(
        'REUSED_DISCOVERED_BUILD',
        artifact,
        recoveredState,
        matchingBuild);
  }

  const request = nexusBuildRequestV1_(cfg, staged, baseline);
  const operation = nexusGoogleJsonV1_(
      'https://cloudbuild.googleapis.com/v1/projects/' +
          encodeURIComponent(cfg.projectId) + '/locations/' +
          encodeURIComponent(cfg.region) + '/builds?projectId=' +
          encodeURIComponent(cfg.projectId),
      'post',
      request,
      [200]);
  const build = nexusBuildFromOperationV1_(operation);
  if (!build || !build.id) {
    throw new Error('nexus_build_id_missing');
  }

  const state = nexusMakeStateV1_(
      cfg,
      artifact,
      staged,
      baseline,
      build,
      'SUBMITTED_NEW_BUILD');
  state.operationName = operation.name || null;
  nexusWriteStateV1_(props, cfg.stateKey, state);
  return nexusSubmissionReceiptV1_('SUBMITTED_NEW_BUILD', artifact, state, build);
}

/**
 * Read-only terminal proof. This does not poll or schedule another execution.
 */
function nexusCodexStatusV1() {
  const cfg = NEXUS_CODEX_DEPLOYER_V1;
  nexusAssertTargetV1_(cfg);
  const state = nexusReadStateV1_(
      PropertiesService.getScriptProperties(),
      cfg.stateKey);
  if (!state || !nexusStateMatchesReleaseV1_(state, cfg)) {
    return {
      ok: true,
      status: 'NOT_SUBMITTED',
      target: nexusTargetIdentityV1_(cfg),
      manualUserTasks: [],
      ownerActionRequired: false
    };
  }

  const build = state.buildId ? nexusGetBuildV1_(cfg, state.buildId) : null;
  const service = nexusReadServiceBaselineV1_(cfg);
  const proof = nexusServiceProofV1_(cfg, service);
  return {
    ok: Boolean(build && build.status === 'SUCCESS' && proof.verified),
    status: build ? build.status : 'BUILD_NOT_FOUND',
    buildId: state.buildId || null,
    buildTerminal: build ?
        NEXUS_CODEX_TERMINAL_BUILD_STATES_V1.indexOf(build.status) >= 0 :
        false,
    target: nexusTargetIdentityV1_(cfg),
    serviceProof: proof,
    rollback: state.rollback,
    submittedAt: state.submittedAt,
    manualUserTasks: [],
    ownerActionRequired: false
  };
}

/**
 * Explicit rollback adapter. It submits one bounded build that restores the
 * exact pre-deployment revision percentages captured in the state record.
 */
function nexusCodexSubmitRollbackV1() {
  const cfg = NEXUS_CODEX_DEPLOYER_V1;
  nexusAssertTargetV1_(cfg);
  const props = PropertiesService.getScriptProperties();
  const state = nexusReadStateV1_(props, cfg.stateKey);
  if (!state || !nexusStateMatchesReleaseV1_(state, cfg)) {
    throw new Error('nexus_rollback_state_missing');
  }
  const spec = nexusRollbackTrafficSpecV1_(state.rollback &&
                                           state.rollback.previousTraffic);
  if (!spec) {
    throw new Error('nexus_rollback_target_missing');
  }
  if (state.rollbackBuildId) {
    return {
      ok: true,
      status: 'REUSED_ROLLBACK_BUILD',
      buildId: state.rollbackBuildId,
      rollbackTrafficSpec: spec
    };
  }

  const body = nexusRollbackBuildRequestV1_(cfg, spec);
  const operation = nexusGoogleJsonV1_(
      'https://cloudbuild.googleapis.com/v1/projects/' +
          encodeURIComponent(cfg.projectId) + '/locations/' +
          encodeURIComponent(cfg.region) + '/builds?projectId=' +
          encodeURIComponent(cfg.projectId),
      'post',
      body,
      [200]);
  const build = nexusBuildFromOperationV1_(operation);
  if (!build || !build.id) {
    throw new Error('nexus_rollback_build_id_missing');
  }
  state.rollbackBuildId = build.id;
  state.rollbackSubmittedAt = new Date().toISOString();
  nexusWriteStateV1_(props, cfg.stateKey, state);
  return {
    ok: true,
    status: 'ROLLBACK_SUBMITTED',
    buildId: build.id,
    rollbackTrafficSpec: spec
  };
}

function nexusAssertTargetV1_(cfg) {
  const expected = NEXUS_CODEX_DEPLOYER_V1;
  const keys = [
    'projectId',
    'projectNumber',
    'region',
    'service',
    'runtimeServiceAccount',
    'artifactDriveFileId',
    'artifactSha256',
    'bucket',
    'objectName'
  ];
  keys.forEach(function(key) {
    if (!cfg || cfg[key] !== expected[key]) {
      throw new Error('nexus_target_confusion_' + key);
    }
  });
  if (!/^[a-f0-9]{64}$/.test(cfg.artifactSha256)) {
    throw new Error('nexus_artifact_sha256_invalid');
  }
  if (cfg.service === 'architron9') {
    throw new Error('nexus_target_confusion_source_service');
  }
  return true;
}

function nexusTargetIdentityV1_(cfg) {
  return {
    projectId: cfg.projectId,
    projectNumber: cfg.projectNumber,
    region: cfg.region,
    service: cfg.service,
    runtimeServiceAccount: cfg.runtimeServiceAccount
  };
}

function nexusReadAndVerifyDriveArtifactV1_(cfg) {
  const file = DriveApp.getFileById(cfg.artifactDriveFileId);
  if (file.getName() !== cfg.artifactName) {
    throw new Error('nexus_artifact_name_mismatch');
  }
  const blob = file.getBlob();
  const bytes = blob.getBytes();
  if (bytes.length !== cfg.artifactSize) {
    throw new Error('nexus_artifact_size_mismatch');
  }
  const sha256 = nexusSha256HexV1_(bytes);
  if (sha256 !== cfg.artifactSha256) {
    throw new Error('nexus_artifact_sha256_mismatch');
  }
  return {
    driveFileId: cfg.artifactDriveFileId,
    name: cfg.artifactName,
    size: bytes.length,
    sha256: sha256,
    blob: blob
  };
}

function nexusSha256HexV1_(bytes) {
  const digest = Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      bytes);
  return digest.map(function(value) {
    const normalized = value < 0 ? value + 256 : value;
    return ('0' + normalized.toString(16)).slice(-2);
  }).join('');
}

function nexusStageVerifiedObjectV1_(cfg, artifact) {
  const metadataUrl =
      'https://storage.googleapis.com/storage/v1/b/' +
      encodeURIComponent(cfg.bucket) + '/o/' +
      encodeURIComponent(cfg.objectName) +
      '?fields=name,generation,size';
  let metadata = nexusGoogleJsonV1_(
      metadataUrl,
      'get',
      null,
      [200, 404],
      true);

  if (metadata.httpCode === 404) {
    const uploadUrl =
        'https://storage.googleapis.com/upload/storage/v1/b/' +
        encodeURIComponent(cfg.bucket) +
        '/o?uploadType=media&ifGenerationMatch=0&name=' +
        encodeURIComponent(cfg.objectName);
    const upload = nexusGoogleRawV1_(
        uploadUrl,
        'post',
        artifact.blob,
        artifact.blob.getContentType() || 'application/zip',
        [200, 201, 412],
        true);
    if (upload.httpCode !== 200 &&
        upload.httpCode !== 201 &&
        upload.httpCode !== 412) {
      throw new Error('nexus_gcs_stage_http_' + upload.httpCode);
    }
    metadata = nexusGoogleJsonV1_(
        metadataUrl,
        'get',
        null,
        [200],
        true);
  }

  const media = nexusGoogleRawV1_(
      'https://storage.googleapis.com/download/storage/v1/b/' +
          encodeURIComponent(cfg.bucket) + '/o/' +
          encodeURIComponent(cfg.objectName) + '?alt=media',
      'get',
      null,
      null,
      [200],
      false);
  const stagedBytes = media.blob.getBytes();
  const stagedSha256 = nexusSha256HexV1_(stagedBytes);
  if (stagedBytes.length !== artifact.size ||
      stagedSha256 !== artifact.sha256) {
    throw new Error('nexus_staged_artifact_integrity_mismatch');
  }

  return {
    bucket: cfg.bucket,
    objectName: cfg.objectName,
    generation: String(metadata.body.generation || ''),
    size: stagedBytes.length,
    sha256: stagedSha256
  };
}

function nexusReadServiceBaselineV1_(cfg) {
  const result = nexusGoogleJsonV1_(
      'https://run.googleapis.com/v2/projects/' +
          encodeURIComponent(cfg.projectId) + '/locations/' +
          encodeURIComponent(cfg.region) + '/services/' +
          encodeURIComponent(cfg.service),
      'get',
      null,
      [200, 404],
      true);
  if (result.httpCode === 404) {
    return {
      exists: false,
      name: 'projects/' + cfg.projectId + '/locations/' + cfg.region +
          '/services/' + cfg.service,
      latestReadyRevision: null,
      latestCreatedRevision: null,
      uri: null,
      traffic: []
    };
  }
  const service = result.body || {};
  return {
    exists: true,
    name: service.name || null,
    latestReadyRevision: service.latestReadyRevision || null,
    latestCreatedRevision: service.latestCreatedRevision || null,
    uri: service.uri || null,
    traffic: nexusNormalizeTrafficV1_(service.traffic || []),
    template: {
      serviceAccount: service.template && service.template.serviceAccount ?
          service.template.serviceAccount :
          null,
      containers: service.template && service.template.containers ?
          service.template.containers :
          []
    },
    conditions: service.conditions || []
  };
}

function nexusNormalizeTrafficV1_(traffic) {
  return (traffic || []).map(function(item) {
    return {
      revision: item.revision || item.revisionName || null,
      percent: Number(item.percent || 0),
      tag: item.tag || null,
      type: item.type || null
    };
  }).filter(function(item) {
    return item.revision && item.percent > 0;
  });
}

function nexusRollbackTrafficSpecV1_(traffic) {
  const rows = nexusNormalizeTrafficV1_(traffic);
  const total = rows.reduce(function(sum, item) {
    return sum + item.percent;
  }, 0);
  if (!rows.length || total !== 100) return '';
  return rows.map(function(item) {
    if (!/^[a-z][a-z0-9-]{0,62}$/.test(item.revision)) {
      throw new Error('nexus_rollback_revision_invalid');
    }
    return item.revision + '=' + item.percent;
  }).join(',');
}

function nexusBuildRequestV1_(cfg, staged, baseline) {
  const previousTraffic = nexusRollbackTrafficSpecV1_(baseline.traffic || []);
  return {
    source: {
      storageSource: {
        bucket: staged.bucket,
        object: staged.objectName,
        generation: staged.generation
      }
    },
    steps: [{
      name: 'gcr.io/google.com/cloudsdktool/cloud-sdk:slim',
      entrypoint: 'bash',
      args: [
        '-c',
        nexusDeploymentShellV1_()
      ],
      env: ['CLOUDSDK_CORE_DISABLE_PROMPTS=1']
    }],
    substitutions: {
      _PROJECT_ID: cfg.projectId,
      _REGION: cfg.region,
      _SERVICE: cfg.service,
      _RUNTIME_SERVICE_ACCOUNT: cfg.runtimeServiceAccount,
      _RELEASE_SHA256: cfg.artifactSha256,
      _RELEASE: cfg.release,
      _REVISION_TAG: cfg.revisionTag,
      _RELEASE_LABEL: cfg.releaseLabel,
      _RELEASE_SHA_LABEL: cfg.releaseShaLabel,
      _PREVIOUS_TRAFFIC: previousTraffic
    },
    tags: [cfg.buildTag, cfg.releaseLabel, cfg.releaseShaLabel],
    timeout: cfg.buildTimeout,
    options: {
      logging: 'CLOUD_LOGGING_ONLY',
      substitutionOption: 'MUST_MATCH'
    }
  };
}

function nexusDeploymentShellV1_() {
  return [
    'set -euo pipefail',
    'set +x',
    'SERVICE="${_SERVICE}"',
    'REGION="${_REGION}"',
    'PROJECT="${_PROJECT_ID}"',
    'RUNTIME_SA="${_RUNTIME_SERVICE_ACCOUNT}"',
    'TAG="${_REVISION_TAG}"',
    'PREVIOUS_TRAFFIC="${_PREVIOUS_TRAFFIC}"',
    'PROMOTED=0',
    'rollback_on_error() {',
    '  if [ "$$PROMOTED" = "1" ] && [ -n "$$PREVIOUS_TRAFFIC" ]; then',
    '    gcloud run services update-traffic "$$SERVICE" \\',
    '      --project="$$PROJECT" --region="$$REGION" \\',
    '      --to-revisions="$$PREVIOUS_TRAFFIC" --quiet >/dev/null 2>&1 || true',
    '  fi',
    '}',
    'trap rollback_on_error ERR',
    'gcloud run deploy "$$SERVICE" \\',
    '  --source=. \\',
    '  --project="$$PROJECT" \\',
    '  --region="$$REGION" \\',
    '  --service-account="$$RUNTIME_SA" \\',
    '  --no-traffic \\',
    '  --tag="$$TAG" \\',
    '  --update-env-vars="NEXUS_RELEASE_SHA256=${_RELEASE_SHA256},NEXUS_RELEASE=${_RELEASE}" \\',
    '  --update-labels="nexus-release=${_RELEASE_LABEL},nexus-sha=${_RELEASE_SHA_LABEL}" \\',
    '  --quiet',
    'export SERVICE_JSON="$$(gcloud run services describe "$$SERVICE" \\',
    '  --project="$$PROJECT" --region="$$REGION" --format=json)"',
    'python3 - "$$SERVICE" "$$RUNTIME_SA" "${_RELEASE_SHA256}" <<\'PY\'',
    'import json, sys',
    'doc = json.load(sys.stdin) if False else json.loads(__import__("os").environ["SERVICE_JSON"])',
    'service, service_account, release_sha = sys.argv[1:4]',
    'meta = doc.get("metadata", {})',
    'spec = doc.get("spec", {}).get("template", {}).get("spec", {})',
    'status = doc.get("status", {})',
    'if meta.get("name") != service: raise SystemExit("service_identity_mismatch")',
    'if spec.get("serviceAccountName") != service_account: raise SystemExit("service_account_mismatch")',
    'if status.get("latestCreatedRevisionName") != status.get("latestReadyRevisionName"):',
    '  raise SystemExit("revision_not_ready")',
    'env = {}',
    'for c in spec.get("containers", []):',
    '  for item in c.get("env", []): env[item.get("name")] = item.get("value")',
    'if env.get("NEXUS_RELEASE_SHA256") != release_sha:',
    '  raise SystemExit("release_identity_mismatch")',
    'PY',
    'REVISION="$$(gcloud run services describe "$$SERVICE" \\',
    '  --project="$$PROJECT" --region="$$REGION" \\',
    '  --format="value(status.latestCreatedRevisionName)")"',
    'TAG_URL="$$(gcloud run services describe "$$SERVICE" \\',
    '  --project="$$PROJECT" --region="$$REGION" \\',
    '  --format="value(status.traffic[?tag=$${TAG}].url)")"',
    'test -n "$$REVISION"',
    'test -n "$$TAG_URL"',
    'canary() {',
    '  local base="$$1"',
    '  local token=""',
    '  local path=""',
    '  for path in /health /; do',
    '    if curl --fail --silent --show-error --max-time 30 "$${base}$${path}" >/dev/null; then',
    '      return 0',
    '    fi',
    '  done',
    '  token="$$(curl --fail --silent --max-time 10 \\',
    '    -H "Metadata-Flavor: Google" \\',
    '    "http://metadata/computeMetadata/v1/instance/service-accounts/default/identity?audience=$${base}&format=full" || true)"',
    '  test -n "$$token" || return 1',
    '  for path in /health /; do',
    '    if curl --fail --silent --show-error --max-time 30 \\',
    '      -H "Authorization: Bearer $${token}" "$${base}$${path}" >/dev/null; then',
    '      return 0',
    '    fi',
    '  done',
    '  return 1',
    '}',
    'canary "$$TAG_URL"',
    'gcloud run services update-traffic "$$SERVICE" \\',
    '  --project="$$PROJECT" --region="$$REGION" \\',
    '  --to-tags="$${TAG}=100" --quiet',
    'PROMOTED=1',
    'SERVICE_URL="$$(gcloud run services describe "$$SERVICE" \\',
    '  --project="$$PROJECT" --region="$$REGION" --format="value(status.url)")"',
    'canary "$$SERVICE_URL"',
    'trap - ERR'
  ].join('\n');
}

function nexusRollbackBuildRequestV1_(cfg, trafficSpec) {
  return {
    steps: [{
      name: 'gcr.io/google.com/cloudsdktool/cloud-sdk:slim',
      entrypoint: 'gcloud',
      args: [
        'run',
        'services',
        'update-traffic',
        cfg.service,
        '--project=' + cfg.projectId,
        '--region=' + cfg.region,
        '--to-revisions=' + trafficSpec,
        '--quiet'
      ]
    }],
    tags: [cfg.buildTag, 'rollback', cfg.releaseShaLabel],
    timeout: '600s',
    options: {
      logging: 'CLOUD_LOGGING_ONLY'
    }
  };
}

function nexusFindMatchingBuildV1_(cfg) {
  const result = nexusGoogleJsonV1_(
      'https://cloudbuild.googleapis.com/v1/projects/' +
          encodeURIComponent(cfg.projectId) + '/locations/' +
          encodeURIComponent(cfg.region) +
          '/builds?projectId=' + encodeURIComponent(cfg.projectId) +
          '&pageSize=50&filter=' +
          encodeURIComponent('tags="' + cfg.buildTag + '"'),
      'get',
      null,
      [200],
      true);
  const builds = (result.body && result.body.builds) || [];
  const matches = builds.filter(function(build) {
    const substitutions = build.substitutions || {};
    const source = build.source && build.source.storageSource;
    return substitutions._SERVICE === cfg.service &&
        substitutions._REGION === cfg.region &&
        substitutions._RELEASE_SHA256 === cfg.artifactSha256 &&
        source &&
        source.bucket === cfg.bucket &&
        source.object === cfg.objectName;
  });
  matches.sort(function(a, b) {
    return String(b.createTime || '').localeCompare(String(a.createTime || ''));
  });
  return matches.length ? matches[0] : null;
}

function nexusGetBuildV1_(cfg, buildId) {
  if (!/^[a-zA-Z0-9-]+$/.test(String(buildId || ''))) {
    throw new Error('nexus_build_id_invalid');
  }
  const result = nexusGoogleJsonV1_(
      'https://cloudbuild.googleapis.com/v1/projects/' +
          encodeURIComponent(cfg.projectId) + '/locations/' +
          encodeURIComponent(cfg.region) + '/builds/' +
          encodeURIComponent(buildId) + '?projectId=' +
          encodeURIComponent(cfg.projectId),
      'get',
      null,
      [200, 404],
      true);
  return result.httpCode === 404 ? null : result.body;
}

function nexusBuildFromOperationV1_(operation) {
  if (!operation) return null;
  if (operation.metadata && operation.metadata.build) {
    return operation.metadata.build;
  }
  if (operation.response && operation.response.id) {
    return operation.response;
  }
  return null;
}

function nexusServiceProofV1_(cfg, service) {
  if (!service || !service.exists) {
    return {
      verified: false,
      reason: 'SERVICE_NOT_FOUND'
    };
  }
  const revisionReady = Boolean(
      service.latestCreatedRevision &&
      service.latestCreatedRevision === service.latestReadyRevision);
  const serviceAccountMatches = Boolean(
      service.template &&
      service.template.serviceAccount === cfg.runtimeServiceAccount);
  const releaseEnvMatches = (service.template.containers || []).some(
      function(container) {
        return (container.env || []).some(function(item) {
          return item.name === 'NEXUS_RELEASE_SHA256' &&
              item.value === cfg.artifactSha256;
        });
      });
  const promoted = (service.traffic || []).some(function(item) {
    return item.tag === cfg.revisionTag && item.percent === 100;
  });
  return {
    verified: revisionReady &&
        serviceAccountMatches &&
        releaseEnvMatches &&
        promoted,
    revisionReady: revisionReady,
    serviceAccountMatches: serviceAccountMatches,
    releaseIdentityMatches: releaseEnvMatches,
    promoted: promoted,
    latestReadyRevision: service.latestReadyRevision,
    latestCreatedRevision: service.latestCreatedRevision,
    uri: service.uri
  };
}

function nexusMakeStateV1_(
    cfg,
    artifact,
    staged,
    baseline,
    build,
    submissionMode) {
  return {
    contract: cfg.contract,
    release: cfg.release,
    artifactSha256: artifact.sha256,
    artifactDriveFileId: artifact.driveFileId,
    projectId: cfg.projectId,
    region: cfg.region,
    service: cfg.service,
    runtimeServiceAccount: cfg.runtimeServiceAccount,
    stagedObject: {
      bucket: staged.bucket,
      objectName: staged.objectName,
      generation: staged.generation,
      size: staged.size,
      sha256: staged.sha256
    },
    buildId: build.id,
    buildStatusAtSubmission: build.status || 'QUEUED',
    submissionMode: submissionMode,
    submittedAt: new Date().toISOString(),
    rollback: {
      serviceExisted: baseline.exists,
      previousReadyRevision: baseline.latestReadyRevision,
      previousCreatedRevision: baseline.latestCreatedRevision,
      previousTraffic: baseline.traffic || []
    }
  };
}

function nexusSubmissionReceiptV1_(status, artifact, state, build) {
  return {
    ok: true,
    status: status,
    contract: state.contract,
    release: state.release,
    target: {
      projectId: state.projectId,
      region: state.region,
      service: state.service,
      runtimeServiceAccount: state.runtimeServiceAccount
    },
    artifact: {
      driveFileId: artifact.driveFileId,
      name: artifact.name,
      size: artifact.size,
      sha256: artifact.sha256
    },
    stagedObject: state.stagedObject,
    buildId: build.id,
    buildStatus: build.status || 'QUEUED',
    rollback: state.rollback,
    submittedAt: state.submittedAt,
    manualUserTasks: [],
    ownerActionRequired: false
  };
}

function nexusStateMatchesReleaseV1_(state, cfg) {
  return state &&
      state.contract === cfg.contract &&
      state.artifactSha256 === cfg.artifactSha256 &&
      state.artifactDriveFileId === cfg.artifactDriveFileId &&
      state.projectId === cfg.projectId &&
      state.region === cfg.region &&
      state.service === cfg.service &&
      state.runtimeServiceAccount === cfg.runtimeServiceAccount;
}

function nexusReadStateV1_(props, key) {
  const raw = props.getProperty(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error('nexus_state_corrupt');
  }
}

function nexusWriteStateV1_(props, key, state) {
  props.setProperty(key, JSON.stringify(state));
}

function nexusGoogleJsonV1_(
    url,
    method,
    body,
    allowedCodes,
    includeEnvelope) {
  const options = {
    method: method,
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken()
    }
  };
  if (body !== null && body !== undefined) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(body);
  }
  const response = UrlFetchApp.fetch(url, options);
  const httpCode = response.getResponseCode();
  const allowed = allowedCodes || [200];
  if (allowed.indexOf(httpCode) < 0) {
    throw new Error('google_api_http_' + httpCode);
  }
  let parsed = {};
  const text = response.getContentText();
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch (error) {
      throw new Error('google_api_invalid_json_' + httpCode);
    }
  }
  return includeEnvelope ? {httpCode: httpCode, body: parsed} : parsed;
}

function nexusGoogleRawV1_(
    url,
    method,
    payload,
    contentType,
    allowedCodes,
    includeEnvelope) {
  const options = {
    method: method,
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken()
    }
  };
  if (payload !== null && payload !== undefined) {
    options.payload = payload;
    if (contentType) options.contentType = contentType;
  }
  const response = UrlFetchApp.fetch(url, options);
  const httpCode = response.getResponseCode();
  const allowed = allowedCodes || [200];
  if (allowed.indexOf(httpCode) < 0) {
    throw new Error('google_api_http_' + httpCode);
  }
  const value = {
    httpCode: httpCode,
    blob: response.getBlob()
  };
  return includeEnvelope ? value : value;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    NEXUS_CODEX_DEPLOYER_V1: NEXUS_CODEX_DEPLOYER_V1,
    nexusCodexPlanV1: nexusCodexPlanV1,
    nexusCodexStageAndSubmitV1: nexusCodexStageAndSubmitV1,
    nexusCodexStatusV1: nexusCodexStatusV1,
    nexusCodexSubmitRollbackV1: nexusCodexSubmitRollbackV1,
    nexusAssertTargetV1_: nexusAssertTargetV1_,
    nexusSha256HexV1_: nexusSha256HexV1_,
    nexusRollbackTrafficSpecV1_: nexusRollbackTrafficSpecV1_,
    nexusBuildRequestV1_: nexusBuildRequestV1_,
    nexusRollbackBuildRequestV1_: nexusRollbackBuildRequestV1_,
    nexusDeploymentShellV1_: nexusDeploymentShellV1_,
    nexusReadAndVerifyDriveArtifactV1_:
        nexusReadAndVerifyDriveArtifactV1_,
    nexusStateMatchesReleaseV1_: nexusStateMatchesReleaseV1_
  };
}
