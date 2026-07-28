import test from "node:test";
import assert from "node:assert/strict";
import { authorize, defaultPolicy } from "../src/policy.js";

test("allows only recovery-service allowlist", () => {
  assert.doesNotThrow(() => authorize({ action:"enable_service", payload:{service:"script.googleapis.com"}, policy:defaultPolicy }));
  assert.throws(() => authorize({ action:"enable_service", payload:{service:"compute.googleapis.com"}, policy:defaultPolicy }));
});

test("blocks mutation without policy and rollback", () => {
  assert.throws(() => authorize({ action:"delete_resource", payload:{}, policy:defaultPolicy }));
});

test("allows only the exact deadman Scheduler target and confirmation", () => {
  const exact = { ...defaultPolicy.deadman, confirmation:defaultPolicy.deadman.confirmation };
  assert.doesNotThrow(() => authorize({ action:"run_deadman_scheduler_job", payload:exact, policy:defaultPolicy }));
  assert.throws(() => authorize({ action:"run_deadman_scheduler_job", payload:{...exact, jobName:"other-job"}, policy:defaultPolicy }));
  assert.throws(() => authorize({ action:"run_deadman_scheduler_job", payload:{...exact, confirmation:"RUN"}, policy:defaultPolicy }));
});
