(function (root) {
  "use strict";

  const {AggregateBrowserProbe} = typeof require === "function"
    ? require("./aggregate_browser_probe.js")
    : root.ChatPerformanceAggregateProbe;

  const MAX_AGGREGATE_SAMPLES = 256;
  const HYDRATION_MILESTONES = new Set(["START", "READY"]);
  const TRANSPORT_STATES = new Set(["CONNECTED", "RECONNECTING", "ERROR"]);

  function finite(value) {
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? number : 0;
  }

  function rounded(value) {
    return Number(finite(value).toFixed(3));
  }

  function percentile(values, fraction) {
    if (!values.length) return 0;
    const sorted = values.slice().sort((a, b) => a - b);
    return rounded(sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * fraction) - 1)]);
  }

  function aggregate(values) {
    return {
      sampleCount: values.length,
      p50: percentile(values, 0.5),
      p95: percentile(values, 0.95),
      maximum: rounded(values.length ? Math.max(...values) : 0)
    };
  }

  class NativeEdgeChatGPTDiagnostic {
    constructor(options = {}) {
      this.config = options.config || {};
      this.performanceApi = options.performanceApi;
      this.ObserverClass = options.ObserverClass;
      this.eventTarget = options.eventTarget || null;
      this.clock = typeof options.clock === "function" ? options.clock : () => Date.now();
      this.probe = new AggregateBrowserProbe(this.performanceApi, this.ObserverClass);
      this.started = false;
      this.listeners = [];
      this.hydrationStart = null;
      this.hydrationDurations = [];
      this.memoryRatios = [];
      this.droppedSamples = 0;
      this.lifecycle = {pageShow: 0, pageHide: 0, online: 0, offline: 0, visibilityChange: 0};
      this.transport = {connected: 0, reconnecting: 0, errors: 0};
    }

    start(evidence = {}) {
      if (this.config.enabled !== true) return {state: "DISABLED_CONFIG"};
      if (this.config.mode !== "SHADOW_OBSERVE_ONLY") return {state: "ACTIVATION_DENIED", reason: "INVALID_MODE"};
      if (!this.config.activation || this.config.activation.authorizedEdgeHookPresent !== true) {
        return {state: "ACTIVATION_DENIED", reason: "AUTHORIZED_EDGE_HOOK_REQUIRED"};
      }
      if (evidence.formationPermitValidated !== true || evidence.operatorActivationValidated !== true) {
        return {state: "ACTIVATION_DENIED", reason: "EVIDENCE_INCOMPLETE"};
      }
      if (this.started) return {state: "ALREADY_OBSERVING"};
      this.started = true;
      this._listen("pageshow", () => { this.lifecycle.pageShow += 1; });
      this._listen("pagehide", () => { this.lifecycle.pageHide += 1; });
      this._listen("online", () => { this.lifecycle.online += 1; });
      this._listen("offline", () => { this.lifecycle.offline += 1; });
      this._listen("visibilitychange", () => { this.lifecycle.visibilityChange += 1; });
      const longTask = this.probe.start();
      return {state: "OBSERVING", longTaskState: longTask.state};
    }

    _listen(type, listener) {
      if (!this.eventTarget || typeof this.eventTarget.addEventListener !== "function") return;
      this.eventTarget.addEventListener(type, listener);
      this.listeners.push({type, listener});
    }

    _admitSample(collection, value) {
      if (collection.length >= MAX_AGGREGATE_SAMPLES) {
        this.droppedSamples += 1;
        return false;
      }
      collection.push(value);
      return true;
    }

    recordHydration(milestone, atMs = this.clock()) {
      if (!this.started) return {state: "IGNORED_NOT_OBSERVING"};
      if (!HYDRATION_MILESTONES.has(milestone)) return {state: "REJECTED_ENUM"};
      const time = finite(atMs);
      if (milestone === "START") {
        this.hydrationStart = time;
        return {state: "RECORDED"};
      }
      if (this.hydrationStart === null || time < this.hydrationStart) return {state: "REJECTED_SEQUENCE"};
      const admitted = this._admitSample(this.hydrationDurations, rounded(time - this.hydrationStart));
      this.hydrationStart = null;
      return {state: admitted ? "RECORDED" : "DROPPED_BUDGET"};
    }

    recordTransportState(state) {
      if (!this.started) return {state: "IGNORED_NOT_OBSERVING"};
      if (!TRANSPORT_STATES.has(state)) return {state: "REJECTED_ENUM"};
      if (state === "CONNECTED") this.transport.connected += 1;
      if (state === "RECONNECTING") this.transport.reconnecting += 1;
      if (state === "ERROR") this.transport.errors += 1;
      return {state: "RECORDED"};
    }

    recordMemorySample(usedBytes, limitBytes) {
      if (!this.started) return {state: "IGNORED_NOT_OBSERVING"};
      const used = finite(usedBytes);
      const limit = finite(limitBytes);
      if (limit === 0 || used > limit) return {state: "REJECTED_RANGE"};
      const admitted = this._admitSample(this.memoryRatios, rounded(used / limit));
      return {state: admitted ? "RECORDED" : "DROPPED_BUDGET"};
    }

    snapshot() {
      const browser = this.probe.snapshot();
      const rawNavigationEntries = this.performanceApi && typeof this.performanceApi.getEntriesByType === "function"
        ? this.performanceApi.getEntriesByType("navigation") : [];
      const navigationEntries = Array.isArray(rawNavigationEntries) ? rawNavigationEntries : [];
      const navigation = navigationEntries[0] || null;
      const memory = aggregate(this.memoryRatios);
      return {
        schema: "FACPF-NATIVE-EDGE-DIAGNOSTIC-1",
        state: this.started ? "OBSERVING" : "INACTIVE",
        runtimeBoundary: "AUTHORIZED_EDGE_HOOK_REQUIRED",
        privacy: {
          messageTextCaptured: false,
          perMessageIdentifiersCaptured: false,
          rawDomCaptured: false,
          urlsCaptured: false,
          entryNamesCaptured: false,
          attributionCaptured: false,
          rawMemoryBytesCaptured: false
        },
        navigation: {...browser.navigation, reloadCount: navigation && navigation.type === "reload" ? 1 : 0},
        resources: browser.resources,
        longTasks: browser.longTasks,
        hydrationMs: aggregate(this.hydrationDurations),
        lifecycle: {...this.lifecycle},
        transport: {...this.transport},
        memoryPressure: {...memory, threshold80PercentCount: this.memoryRatios.filter((value) => value >= 0.8).length},
        droppedSamples: this.droppedSamples
      };
    }

    stop() {
      for (const {type, listener} of this.listeners) {
        if (this.eventTarget && typeof this.eventTarget.removeEventListener === "function") {
          this.eventTarget.removeEventListener(type, listener);
        }
      }
      this.listeners.length = 0;
      this.probe.stop();
      this.started = false;
    }

    rollback() {
      this.stop();
      this.probe.rollback();
      this.hydrationStart = null;
      this.hydrationDurations.length = 0;
      this.memoryRatios.length = 0;
      this.droppedSamples = 0;
      this.lifecycle = {pageShow: 0, pageHide: 0, online: 0, offline: 0, visibilityChange: 0};
      this.transport = {connected: 0, reconnecting: 0, errors: 0};
    }
  }

  root.FACPFNativeEdgeDiagnostic = {
    NativeEdgeChatGPTDiagnostic,
    MAX_AGGREGATE_SAMPLES,
    HYDRATION_MILESTONES,
    TRANSPORT_STATES
  };
  if (typeof module !== "undefined" && module.exports) module.exports = root.FACPFNativeEdgeDiagnostic;
})(typeof globalThis !== "undefined" ? globalThis : this);
