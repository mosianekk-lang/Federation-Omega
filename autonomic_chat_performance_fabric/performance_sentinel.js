(function (root) {
  "use strict";

  const DEFAULTS = Object.freeze({
    quietMs: 1800,
    minimumIntervalMs: 30000,
    maximumPayloadChars: 32000,
    maximumQueueItems: 64,
    maximumCaptureMs: 40
  });

  class PerformanceSentinel {
    constructor(options = {}) {
      this.options = Object.assign({}, DEFAULTS, options);
      this.lastHashes = new Map();
      this.queue = [];
      this.lastCaptureAt = 0;
      this.streaming = false;
      this.circuitOpen = false;
      this.disabled = false;
    }

    static hashText(text) {
      let hash = 2166136261;
      for (let index = 0; index < text.length; index += 1) {
        hash ^= text.charCodeAt(index);
        hash = Math.imul(hash, 16777619);
      }
      return (hash >>> 0).toString(16).padStart(8, "0");
    }

    setStreaming(value) {
      this.streaming = Boolean(value);
    }

    admit(messages, now = Date.now()) {
      if (this.disabled) return {state: "DISABLED", deltas: [], changeCount: 0};
      if (this.circuitOpen || this.streaming) return {state: "DEFERRED", deltas: []};
      if (now - this.lastCaptureAt < this.options.minimumIntervalMs) {
        return {state: "THROTTLED", deltas: []};
      }
      const started = typeof performance !== "undefined" ? performance.now() : now;
      const pendingHashes = [];
      let changeCount = 0;
      let payloadChars = 0;
      for (const message of messages) {
        const id = String(message.id || "");
        const text = String(message.text || "");
        if (!id || !text) continue;
        const hash = PerformanceSentinel.hashText(text);
        if (this.lastHashes.get(id) === hash) continue;
        pendingHashes.push([id, hash]);
        changeCount += 1;
        payloadChars += text.length;
      }
      const ended = typeof performance !== "undefined" ? performance.now() : now;
      const elapsedMs = Math.max(0, ended - started);
      if (payloadChars > this.options.maximumPayloadChars || elapsedMs > this.options.maximumCaptureMs) {
        this.circuitOpen = true;
        return {state: "CIRCUIT_OPEN", deltas: [], changeCount: 0, payloadChars, elapsedMs};
      }
      for (const [id, hash] of pendingHashes) this.lastHashes.set(id, hash);
      this.lastCaptureAt = now;
      if (changeCount) this.queue.push({observedAt: Number(now), changeCount, payloadChars, elapsedMs});
      if (this.queue.length > this.options.maximumQueueItems) {
        this.queue.splice(0, this.queue.length - this.options.maximumQueueItems);
      }
      return {
        state: changeCount ? "DELTA_READY" : "NO_CHANGE",
        deltas: [],
        changeCount,
        payloadChars,
        elapsedMs
      };
    }

    drain(limit = 16) {
      return this.queue.splice(0, Math.max(0, limit));
    }

    resetCircuit() {
      this.circuitOpen = false;
    }

    rollback() {
      this.disabled = true;
      this.streaming = false;
      this.circuitOpen = false;
      this.lastHashes.clear();
      this.queue.length = 0;
    }
  }

  root.ChatPerformanceSentinel = {PerformanceSentinel, DEFAULTS};
  if (typeof module !== "undefined" && module.exports) module.exports = root.ChatPerformanceSentinel;
})(typeof globalThis !== "undefined" ? globalThis : this);
