import { sha256Hex } from "./contracts.mjs";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function revisionId(value = "") {
  return String(value).split("/").filter(Boolean).at(-1) || "";
}

function canonicalTraffic(items = []) {
  return items
    .map((item) => ({
      type: item.type || "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
      revision: revisionId(item.revision),
      percent: Number(item.percent || 0),
      tag: item.tag || "",
    }))
    .filter((item) => item.revision || item.tag || item.percent)
    .sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)));
}

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export class GoogleCloudAdapter {
  constructor(env = process.env, fetchImpl = fetch) {
    this.env = env;
    this.fetch = fetchImpl;
    this.accessToken = null;
    this.accessTokenExpiresAt = 0;
  }

  async token() {
    if (this.accessToken && this.accessTokenExpiresAt > Date.now() + 60000) return this.accessToken;
    const response = await this.fetch("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", { headers: { "Metadata-Flavor": "Google" } });
    if (!response.ok) throw new Error(`metadata token failed: ${response.status}`);
    const body = await response.json();
    this.accessToken = body.access_token;
    this.accessTokenExpiresAt = Date.now() + Number(body.expires_in || 300) * 1000;
    return this.accessToken;
  }

  async api(url, options = {}, expected = [200]) {
    const token = await this.token();
    const response = await this.fetch(url, { ...options, headers: { accept: "application/json", authorization: `Bearer ${token}`, ...(options.headers || {}) } });
    const text = await response.text();
    let body; try { body = text ? JSON.parse(text) : {}; } catch { body = { text: text.slice(0, 2000) }; }
    if (!expected.includes(response.status)) throw new Error(`provider ${response.status}: ${JSON.stringify(body).slice(0, 2000)}`);
    return { status: response.status, body };
  }

  async readService({ project, region, service }) {
    return (await this.api(`https://run.googleapis.com/v2/projects/${encodeURIComponent(project)}/locations/${encodeURIComponent(region)}/services/${encodeURIComponent(service)}`)).body;
  }

  async readServiceOptional(target) {
    const response = await this.api(
      `https://run.googleapis.com/v2/projects/${encodeURIComponent(target.project)}/locations/${encodeURIComponent(target.region)}/services/${encodeURIComponent(target.service)}`,
      {},
      [200, 404],
    );
    return response.status === 404 ? null : response.body;
  }

  async readRevision({ project, region, service, revision }) {
    return (await this.api(
      `https://run.googleapis.com/v2/projects/${encodeURIComponent(project)}/locations/${encodeURIComponent(region)}/services/${encodeURIComponent(service)}/revisions/${encodeURIComponent(revision)}`,
    )).body;
  }

  ciosControlObject(binding, suffix) {
    return `cios-production/${binding.service}/${binding.deploymentKey || binding.idempotencyKey}/${suffix}.json`;
  }

  async readCiosControlRecord(binding, suffix) {
    const bucket = this.env.CIOS_CONTROL_BUCKET || `fo-control-plane-${binding.project}`;
    const object = this.ciosControlObject(binding, suffix);
    const response = await this.api(
      `https://storage.googleapis.com/download/storage/v1/b/${encodeURIComponent(bucket)}/o/${encodeURIComponent(object)}?alt=media`,
      {},
      [200, 404],
    );
    return response.status === 404 ? null : response.body;
  }

  async writeCiosControlRecord(binding, suffix, record) {
    const bucket = this.env.CIOS_CONTROL_BUCKET || `fo-control-plane-${binding.project}`;
    const object = this.ciosControlObject(binding, suffix);
    const receipt = { ...record };
    receipt.receiptDigest = sha256Hex(Buffer.from(JSON.stringify(receipt)));
    const response = await this.api(
      `https://storage.googleapis.com/upload/storage/v1/b/${encodeURIComponent(bucket)}/o?uploadType=media&name=${encodeURIComponent(object)}&ifGenerationMatch=0`,
      { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(receipt) },
      [200, 412],
    );
    if (response.status === 412) {
      const existing = await this.readCiosControlRecord(binding, suffix);
      if (!existing || existing.receiptDigest !== receipt.receiptDigest) {
        throw new Error(`immutable CIOS ${suffix} receipt collision`);
      }
      return { ...existing, reused: true };
    }
    return receipt;
  }

  async accessSecret(project, secret) {
    const response = await this.api(
      `https://secretmanager.googleapis.com/v1/projects/${encodeURIComponent(project)}/secrets/${encodeURIComponent(secret)}/versions/latest:access`,
    );
    const encoded = response.body.payload?.data;
    if (!encoded) throw new Error(`Secret Manager payload missing for ${secret}`);
    return Buffer.from(encoded, "base64").toString("utf8");
  }

  async patchServiceTraffic(binding, traffic) {
    const service = await this.readService(binding);
    const response = await this.api(
      `https://run.googleapis.com/v2/${service.name}?updateMask=traffic`,
      {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: service.name, traffic }),
      },
      [200],
    );
    await this.waitOperation(response.body.name);
    return this.readService(binding);
  }

  async readCiosProduction(binding) {
    const service = await this.readServiceOptional(binding);
    if (!service) {
      return { ok: true, status: "CIOS_SERVICE_ABSENT", target: binding, service: null };
    }
    return {
      ok: true,
      status: "CIOS_PRODUCTION_READ",
      target: binding,
      service: {
        name: service.name,
        uri: service.uri || null,
        latestCreatedRevision: service.latestCreatedRevision || null,
        latestReadyRevision: service.latestReadyRevision || null,
        traffic: canonicalTraffic(service.trafficStatuses || service.traffic || []),
        serviceAccount: service.template?.serviceAccount || null,
        image: service.template?.containers?.[0]?.image || null,
      },
    };
  }

  async readCiosPersistence(binding) {
    const [instanceProject, instanceRegion, instanceId] = binding.cloudSqlInstance.split(":");
    if (instanceProject !== binding.project || instanceRegion !== binding.region || !instanceId) {
      throw new Error("CIOS Cloud SQL instance binding is invalid");
    }
    const instance = (await this.api(
      `https://sqladmin.googleapis.com/sql/v1beta4/projects/${encodeURIComponent(binding.project)}/instances/${encodeURIComponent(instanceId)}`,
    )).body;
    const backups = (await this.api(
      `https://sqladmin.googleapis.com/sql/v1beta4/projects/${encodeURIComponent(binding.project)}/instances/${encodeURIComponent(instanceId)}/backupRuns?maxResults=10`,
    )).body.items || [];
    const latestSuccessful = backups.find((item) => item.status === "SUCCESSFUL") || null;
    const backup = instance.settings?.backupConfiguration || {};
    const controls = {
      postgres: String(instance.databaseVersion || "").startsWith("POSTGRES_"),
      regionExact: instance.region === binding.region,
      backupsEnabled: backup.enabled === true,
      pointInTimeRecoveryEnabled: backup.pointInTimeRecoveryEnabled === true,
      retainedTransactionLogDays: Number(backup.transactionLogRetentionDays || 0) >= 1,
      storageAutoResize: instance.settings?.storageAutoResize === true,
      deletionProtection: instance.settings?.deletionProtectionEnabled === true,
      successfulBackupPresent: latestSuccessful !== null,
    };
    return {
      ok: Object.values(controls).every(Boolean),
      status: Object.values(controls).every(Boolean)
        ? "CIOS_MANAGED_POSTGRES_RECOVERY_READY"
        : "CIOS_MANAGED_POSTGRES_RECOVERY_BLOCKED",
      project: binding.project,
      region: binding.region,
      instance: instance.name || instanceId,
      connectionName: instance.connectionName || null,
      databaseVersion: instance.databaseVersion || null,
      availabilityType: instance.settings?.availabilityType || null,
      controls,
      latestSuccessfulBackup: latestSuccessful
        ? { id: latestSuccessful.id || null, startTime: latestSuccessful.startTime || null, endTime: latestSuccessful.endTime || null, type: latestSuccessful.type || null }
        : null,
      restoreExecutionAttempted: false,
      secretValuesReturned: false,
    };
  }

  async deployCiosZeroTraffic(binding) {
    const replayBinding = { ...binding, deploymentKey: binding.idempotencyKey };
    const existing = await this.readCiosControlRecord(replayBinding, "deploy");
    if (existing) {
      const revision = await this.readRevision({ ...binding, revision: existing.candidate.revision });
      if (revision.containers?.[0]?.image !== binding.image || existing.sourceSha !== binding.sourceSha) {
        throw new Error("CIOS deployment receipt no longer matches the requested immutable image");
      }
      return { ...existing, reused: true };
    }

    const persistence = await this.readCiosPersistence(binding);
    if (!persistence.ok) {
      throw new Error(`CIOS managed persistence preflight failed: ${persistence.status}`);
    }
    const before = await this.readServiceOptional(binding);
    const baselineTraffic = canonicalTraffic(before?.traffic || []);
    const baselineFingerprint = sha256Hex(Buffer.from(JSON.stringify(baselineTraffic)));
    const revisionName = `${binding.service}-${binding.sourceSha.slice(0, 12)}`;
    const operationLabel = sha256Hex(Buffer.from(binding.idempotencyKey)).slice(0, 16);
    const traffic = baselineTraffic.filter((item) => item.tag !== binding.tag);
    traffic.push({
      type: "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
      revision: revisionName,
      percent: 0,
      tag: binding.tag,
    });

    const secretEnv = (name, secret) => ({
      name,
      valueSource: { secretKeyRef: { secret, version: "latest" } },
    });
    const body = {
      labels: {
        "fo-system": "cios-production",
        "cios-source": binding.sourceSha.slice(0, 12),
        "cios-operation": operationLabel,
      },
      ingress: "INGRESS_TRAFFIC_ALL",
      template: {
        revision: revisionName,
        serviceAccount: binding.serviceAccount,
        maxInstanceRequestConcurrency: 8,
        timeout: "300s",
        scaling: { minInstanceCount: 0, maxInstanceCount: 4 },
        volumes: [{ name: "cloudsql", cloudSqlInstance: { instances: [binding.cloudSqlInstance] } }],
        containers: [{
          image: binding.image,
          ports: [{ name: "http1", containerPort: 8080 }],
          env: [
            { name: "CIOS_STORAGE_BACKEND", value: "postgres" },
            { name: "CIOS_EXPECTED_SOURCE_SHA", value: binding.sourceSha },
            { name: "CIOS_RUNTIME_SOURCE_SHA", value: binding.sourceSha },
            { name: "CIOS_RUNTIME_IDENTITY", value: binding.serviceAccount },
            { name: "CIOS_TENANT_ID", value: binding.tenantId },
            { name: "CIOS_RUNTIME_USER_ID", value: binding.runtimeUserId },
            { name: "CIOS_APPLY_MIGRATIONS", value: "true" },
            { name: "CIOS_DB_POOL_MAX_SIZE", value: "8" },
            secretEnv("CIOS_DATABASE_URL", binding.databaseSecret),
            secretEnv("CIOS_AUDIT_DATABASE_URL", binding.auditDatabaseSecret),
            secretEnv("CIOS_BEARER_TOKEN", binding.bearerSecret),
          ],
          volumeMounts: [{ name: "cloudsql", mountPath: "/cloudsql" }],
          startupProbe: { tcpSocket: { port: 8080 }, initialDelaySeconds: 0, timeoutSeconds: 2, periodSeconds: 3, failureThreshold: 40 },
          livenessProbe: { tcpSocket: { port: 8080 }, initialDelaySeconds: 5, timeoutSeconds: 2, periodSeconds: 10, failureThreshold: 3 },
          resources: { limits: { cpu: "1", memory: "1Gi" }, cpuIdle: true },
        }],
      },
      traffic,
    };
    const base = `https://run.googleapis.com/v2/projects/${binding.project}/locations/${binding.region}/services`;
    const submitted = before
      ? await this.api(
        `${base}/${binding.service}?updateMask=labels,ingress,template,traffic`,
        { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ ...body, name: before.name }) },
        [200],
      )
      : await this.api(
        `${base}?serviceId=${encodeURIComponent(binding.service)}`,
        { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) },
        [200],
      );
    await this.waitOperation(submitted.body.name);
    const after = await this.readService(binding);
    const revision = await this.readRevision({ ...binding, revision: revisionName });
    const rawTraffic = after.trafficStatuses || after.traffic || [];
    const observedTraffic = canonicalTraffic(rawTraffic);
    const candidateTraffic = rawTraffic.find((item) => revisionId(item.revision) === revisionName && item.tag === binding.tag);
    if (revisionId(after.latestReadyRevision) !== revisionName || revision.containers?.[0]?.image !== binding.image) {
      throw new Error("CIOS zero-traffic revision or digest readback mismatch");
    }
    if (!candidateTraffic || Number(candidateTraffic.percent || 0) !== 0) {
      throw new Error("CIOS candidate is not bound to the requested zero-traffic tag");
    }
    const baselineStillExact = sameJson(
      baselineTraffic,
      observedTraffic.filter((item) => item.revision !== revisionName && item.tag !== binding.tag),
    );
    if (!baselineStillExact) throw new Error("CIOS baseline traffic changed during zero-traffic deployment");
    return this.writeCiosControlRecord(replayBinding, "deploy", {
      ok: true,
      status: "CIOS_ZERO_TRAFFIC_DEPLOYED",
      checkedAt: new Date().toISOString(),
      project: binding.project,
      region: binding.region,
      service: binding.service,
      sourceSha: binding.sourceSha,
      image: binding.image,
      deploymentKey: binding.idempotencyKey,
      baseline: { traffic: baselineTraffic, fingerprint: baselineFingerprint, latestReadyRevision: before?.latestReadyRevision || null },
      candidate: { revision: revisionName, tag: binding.tag, uri: candidateTraffic.uri || null, percent: 0, serviceAccount: revision.serviceAccount || binding.serviceAccount },
      secretBindings: [binding.databaseSecret, binding.auditDatabaseSecret, binding.bearerSecret],
      cloudSqlInstance: binding.cloudSqlInstance,
      persistence: {
        status: persistence.status,
        controls: persistence.controls,
        latestSuccessfulBackup: persistence.latestSuccessfulBackup,
      },
    });
  }

  async invokeCiosJson({ url, audience, token, method = "GET", body = null, idempotencyKey = null }) {
    const identity = await this.identityToken(audience);
    const headers = {
      accept: "application/json",
      authorization: `Bearer ${identity}`,
      "x-cios-token": token,
    };
    if (body !== null) headers["content-type"] = "application/json";
    if (idempotencyKey) headers["idempotency-key"] = idempotencyKey;
    const response = await this.fetch(url, {
      method,
      headers,
      body: body === null ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let payload;
    try { payload = text ? JSON.parse(text) : {}; } catch { payload = { text: text.slice(0, 1000) }; }
    if (!response.ok) throw new Error(`CIOS canary ${response.status}: ${JSON.stringify(payload).slice(0, 1000)}`);
    return payload;
  }

  async verifyCiosCanary(binding) {
    const deploy = await this.readCiosControlRecord(binding, "deploy");
    if (!deploy || deploy.sourceSha !== binding.sourceSha || deploy.candidate.revision !== binding.revision) {
      throw new Error("verified immutable CIOS deployment receipt is required");
    }
    const service = await this.readService(binding);
    const rawTraffic = service.trafficStatuses || service.traffic || [];
    const candidate = rawTraffic.find((item) => revisionId(item.revision) === binding.revision && item.tag === deploy.candidate.tag);
    if (!candidate || Number(candidate.percent || 0) !== 0 || !candidate.uri) {
      throw new Error("CIOS semantic canary requires the exact zero-traffic tagged revision");
    }
    const applicationToken = await this.accessSecret(binding.project, binding.bearerSecret);
    const base = candidate.uri.replace(/\/$/, "");
    const health = await this.invokeCiosJson({ url: `${base}/health`, audience: service.uri, token: applicationToken });
    const ready = await this.invokeCiosJson({ url: `${base}/ready`, audience: service.uri, token: applicationToken });
    if (
      health.status !== "ok" ||
      health.runtime_source_sha !== binding.sourceSha ||
      health.storage_backend !== "postgres" ||
      health.managed_persistence_configured !== true ||
      health.append_only_audit_configured !== true ||
      health.audit_chain_valid !== true ||
      ready.ready !== true
    ) {
      throw new Error("CIOS semantic health or persistence contract mismatch");
    }
    const eventId = `cios-canary-${binding.sourceSha.slice(0, 12)}-${sha256Hex(Buffer.from(binding.canaryKey)).slice(0, 12)}`;
    const event = {
      event_type: "CIOS_PROVIDER_SEMANTIC_CANARY",
      source: "federation-omega-operator",
      subject_id: binding.revision,
      payload: { source_sha: binding.sourceSha, revision: binding.revision },
      domain: "GOVERNANCE",
      information_class: "PUBLIC",
      materiality: 0.1,
      event_id: eventId,
      occurred_at: binding.occurredAt,
    };
    const first = await this.invokeCiosJson({
      url: `${base}/v1/events`, audience: service.uri, token: applicationToken,
      method: "POST", body: event, idempotencyKey: binding.canaryKey,
    });
    const replay = await this.invokeCiosJson({
      url: `${base}/v1/events`, audience: service.uri, token: applicationToken,
      method: "POST", body: event, idempotencyKey: binding.canaryKey,
    });
    if (replay.replayed !== true || !first.receipt_hash || replay.receipt_hash !== first.receipt_hash) {
      throw new Error("CIOS idempotent persistence replay mismatch");
    }
    return this.writeCiosControlRecord(binding, `canary-${binding.canaryKey}`, {
      ok: true,
      status: "CIOS_ZERO_TRAFFIC_CANARY_VERIFIED",
      checkedAt: new Date().toISOString(),
      project: binding.project,
      region: binding.region,
      service: binding.service,
      sourceSha: binding.sourceSha,
      revision: binding.revision,
      deploymentKey: binding.deploymentKey,
      canaryKey: binding.canaryKey,
      taggedUri: candidate.uri,
      health: {
        status: health.status,
        runtimeMode: health.runtime_mode,
        storageBackend: health.storage_backend,
        databaseQuickCheck: health.database_quick_check,
        auditChainValid: health.audit_chain_valid,
      },
      semantic: { eventId, receiptHash: first.receipt_hash, replayVerified: true },
      providerIdentityTokenUsed: true,
      applicationSecretValueReturned: false,
    });
  }

  async rollbackCiosTraffic(binding) {
    const deploy = await this.readCiosControlRecord(binding, "deploy");
    if (!deploy || deploy.sourceSha !== binding.sourceSha || deploy.candidate.revision !== binding.revision) {
      throw new Error("CIOS rollback requires the exact immutable deployment receipt");
    }
    const rollbackTraffic = [
      ...canonicalTraffic(deploy.baseline.traffic),
      {
        type: "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
        revision: binding.revision,
        percent: 0,
        tag: deploy.candidate.tag,
      },
    ];
    const after = await this.patchServiceTraffic(binding, rollbackTraffic);
    const observed = canonicalTraffic(after.trafficStatuses || after.traffic || []);
    const baseline = canonicalTraffic(deploy.baseline.traffic);
    const observedBaseline = observed.filter(
      (item) => item.revision !== binding.revision && item.tag !== deploy.candidate.tag,
    );
    const preservedCandidate = observed.find(
      (item) => item.revision === binding.revision && item.tag === deploy.candidate.tag,
    );
    if (!sameJson(observedBaseline, baseline) || !preservedCandidate || preservedCandidate.percent !== 0) {
      throw new Error("CIOS baseline rollback or zero-traffic recovery readback mismatch");
    }
    return this.writeCiosControlRecord(binding, "rollback", {
      ok: true,
      status: "CIOS_BASELINE_TRAFFIC_RESTORED",
      checkedAt: new Date().toISOString(),
      project: binding.project,
      region: binding.region,
      service: binding.service,
      sourceSha: binding.sourceSha,
      revision: binding.revision,
      deploymentKey: binding.deploymentKey,
      baselineFingerprint: deploy.baseline.fingerprint,
      traffic: observed,
      candidateRevisionPreserved: true,
    });
  }

  async promoteCiosTraffic(binding) {
    const deploy = await this.readCiosControlRecord(binding, "deploy");
    const canary = await this.readCiosControlRecord(binding, `canary-${binding.canaryKey}`);
    const rollback = await this.readCiosControlRecord(binding, "rollback");
    if (!deploy || !canary || !rollback) {
      throw new Error("CIOS promotion requires deployment, semantic canary and rollback receipts");
    }
    if (
      deploy.sourceSha !== binding.sourceSha ||
      deploy.candidate.revision !== binding.revision ||
      canary.revision !== binding.revision ||
      rollback.baselineFingerprint !== deploy.baseline.fingerprint
    ) {
      throw new Error("CIOS promotion receipt binding mismatch");
    }
    const traffic = [{
      type: "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
      revision: binding.revision,
      percent: 100,
      tag: deploy.candidate.tag,
    }];
    const after = await this.patchServiceTraffic(binding, traffic);
    const observed = canonicalTraffic(after.trafficStatuses || after.traffic || []);
    if (!sameJson(observed, canonicalTraffic(traffic))) {
      throw new Error("CIOS production traffic promotion readback mismatch");
    }
    return this.writeCiosControlRecord(binding, `promotion-${binding.canaryKey}`, {
      ok: true,
      status: "CIOS_PRODUCTION_TRAFFIC_PROMOTED",
      checkedAt: new Date().toISOString(),
      project: binding.project,
      region: binding.region,
      service: binding.service,
      sourceSha: binding.sourceSha,
      image: deploy.image,
      revision: binding.revision,
      deploymentKey: binding.deploymentKey,
      canaryReceiptDigest: canary.receiptDigest,
      rollbackReceiptDigest: rollback.receiptDigest,
      traffic: observed,
      rollbackPlan: deploy.baseline,
    });
  }

  async identityToken(audience) {
    const url = `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(audience)}&format=full`;
    const response = await this.fetch(url, { headers: { "Metadata-Flavor": "Google" } });
    if (!response.ok) throw new Error(`metadata identity token failed: ${response.status}`);
    return response.text();
  }

  async verifyServiceHealth(target) {
    const service = await this.readService(target);
    const audience = service.uri;
    const identity = await this.identityToken(audience);
    const response = await this.fetch(`${audience.replace(/\/$/, "")}/health`, { headers: { accept: "application/json", authorization: `Bearer ${identity}` } });
    const body = await response.json();
    return { ok: response.ok && body.ok === true, status: response.ok && body.ok === true ? "TARGET_HEALTH_VERIFIED" : "TARGET_HEALTH_FAILED", service: target.service, latestReadyRevision: service.latestReadyRevision || null, uri: service.uri, health: body };
  }

  async readBuild(payload = {}) {
    const project = payload.project || this.env.PROJECT_ID;
    const region = payload.region || this.env.REGION;
    if (!payload.buildId) throw new Error("buildId is required");
    return (await this.api(`https://cloudbuild.googleapis.com/v1/projects/${encodeURIComponent(project)}/locations/${encodeURIComponent(region)}/builds/${encodeURIComponent(payload.buildId)}`)).body;
  }

  vertexBase(location) {
    return location === "global"
      ? "https://aiplatform.googleapis.com"
      : `https://${encodeURIComponent(location)}-aiplatform.googleapis.com`;
  }

  vertexModelUrl({ project, location, model }, suffix = "") {
    return `${this.vertexBase(location)}/v1/projects/${encodeURIComponent(project)}/locations/${encodeURIComponent(location)}/publishers/google/models/${encodeURIComponent(model)}${suffix}`;
  }

  async readGeminiVertexCapability(target) {
    const service = await this.api(
      `https://serviceusage.googleapis.com/v1/projects/${encodeURIComponent(target.project)}/services/aiplatform.googleapis.com`,
    );
    if (service.body.state !== "ENABLED") {
      return {
        ok: false,
        status: "VERTEX_AI_API_DISABLED",
        provider: "vertex",
        authMode: "CLOUD_RUN_SERVICE_IDENTITY",
        target,
        serviceState: service.body.state || "UNKNOWN",
        semanticExecutionAttempted: false,
        incrementalCost: 0,
        silentFallback: false,
      };
    }
    const publisherModel = await this.api(this.vertexModelUrl(target));
    return {
      ok: true,
      status: "GEMINI_VERTEX_CAPABILITY_READ",
      provider: "vertex",
      authMode: "CLOUD_RUN_SERVICE_IDENTITY",
      target,
      serviceState: service.body.state,
      modelReadback: {
        name: publisherModel.body.name || null,
        versionId: publisherModel.body.versionId || null,
        displayName: publisherModel.body.displayName || null,
        launchStage: publisherModel.body.launchStage || null,
        supportedActions: publisherModel.body.supportedActions || null,
      },
      semanticExecutionAttempted: false,
      incrementalCost: 0,
      silentFallback: false,
    };
  }

  async verifyGeminiVertexSemantic(canary) {
    const capability = await this.readGeminiVertexCapability(canary);
    if (!capability.ok) throw new Error(`Gemini Vertex capability unavailable: ${capability.status}`);
    const request = {
      contents: [{ role: "user", parts: [{ text: `Return exactly this nonce and nothing else: ${canary.nonce}` }] }],
      generationConfig: {
        candidateCount: 1,
        temperature: 0,
        maxOutputTokens: canary.maxOutputTokens,
      },
    };
    const response = await this.api(
      this.vertexModelUrl(canary, ":generateContent"),
      { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request) },
    );
    const observed = (response.body.candidates?.[0]?.content?.parts || [])
      .map((part) => typeof part.text === "string" ? part.text : "")
      .join("")
      .trim();
    if (observed !== canary.nonce) {
      throw new Error("Gemini Vertex semantic nonce mismatch");
    }
    const usage = response.body.usageMetadata || {};
    return {
      ok: true,
      status: "GEMINI_VERTEX_SEMANTIC_VERIFIED",
      provider: "vertex",
      authMode: "CLOUD_RUN_SERVICE_IDENTITY",
      target: {
        project: canary.project,
        location: canary.location,
        model: canary.model,
        tenantId: canary.tenantId,
      },
      nonceVerified: true,
      idempotencyKey: canary.idempotencyKey,
      usage: {
        promptTokenCount: Number(usage.promptTokenCount || 0),
        candidatesTokenCount: Number(usage.candidatesTokenCount || 0),
        totalTokenCount: Number(usage.totalTokenCount || 0),
      },
      silentFallback: false,
    };
  }

  async downloadDriveFile(fileId) {
    const token = await this.token();
    const response = await this.fetch(`https://www.googleapis.com/drive/v3/files/${encodeURIComponent(fileId)}?alt=media&supportsAllDrives=true`, { headers: { authorization: `Bearer ${token}` } });
    if (!response.ok) throw new Error(`Drive artifact read failed: ${response.status}`);
    return Buffer.from(await response.arrayBuffer());
  }

  async stageSource(binding, bytes) {
    const bucket = this.env.CFRE_SOURCE_BUCKET || `fo-control-plane-${binding.project}`;
    const object = `cfre-private-runtime/source-${binding.sourceSha256}.tar.gz`;
    const metadataUrl = `https://storage.googleapis.com/storage/v1/b/${encodeURIComponent(bucket)}/o/${encodeURIComponent(object)}`;
    try {
      const existing = await this.api(metadataUrl, {}, [200, 404]);
      if (existing.status === 200) {
        if (existing.body.metadata?.sha256 !== binding.sourceSha256) throw new Error("immutable source object collision");
        return { bucket, object, generation: existing.body.generation, reused: true };
      }
    } catch (error) {
      if (!String(error.message).includes("404")) throw error;
    }
    const boundary = `fo-cfre-${binding.sourceSha256.slice(0, 16)}`;
    const metadata = JSON.stringify({ name: object, contentType: "application/gzip", metadata: { sha256: binding.sourceSha256, embeddedRepairSha256: binding.embeddedRepairSha256, manifestSha256: binding.manifestSha256 } });
    const multipart = Buffer.concat([
      Buffer.from(`--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${metadata}\r\n--${boundary}\r\nContent-Type: application/gzip\r\n\r\n`),
      bytes,
      Buffer.from(`\r\n--${boundary}--`),
    ]);
    const uploaded = await this.api(`https://storage.googleapis.com/upload/storage/v1/b/${encodeURIComponent(bucket)}/o?uploadType=multipart&ifGenerationMatch=0`, { method: "POST", headers: { "content-type": `multipart/related; boundary=${boundary}` }, body: multipart }, [200]);
    return { bucket, object, generation: uploaded.body.generation, reused: false };
  }

  async submitBuild(binding, staged) {
    const repository = this.env.CFRE_ARTIFACT_REPOSITORY || "fo-runtime";
    const image = `${binding.region}-docker.pkg.dev/${binding.project}/${repository}/${binding.service}:cfre-${binding.sourceSha256.slice(0, 24)}`;
    const request = {
      source: { storageSource: { bucket: staged.bucket, object: staged.object, generation: staged.generation } },
      steps: [
        { name: "gcr.io/cloud-builders/docker", args: ["build", "--pull", "-t", image, "."] },
        { name: "gcr.io/cloud-builders/docker", args: ["push", image] },
      ],
      images: [image],
      timeout: "1200s",
      options: { logging: "CLOUD_LOGGING_ONLY", machineType: "E2_HIGHCPU_8" },
      tags: ["cfre-omega", binding.sourceSha256.slice(0, 16)],
    };
    const submitted = await this.api(`https://cloudbuild.googleapis.com/v1/projects/${binding.project}/locations/${binding.region}/builds`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request) }, [200]);
    const buildId = submitted.body.metadata?.build?.id || submitted.body.name?.split("/").at(-1);
    if (!buildId) throw new Error("Cloud Build id missing from submission");
    return { buildId, image };
  }

  async waitBuild(project, region, buildId, timeoutMs = 1200000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const build = await this.readBuild({ project, region, buildId });
      if (["SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"].includes(build.status)) {
        if (build.status !== "SUCCESS") throw new Error(`Cloud Build terminal status ${build.status}`);
        return build;
      }
      await sleep(5000);
    }
    throw new Error("Cloud Build polling timeout");
  }

  async waitOperation(name, timeoutMs = 600000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const operation = (await this.api(`https://run.googleapis.com/v2/${name}`)).body;
      if (operation.done) {
        if (operation.error) throw new Error(`Cloud Run operation failed: ${JSON.stringify(operation.error)}`);
        return operation.response || operation;
      }
      await sleep(3000);
    }
    throw new Error("Cloud Run operation polling timeout");
  }

  async deployPrivateService(binding, image) {
    let before = null;
    try { before = await this.readService(binding); } catch (error) { if (!String(error.message).includes("404")) throw error; }
    const body = {
      labels: { "fo-system": "cfre-omega", "fo-binding": binding.embeddedRepairSha256.slice(0, 16) },
      ingress: "INGRESS_TRAFFIC_ALL",
      template: {
        serviceAccount: binding.serviceAccount,
        maxInstanceRequestConcurrency: 8,
        timeout: "300s",
        scaling: { minInstanceCount: 0, maxInstanceCount: 1 },
        containers: [{ image, env: [
          { name: "CFRE_REPAIR_SHA256", value: binding.embeddedRepairSha256 },
          { name: "CFRE_MANIFEST_SHA256", value: binding.manifestSha256 },
        ], resources: { limits: { cpu: "1", memory: "512Mi" }, cpuIdle: true } }],
      },
    };
    const base = `https://run.googleapis.com/v2/projects/${binding.project}/locations/${binding.region}/services`;
    const result = before
      ? await this.api(`${base}/${binding.service}?updateMask=labels,ingress,template`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ ...body, name: before.name }) }, [200])
      : await this.api(`${base}?serviceId=${encodeURIComponent(binding.service)}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }, [200]);
    const response = await this.waitOperation(result.body.name);
    const after = await this.readService(binding);
    const actualImage = after.template?.containers?.[0]?.image;
    if (!after.latestReadyRevision || actualImage !== image) throw new Error("Cloud Run semantic readback mismatch");
    return { before: before ? { latestReadyRevision: before.latestReadyRevision || null, image: before.template?.containers?.[0]?.image || null } : null, after: { name: after.name, uri: after.uri, latestReadyRevision: after.latestReadyRevision, image: actualImage, serviceAccount: after.template?.serviceAccount }, operation: response };
  }

  async bindCfrePrivateRuntime(binding) {
    const bytes = await this.downloadDriveFile(binding.sourceDriveId);
    const observedSha256 = sha256Hex(bytes);
    if (observedSha256 !== binding.sourceSha256) throw new Error(`source hash mismatch: ${observedSha256}`);
    const staged = await this.stageSource(binding, bytes);
    const submitted = await this.submitBuild(binding, staged);
    const build = await this.waitBuild(binding.project, binding.region, submitted.buildId);
    const service = await this.deployPrivateService(binding, submitted.image);
    return {
      ok: true,
      status: "CFRE_PRIVATE_RUNTIME_BOUND",
      identity: "CFRE-OMEGA",
      sourceSha256: observedSha256,
      embeddedRepairSha256: binding.embeddedRepairSha256,
      manifestSha256: binding.manifestSha256,
      build: { id: build.id, status: build.status, image: submitted.image },
      service,
      idempotencyKey: binding.idempotencyKey,
      rollback: service.before,
    };
  }
}
