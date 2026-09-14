const DEFAULT_LIMITS = Object.freeze({
  maxPools: 20,
  maxProvidersPerPool: 100,
  maxServiceAccounts: 100,
  maxPages: 3,
  providerConcurrency: 4,
  requestBudget: 25,
  timeoutMs: 5_000,
});

const MAX_LIMITS = DEFAULT_LIMITS;
const PROJECT_ID_PATTERN = /^(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[0-9]{6,20})$/;
const POOL_NAME_PATTERN =
  /^projects\/[^/]+\/locations\/global\/workloadIdentityPools\/([a-z0-9-]{4,32})$/;

export class InventoryInputError extends Error {
  constructor(code) {
    super(code);
    this.name = "InventoryInputError";
    this.code = code;
    this.httpStatus = 400;
  }
}

export class InventoryConfigurationError extends Error {
  constructor(code) {
    super(code);
    this.name = "InventoryConfigurationError";
    this.code = code;
    this.httpStatus = 500;
  }
}

export class InventoryDependencyError extends Error {
  constructor(code, httpStatus = 502) {
    super(code);
    this.name = "InventoryDependencyError";
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

class RequestBudget {
  constructor(limit) {
    this.limit = limit;
    this.used = 0;
  }

  take() {
    if (this.used >= this.limit) {
      throw new InventoryDependencyError("DEPENDENCY_REQUEST_BUDGET_EXCEEDED", 503);
    }
    this.used += 1;
  }
}

function boundedInteger(value, name, maximum) {
  if (value === undefined) return maximum;
  if (!Number.isInteger(value) || value < 1 || value > maximum) {
    throw new InventoryInputError(`INVALID_LIMIT_${name.toUpperCase()}`);
  }
  return value;
}

function effectiveLimits(requested = {}) {
  if (!requested || typeof requested !== "object" || Array.isArray(requested)) {
    throw new InventoryInputError("INVALID_LIMITS");
  }
  return Object.freeze({
    maxPools: boundedInteger(requested.maxPools, "maxPools", MAX_LIMITS.maxPools),
    maxProvidersPerPool: boundedInteger(
      requested.maxProvidersPerPool,
      "maxProvidersPerPool",
      MAX_LIMITS.maxProvidersPerPool,
    ),
    maxServiceAccounts: boundedInteger(
      requested.maxServiceAccounts,
      "maxServiceAccounts",
      MAX_LIMITS.maxServiceAccounts,
    ),
    maxPages: boundedInteger(requested.maxPages, "maxPages", MAX_LIMITS.maxPages),
    providerConcurrency: boundedInteger(
      requested.providerConcurrency,
      "providerConcurrency",
      MAX_LIMITS.providerConcurrency,
    ),
    requestBudget: boundedInteger(
      requested.requestBudget,
      "requestBudget",
      MAX_LIMITS.requestBudget,
    ),
    timeoutMs: boundedInteger(requested.timeoutMs, "timeoutMs", MAX_LIMITS.timeoutMs),
  });
}

function dependencyError(error) {
  if (error instanceof InventoryDependencyError) return error;
  const status = Number(
    error?.response?.status ?? error?.status ?? error?.httpStatus ?? 0,
  );
  const timeout =
    error?.code === "ETIMEDOUT" ||
    error?.code === "ECONNABORTED" ||
    error?.name === "AbortError" ||
    status === 408 ||
    status === 504;
  if (timeout) return new InventoryDependencyError("DEPENDENCY_TIMEOUT", 504);
  if (status === 401) {
    return new InventoryDependencyError("DEPENDENCY_UNAUTHENTICATED", 401);
  }
  if (status === 403) {
    return new InventoryDependencyError("DEPENDENCY_PERMISSION_DENIED", 403);
  }
  if (status === 404) {
    return new InventoryDependencyError("DEPENDENCY_NOT_FOUND", 404);
  }
  if (status === 429) {
    return new InventoryDependencyError("DEPENDENCY_RATE_LIMITED", 429);
  }
  return new InventoryDependencyError("DEPENDENCY_REQUEST_FAILED", 502);
}

function dataOf(response) {
  if (response && typeof response === "object" && "data" in response) {
    return response.data;
  }
  return response;
}

async function getPage({ request, url, timeoutMs, budget }) {
  budget.take();
  try {
    const response = await request({ method: "GET", url, timeout: timeoutMs });
    const data = dataOf(response);
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new InventoryDependencyError("DEPENDENCY_SCHEMA_INVALID", 502);
    }
    return data;
  } catch (error) {
    throw dependencyError(error);
  }
}

async function collectPages({
  request,
  baseUrl,
  arrayKey,
  pageSize,
  maxItems,
  maxPages,
  timeoutMs,
  budget,
}) {
  const items = [];
  let pageToken = "";
  let pages = 0;
  let exhausted = false;

  while (pages < maxPages && items.length < maxItems) {
    const url = new URL(baseUrl);
    url.searchParams.set("pageSize", String(Math.min(pageSize, maxItems - items.length)));
    if (pageToken) url.searchParams.set("pageToken", pageToken);
    const data = await getPage({ request, url: url.toString(), timeoutMs, budget });
    const pageItems = data[arrayKey] ?? [];
    if (!Array.isArray(pageItems)) {
      throw new InventoryDependencyError("DEPENDENCY_SCHEMA_INVALID", 502);
    }
    items.push(...pageItems.slice(0, maxItems - items.length));
    pages += 1;
    pageToken = typeof data.nextPageToken === "string" ? data.nextPageToken : "";
    if (!pageToken) {
      exhausted = true;
      break;
    }
  }

  return {
    items,
    pages,
    truncated: !exhausted && Boolean(pageToken),
  };
}

async function mapLimit(items, concurrency, mapper) {
  const results = new Array(items.length);
  let cursor = 0;
  const workers = Array.from(
    { length: Math.min(concurrency, Math.max(items.length, 1)) },
    async () => {
      while (cursor < items.length) {
        const index = cursor;
        cursor += 1;
        results[index] = await mapper(items[index], index);
      }
    },
  );
  await Promise.all(workers);
  return results;
}

function stringField(value, maximum = 256) {
  return typeof value === "string" ? value.slice(0, maximum) : undefined;
}

function compact(record) {
  return Object.fromEntries(
    Object.entries(record).filter(([, value]) => value !== undefined),
  );
}

function safeIssuerUri(value) {
  if (typeof value !== "string") return undefined;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:" || parsed.username || parsed.password) {
      return undefined;
    }
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return undefined;
  }
}

function providerType(provider) {
  for (const type of ["aws", "oidc", "saml", "x509"]) {
    if (provider?.[type] && typeof provider[type] === "object") return type.toUpperCase();
  }
  return "UNSPECIFIED";
}

function sanitizeProvider(provider) {
  const attributeMappingKeys =
    provider?.attributeMapping && typeof provider.attributeMapping === "object"
      ? Object.keys(provider.attributeMapping).sort().slice(0, 51)
      : [];
  return compact({
    name: stringField(provider?.name, 512),
    displayName: stringField(provider?.displayName, 64),
    descriptionPresent:
      typeof provider?.description === "string" && provider.description.length > 0,
    state: stringField(provider?.state, 32),
    disabled: typeof provider?.disabled === "boolean" ? provider.disabled : undefined,
    expireTime: stringField(provider?.expireTime, 64),
    providerType: providerType(provider),
    attributeMappingKeys,
    attributeConditionPresent:
      typeof provider?.attributeCondition === "string" &&
      provider.attributeCondition.length > 0,
    oidcIssuerUri: safeIssuerUri(provider?.oidc?.issuerUri),
    allowedAudienceCount: Array.isArray(provider?.oidc?.allowedAudiences)
      ? provider.oidc.allowedAudiences.length
      : undefined,
  });
}

function sanitizePool(pool, providers, providersTruncated) {
  return compact({
    name: stringField(pool?.name, 512),
    displayName: stringField(pool?.displayName, 64),
    descriptionPresent: typeof pool?.description === "string" && pool.description.length > 0,
    state: stringField(pool?.state, 32),
    disabled: typeof pool?.disabled === "boolean" ? pool.disabled : undefined,
    mode: stringField(pool?.mode, 32),
    expireTime: stringField(pool?.expireTime, 64),
    providerCount: providers.length,
    providersTruncated,
    providers,
  });
}

function sanitizeServiceAccount(account) {
  return compact({
    name: stringField(account?.name, 512),
    projectId: stringField(account?.projectId, 64),
    uniqueId: stringField(account?.uniqueId, 32),
    email: stringField(account?.email, 320),
    displayName: stringField(account?.displayName, 128),
    descriptionPresent:
      typeof account?.description === "string" && account.description.length > 0,
    disabled: typeof account?.disabled === "boolean" ? account.disabled : undefined,
  });
}

function poolId(poolName) {
  const match = POOL_NAME_PATTERN.exec(String(poolName ?? ""));
  if (!match) {
    throw new InventoryDependencyError("DEPENDENCY_POOL_NAME_INVALID", 502);
  }
  return match[1];
}

export function publicInventoryError(error) {
  if (
    error instanceof InventoryInputError ||
    error instanceof InventoryConfigurationError ||
    error instanceof InventoryDependencyError
  ) {
    return { code: error.code, httpStatus: error.httpStatus };
  }
  return { code: "INTERNAL_ERROR", httpStatus: 500 };
}

export async function readWifInventory({
  projectId,
  location = "global",
  request,
  limits: requestedLimits,
  requestId,
  now = () => new Date().toISOString(),
}) {
  if (typeof projectId !== "string" || !PROJECT_ID_PATTERN.test(projectId)) {
    throw new InventoryConfigurationError("PROJECT_ID_INVALID");
  }
  if (location !== "global") {
    throw new InventoryInputError("LOCATION_NOT_ALLOWED");
  }
  if (typeof request !== "function") {
    throw new InventoryConfigurationError("AUTHENTICATED_REQUEST_REQUIRED");
  }

  const limits = effectiveLimits(requestedLimits);
  const budget = new RequestBudget(limits.requestBudget);
  const encodedProject = encodeURIComponent(projectId);
  const poolBase =
    `https://iam.googleapis.com/v1/projects/${encodedProject}/locations/global/workloadIdentityPools`;
  const serviceAccountBase =
    `https://iam.googleapis.com/v1/projects/${encodedProject}/serviceAccounts`;

  const [poolPages, accountPages] = await Promise.all([
    collectPages({
      request,
      baseUrl: poolBase,
      arrayKey: "workloadIdentityPools",
      pageSize: Math.min(limits.maxPools, 1_000),
      maxItems: limits.maxPools,
      maxPages: limits.maxPages,
      timeoutMs: limits.timeoutMs,
      budget,
    }),
    collectPages({
      request,
      baseUrl: serviceAccountBase,
      arrayKey: "accounts",
      pageSize: Math.min(limits.maxServiceAccounts, 100),
      maxItems: limits.maxServiceAccounts,
      maxPages: limits.maxPages,
      timeoutMs: limits.timeoutMs,
      budget,
    }),
  ]);

  const pools = await mapLimit(
    poolPages.items,
    limits.providerConcurrency,
    async (pool) => {
      const id = poolId(pool?.name);
      const providerBase =
        `${poolBase}/${encodeURIComponent(id)}/providers`;
      const providerPages = await collectPages({
        request,
        baseUrl: providerBase,
        arrayKey: "workloadIdentityPoolProviders",
        pageSize: Math.min(limits.maxProvidersPerPool, 100),
        maxItems: limits.maxProvidersPerPool,
        maxPages: limits.maxPages,
        timeoutMs: limits.timeoutMs,
        budget,
      });
      const providers = providerPages.items.map(sanitizeProvider);
      return sanitizePool(pool, providers, providerPages.truncated);
    },
  );

  const serviceAccounts = accountPages.items.map(sanitizeServiceAccount);
  return {
    schema: "FO-WIF-INVENTORY-1",
    ok: true,
    status: "WIF_INVENTORY_READ",
    requestId: stringField(requestId, 128),
    projectId,
    location,
    counts: {
      pools: pools.length,
      providers: pools.reduce((total, pool) => total + pool.providerCount, 0),
      serviceAccounts: serviceAccounts.length,
      requests: budget.used,
    },
    truncated: {
      pools: poolPages.truncated,
      providers: pools.some((pool) => pool.providersTruncated),
      serviceAccounts: accountPages.truncated,
    },
    pools,
    serviceAccounts,
    permissionsRequired: [
      "iam.workloadIdentityPools.list",
      "iam.workloadIdentityPoolProviders.list",
      "iam.serviceAccounts.list",
    ],
    secretsRead: false,
    credentialsExported: false,
    serviceAccountKeysRead: false,
    iamPoliciesRead: false,
    checkedAt: now(),
  };
}
