import crypto from "node:crypto";

import { publicOperatorError } from "./operator-service.js";

const MAX_BODY_BYTES = 64 * 1024;
const REQUEST_ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;

function writeJson(res, status, body) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
  });
  res.end(JSON.stringify(body));
}

function safeEqual(left, right) {
  const a = Buffer.from(String(left ?? ""));
  const b = Buffer.from(String(right ?? ""));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

async function readBody(req) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of req) {
    bytes += chunk.length;
    if (bytes > MAX_BODY_BYTES) {
      throw Object.assign(new Error("BODY_TOO_LARGE"), {
        code: "BODY_TOO_LARGE",
        httpStatus: 413,
      });
    }
    chunks.push(chunk);
  }
  if (bytes === 0) return {};
  try {
    const parsed = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("shape");
    }
    return parsed;
  } catch (error) {
    if (error?.code === "BODY_TOO_LARGE") throw error;
    throw Object.assign(new Error("INVALID_JSON_BODY"), {
      code: "INVALID_JSON_BODY",
      httpStatus: 400,
    });
  }
}

function requestId(req) {
  const supplied = req.headers["x-request-id"];
  return typeof supplied === "string" && REQUEST_ID_PATTERN.test(supplied)
    ? supplied
    : crypto.randomUUID();
}

export function createHttpHandler({
  service,
  adminToken,
  logger = (entry) => console.log(JSON.stringify(entry)),
  now = () => new Date().toISOString(),
}) {
  if (!service?.health || !service?.contract || !service?.execute) {
    throw new Error("OPERATOR_SERVICE_REQUIRED");
  }

  return async function handler(req, res) {
    const id = requestId(req);
    const started = Date.now();
    let action = "HTTP";
    try {
      if (req.method === "GET" && req.url === "/health") {
        return writeJson(res, 200, { requestId: id, ...service.health() });
      }
      if (req.method === "GET" && req.url === "/") {
        return writeJson(res, 200, { requestId: id, ...service.contract() });
      }
      if (req.method !== "POST" || req.url !== "/execute") {
        return writeJson(res, 404, {
          ok: false,
          status: "NOT_FOUND",
          requestId: id,
          checkedAt: now(),
        });
      }
      if (!adminToken || !safeEqual(req.headers["x-fo-admin-token"], adminToken)) {
        logger({
          event: "operator_request",
          requestId: id,
          action: "AUTH",
          outcome: "DENIED",
          checkedAt: now(),
        });
        return writeJson(res, 403, {
          ok: false,
          status: "DENIED",
          reason: "ADMIN_TOKEN_REQUIRED",
          requestId: id,
          checkedAt: now(),
        });
      }
      const body = await readBody(req);
      action = body.action ?? "STATUS";
      const result = await service.execute({
        action,
        payload: body.payload ?? {},
        requestId: id,
      });
      logger({
        event: "operator_request",
        requestId: id,
        action,
        outcome: "OK",
        durationMs: Date.now() - started,
        checkedAt: now(),
      });
      return writeJson(res, 200, result);
    } catch (error) {
      const publicError = publicOperatorError(error);
      const code =
        error?.code === "BODY_TOO_LARGE" || error?.code === "INVALID_JSON_BODY"
          ? error.code
          : publicError.code;
      const status =
        error?.httpStatus === 413 || error?.httpStatus === 400
          ? error.httpStatus
          : publicError.httpStatus;
      logger({
        event: "operator_request",
        requestId: id,
        action,
        outcome: "ERROR",
        code,
        durationMs: Date.now() - started,
        checkedAt: now(),
      });
      return writeJson(res, status, {
        ok: false,
        status: "OPERATOR_ERROR",
        code,
        requestId: id,
        checkedAt: now(),
      });
    }
  };
}
