import assert from "node:assert/strict";
import test from "node:test";

import {
  publicInventoryError,
  readWifInventory,
} from "../src/wif-inventory.js";

function response(data) {
  return { data };
}

function routedRequest(routes) {
  const calls = [];
  const request = async ({ method, url, timeout }) => {
    calls.push({ method, url, timeout });
    const parsed = new URL(url);
    const key = `${parsed.pathname}?${parsed.searchParams.get("pageToken") ?? ""}`;
    const handler = routes.get(key);
    if (!handler) throw new Error(`UNEXPECTED_ROUTE:${key}`);
    return typeof handler === "function" ? handler({ method, url, timeout }) : handler;
  };
  return { request, calls };
}

test("reads bounded pools, providers, and service accounts with pagination", async () => {
  const routes = new Map([
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools?",
      response({
        workloadIdentityPools: [{
          name: "projects/257649435135/locations/global/workloadIdentityPools/github-pool",
          displayName: "GitHub",
          description: "present",
          state: "ACTIVE",
          disabled: false,
          mode: "FEDERATION_ONLY",
        }],
        nextPageToken: "next-pools",
      }),
    ],
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools?next-pools",
      response({
        workloadIdentityPools: [{
          name: "projects/257649435135/locations/global/workloadIdentityPools/second-pool",
          state: "ACTIVE",
          disabled: false,
        }],
      }),
    ],
    [
      "/v1/projects/sov-hybrid-suite/serviceAccounts?",
      response({
        accounts: [{
          name: "projects/sov-hybrid-suite/serviceAccounts/fo@example.iam.gserviceaccount.com",
          projectId: "sov-hybrid-suite",
          uniqueId: "123456789012345678901",
          email: "fo@example.iam.gserviceaccount.com",
          displayName: "FO operator",
          description: "present",
          disabled: false,
        }],
      }),
    ],
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools/github-pool/providers?",
      response({
        workloadIdentityPoolProviders: [{
          name: "projects/257649435135/locations/global/workloadIdentityPools/github-pool/providers/github",
          displayName: "GitHub",
          state: "ACTIVE",
          disabled: false,
          attributeMapping: {
            "google.subject": "assertion.sub",
            "attribute.repository": "assertion.repository",
          },
          attributeCondition: "assertion.repository == 'owner/repo'",
          oidc: {
            issuerUri: "https://token.actions.githubusercontent.com",
            allowedAudiences: ["audience"],
          },
        }],
      }),
    ],
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools/second-pool/providers?",
      response({ workloadIdentityPoolProviders: [] }),
    ],
  ]);
  const { request, calls } = routedRequest(routes);

  const result = await readWifInventory({
    projectId: "sov-hybrid-suite",
    request,
    limits: { maxPools: 2 },
    requestId: "req-1",
    now: () => "2026-08-22T00:00:00.000Z",
  });

  assert.equal(result.status, "WIF_INVENTORY_READ");
  assert.deepEqual(result.counts, {
    pools: 2,
    providers: 1,
    serviceAccounts: 1,
    requests: 5,
  });
  assert.equal(result.pools[0].providers[0].providerType, "OIDC");
  assert.deepEqual(result.pools[0].providers[0].attributeMappingKeys, [
    "attribute.repository",
    "google.subject",
  ]);
  assert.equal(result.serviceAccounts[0].descriptionPresent, true);
  assert.equal(result.checkedAt, "2026-08-22T00:00:00.000Z");
  assert.ok(calls.every((call) => call.method === "GET" && call.timeout === 5_000));
  assert.ok(calls.every((call) => call.url.startsWith("https://iam.googleapis.com/")));
});

test("drops credential material, raw mappings, conditions, metadata, and query secrets", async () => {
  const secretValues = [
    "PRIVATE_JWK_MATERIAL",
    "RAW_SAML_CERTIFICATE",
    "RAW_X509_CERTIFICATE",
    "repo-secret-value",
    "condition-secret-value",
    "description-secret-value",
    "audience-secret-value",
    "issuer-query-secret",
    "oauth-client-secret-value",
  ];
  const routes = new Map([
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools?",
      response({
        workloadIdentityPools: [{
          name: "projects/257649435135/locations/global/workloadIdentityPools/github-pool",
          description: "description-secret-value",
          state: "ACTIVE",
        }],
      }),
    ],
    [
      "/v1/projects/sov-hybrid-suite/serviceAccounts?",
      response({
        accounts: [{
          name: "projects/sov-hybrid-suite/serviceAccounts/fo@example.iam.gserviceaccount.com",
          email: "fo@example.iam.gserviceaccount.com",
          description: "description-secret-value",
          oauth2ClientId: "oauth-client-secret-value",
          etag: "credential-etag",
        }],
      }),
    ],
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools/github-pool/providers?",
      response({
        workloadIdentityPoolProviders: [{
          name: "projects/257649435135/locations/global/workloadIdentityPools/github-pool/providers/github",
          description: "description-secret-value",
          attributeMapping: { "google.subject": "repo-secret-value" },
          attributeCondition: "condition-secret-value",
          oidc: {
            issuerUri: "https://issuer.example/oidc?token=issuer-query-secret",
            allowedAudiences: ["audience-secret-value"],
            jwksJson: "PRIVATE_JWK_MATERIAL",
          },
          saml: { idpMetadataXml: "RAW_SAML_CERTIFICATE" },
          x509: { trustStore: "RAW_X509_CERTIFICATE" },
        }],
      }),
    ],
  ]);
  const { request } = routedRequest(routes);

  const result = await readWifInventory({ projectId: "sov-hybrid-suite", request });
  const serialized = JSON.stringify(result);

  for (const value of secretValues) assert.equal(serialized.includes(value), false);
  for (const forbiddenKey of [
    "jwksJson",
    "idpMetadataXml",
    "trustStore",
    "oauth2ClientId",
    "etag",
    "attributeCondition\"",
  ]) {
    assert.equal(serialized.includes(forbiddenKey), false);
  }
  assert.equal(result.pools[0].descriptionPresent, true);
  assert.equal(result.pools[0].providers[0].attributeConditionPresent, true);
  assert.equal(result.pools[0].providers[0].oidcIssuerUri, "https://issuer.example/oidc");
  assert.equal(result.pools[0].providers[0].allowedAudienceCount, 1);
  assert.equal(result.secretsRead, false);
  assert.equal(result.credentialsExported, false);
  assert.equal(result.serviceAccountKeysRead, false);
  assert.equal(result.iamPoliciesRead, false);
});

test("sanitizes permission failures and never returns dependency bodies", async () => {
  const dependencyError = new Error("raw provider error with SECRET_BODY");
  dependencyError.response = {
    status: 403,
    data: { error: { message: "SECRET_BODY", credential: "PRIVATE_VALUE" } },
  };
  const request = async () => {
    throw dependencyError;
  };

  await assert.rejects(
    readWifInventory({ projectId: "sov-hybrid-suite", request }),
    (error) => {
      assert.deepEqual(publicInventoryError(error), {
        code: "DEPENDENCY_PERMISSION_DENIED",
        httpStatus: 403,
      });
      assert.equal(JSON.stringify(publicInventoryError(error)).includes("SECRET_BODY"), false);
      assert.equal(error.message.includes("SECRET_BODY"), false);
      return true;
    },
  );
});

test("rejects project and location overrides before any request", async () => {
  let called = false;
  const request = async () => {
    called = true;
    return response({});
  };

  await assert.rejects(
    readWifInventory({ projectId: "../other-project", request }),
    (error) => publicInventoryError(error).code === "PROJECT_ID_INVALID",
  );
  await assert.rejects(
    readWifInventory({
      projectId: "sov-hybrid-suite",
      location: "us-central1",
      request,
    }),
    (error) => publicInventoryError(error).code === "LOCATION_NOT_ALLOWED",
  );
  assert.equal(called, false);
});

test("rejects limit expansion and enforces the request budget", async () => {
  const noCall = async () => response({});
  await assert.rejects(
    readWifInventory({
      projectId: "sov-hybrid-suite",
      request: noCall,
      limits: { maxPools: 21 },
    }),
    (error) => publicInventoryError(error).code === "INVALID_LIMIT_MAXPOOLS",
  );

  const routes = new Map([
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools?",
      response({
        workloadIdentityPools: [
          {
            name: "projects/257649435135/locations/global/workloadIdentityPools/pool-one",
          },
          {
            name: "projects/257649435135/locations/global/workloadIdentityPools/pool-two",
          },
        ],
      }),
    ],
    ["/v1/projects/sov-hybrid-suite/serviceAccounts?", response({ accounts: [] })],
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools/pool-one/providers?",
      response({ workloadIdentityPoolProviders: [] }),
    ],
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools/pool-two/providers?",
      response({ workloadIdentityPoolProviders: [] }),
    ],
  ]);
  const { request } = routedRequest(routes);
  await assert.rejects(
    readWifInventory({
      projectId: "sov-hybrid-suite",
      request,
      limits: { requestBudget: 3 },
    }),
    (error) =>
      publicInventoryError(error).code === "DEPENDENCY_REQUEST_BUDGET_EXCEEDED",
  );
});

test("fails closed on malformed provider collection schemas", async () => {
  const routes = new Map([
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools?",
      response({
        workloadIdentityPools: [{
          name: "projects/257649435135/locations/global/workloadIdentityPools/github-pool",
        }],
      }),
    ],
    ["/v1/projects/sov-hybrid-suite/serviceAccounts?", response({ accounts: [] })],
    [
      "/v1/projects/sov-hybrid-suite/locations/global/workloadIdentityPools/github-pool/providers?",
      response({ workloadIdentityPoolProviders: { unsafe: true } }),
    ],
  ]);
  const { request } = routedRequest(routes);

  await assert.rejects(
    readWifInventory({ projectId: "sov-hybrid-suite", request }),
    (error) => publicInventoryError(error).code === "DEPENDENCY_SCHEMA_INVALID",
  );
});
