import assert from "node:assert/strict";
import http from "node:http";
import test from "node:test";

import { createHttpHandler } from "../src/http-app.js";

async function withServer(handler, callback) {
  const server = http.createServer(handler);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    await callback(`http://127.0.0.1:${port}`);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test("HTTP surface exposes public contract and denies unauthenticated execution", async () => {
  const logs = [];
  const service = {
    health: () => ({ ok: true, status: "OPERATOR_READY" }),
    contract: () => ({ ok: true, allowedActions: ["STATUS"] }),
    execute: async ({ action, requestId }) => ({
      ok: true,
      status: action,
      requestId,
    }),
  };
  const token = "x".repeat(32);
  const handler = createHttpHandler({
    service,
    adminToken: token,
    logger: (entry) => logs.push(entry),
    now: () => "2026-08-22T00:00:00.000Z",
  });

  await withServer(handler, async (base) => {
    const health = await fetch(`${base}/health`);
    assert.equal(health.status, 200);
    assert.equal((await health.json()).status, "OPERATOR_READY");

    const contract = await fetch(base);
    assert.equal(contract.status, 200);
    assert.deepEqual((await contract.json()).allowedActions, ["STATUS"]);

    const denied = await fetch(`${base}/execute`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: "STATUS" }),
    });
    assert.equal(denied.status, 403);
    assert.equal((await denied.json()).reason, "ADMIN_TOKEN_REQUIRED");

    const allowed = await fetch(`${base}/execute`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-fo-admin-token": token,
        "x-request-id": "http-test-1",
      },
      body: JSON.stringify({ action: "STATUS" }),
    });
    assert.equal(allowed.status, 200);
    assert.equal((await allowed.json()).requestId, "http-test-1");
  });
  assert.equal(JSON.stringify(logs).includes(token), false);
});

test("HTTP surface rejects malformed JSON without echoing the body", async () => {
  const service = {
    health: () => ({ ok: true }),
    contract: () => ({ ok: true }),
    execute: async () => ({ ok: true }),
  };
  const token = "y".repeat(32);
  const handler = createHttpHandler({
    service,
    adminToken: token,
    logger: () => {},
  });

  await withServer(handler, async (base) => {
    const response = await fetch(`${base}/execute`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-fo-admin-token": token,
      },
      body: '{"secret":"MALFORMED_SECRET"',
    });
    const body = await response.text();
    assert.equal(response.status, 400);
    assert.equal(body.includes("MALFORMED_SECRET"), false);
    assert.equal(JSON.parse(body).code, "INVALID_JSON_BODY");
  });
});
