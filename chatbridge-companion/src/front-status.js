(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ChatBridgeFrontStatus = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SCHEMA = "FUSE-FRONT-STATUS-1";
  const SILENT_LONG_RUNNING_EXECUTION = "SILENT_LONG_RUNNING_EXECUTION";
  const INCOMPLETE_PROGRESS_REPORTING = "INCOMPLETE_PROGRESS_REPORTING";
  const USER_INTERRUPTION = "USER_INTERRUPTION";

  function normalizeThreshold(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) && number >= 1000 ? number : fallback;
  }

  function createTracker(options) {
    const opts = Object.assign({
      stallThresholdMs: 90000,
      incompleteGraceMs: 15000,
      ownerStopSuppressMs: 15000,
      now: () => Date.now()
    }, options || {});

    let stallThresholdMs = normalizeThreshold(opts.stallThresholdMs, 90000);
    let incompleteGraceMs = normalizeThreshold(opts.incompleteGraceMs, 15000);
    let ownerStopSuppressMs = normalizeThreshold(opts.ownerStopSuppressMs, 15000);
    const now = typeof opts.now === "function" ? opts.now : () => Date.now();

    let initialized = false;
    let lastContentSignature = "";
    let lastProgressAt = 0;
    let silentReportedForSignature = "";
    let silentReportedAt = 0;
    let incompleteReportedForSignature = "";
    let ownerStopAt = -Infinity;
    let wasInflight = false;
    let epoch = 0;

    function configure(next) {
      if (!next || typeof next !== "object") return;
      stallThresholdMs = normalizeThreshold(next.stallThresholdMs, stallThresholdMs);
      incompleteGraceMs = normalizeThreshold(next.incompleteGraceMs, incompleteGraceMs);
      ownerStopSuppressMs = normalizeThreshold(next.ownerStopSuppressMs, ownerStopSuppressMs);
    }

    function markOwnerStop(observedAtMs) {
      ownerStopAt = Number.isFinite(Number(observedAtMs)) ? Number(observedAtMs) : Number(now());
    }

    function ownerStopActive(observedAtMs) {
      return Number(observedAtMs) - ownerStopAt <= ownerStopSuppressMs;
    }

    function observe(snapshot) {
      const current = snapshot || {};
      const observedAtMs = Number.isFinite(Number(current.observedAtMs))
        ? Number(current.observedAtMs)
        : Number(now());
      const contentSignature = String(current.contentSignature || "");
      const responseInflight = Boolean(current.responseInflight);
      const stopButtonVisible = Boolean(current.stopButtonVisible);
      const ownerVisibleProgress = current.ownerVisibleProgress !== false;
      const stage = String(current.stage || "CHATGPT_FRONTEND");
      const reason = String(current.reason || "OBSERVE");
      const events = [];

      if (!initialized) {
        initialized = true;
        lastContentSignature = contentSignature;
        lastProgressAt = observedAtMs;
      }

      if (contentSignature && contentSignature !== lastContentSignature) {
        lastContentSignature = contentSignature;
        lastProgressAt = observedAtMs;
        silentReportedForSignature = "";
        silentReportedAt = 0;
        incompleteReportedForSignature = "";
      }

      const noProgressMs = Math.max(0, observedAtMs - lastProgressAt);
      const suppressedByOwnerStop = ownerStopActive(observedAtMs);

      if (
        responseInflight
        && noProgressMs >= stallThresholdMs
        && !suppressedByOwnerStop
        && silentReportedForSignature !== lastContentSignature
      ) {
        epoch += 1;
        silentReportedForSignature = lastContentSignature;
        silentReportedAt = observedAtMs;
        events.push({
          schema: SCHEMA,
          eventKind: SILENT_LONG_RUNNING_EXECUTION,
          eventId: `front-stall-${epoch}`,
          observedAtMs,
          noProgressMs,
          responseInflight: true,
          stopButtonVisible,
          ownerVisibleProgress,
          stage,
          reason,
          contentSignature: lastContentSignature
        });
      }

      if (
        wasInflight
        && !responseInflight
        && silentReportedForSignature === lastContentSignature
        && silentReportedAt > 0
        && observedAtMs - silentReportedAt >= incompleteGraceMs
        && !suppressedByOwnerStop
        && incompleteReportedForSignature !== lastContentSignature
      ) {
        epoch += 1;
        incompleteReportedForSignature = lastContentSignature;
        events.push({
          schema: SCHEMA,
          eventKind: INCOMPLETE_PROGRESS_REPORTING,
          eventId: `front-incomplete-${epoch}`,
          observedAtMs,
          noProgressMs,
          responseInflight: false,
          stopButtonVisible: false,
          ownerVisibleProgress,
          stage,
          reason,
          contentSignature: lastContentSignature
        });
      }

      if (suppressedByOwnerStop && wasInflight && !responseInflight) {
        epoch += 1;
        events.push({
          schema: SCHEMA,
          eventKind: USER_INTERRUPTION,
          eventId: `front-user-stop-${epoch}`,
          observedAtMs,
          noProgressMs,
          responseInflight: false,
          stopButtonVisible: false,
          ownerVisibleProgress: true,
          stage,
          reason: "OWNER_STOP_OBSERVED",
          contentSignature: lastContentSignature
        });
        silentReportedForSignature = "";
        silentReportedAt = 0;
        incompleteReportedForSignature = "";
      }

      wasInflight = responseInflight;

      return {
        state: responseInflight
          ? (noProgressMs >= stallThresholdMs ? "STALLED" : "HEALTHY_RUNNING")
          : "IDLE",
        events,
        noProgressMs,
        lastProgressAt,
        suppressedByOwnerStop
      };
    }

    function state() {
      return {
        schema: SCHEMA,
        initialized,
        lastContentSignature,
        lastProgressAt,
        silentReportedForSignature,
        silentReportedAt,
        incompleteReportedForSignature,
        ownerStopAt,
        wasInflight,
        stallThresholdMs,
        incompleteGraceMs,
        ownerStopSuppressMs
      };
    }

    return Object.freeze({
      configure,
      markOwnerStop,
      observe,
      state
    });
  }

  return Object.freeze({
    SCHEMA,
    SILENT_LONG_RUNNING_EXECUTION,
    INCOMPLETE_PROGRESS_REPORTING,
    USER_INTERRUPTION,
    createTracker
  });
});
