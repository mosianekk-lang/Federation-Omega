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
      if (this.circuitOpen || this.streaming) return {state: "DEFERRED", deltas: []};
      if (now - this.lastCaptureAt < this.options.minimumIntervalMs) {
        return {state: "THROTTLED", deltas: []};
      }
      const started = typeof performance !== "undefined" ? performance.now() : now;
      const deltas = [];
      for (const message of messages) {
        const id = String(message.id || "");
        const text = String(message.text || "");
        if (!id || !text) continue;
        const hash = PerformanceSentinel.hashText(text);
        if (this.lastHashes.get(id) === hash) continue;
        this.lastHashes.set(id, hash);
        deltas.push({id, role: String(message.role || "unknown"), text, hash});
      }
      const payloadChars = deltas.reduce((sum, item) => sum + item.text.length, 0);
      const ended = typeof performance !== "undefined" ? performance.now() : now;
      const elapsedMs = Math.max(0, ended - started);
      if (payloadChars > this.options.maximumPayloadChars || elapsedMs > this.options.maximumCaptureMs) {
        this.circuitOpen = true;
        return {state: "CIRCUIT_OPEN", deltas: [], payloadChars, elapsedMs};
      }
      this.lastCaptureAt = now;
      this.queue.push(...deltas);
      if (this.queue.length > this.options.maximumQueueItems) {
        this.queue.splice(0, this.queue.length - this.options.maximumQueueItems);
      }
      return {state: deltas.length ? "DELTA_READY" : "NO_CHANGE", deltas, payloadChars, elapsedMs};
    }

    drain(limit = 16) {
      return this.queue.splice(0, Math.max(0, limit));
    }

    resetCircuit() {
      this.circuitOpen = false;
    }
  }

  root.ChatPerformanceSentinel = {PerformanceSentinel, DEFAULTS};
  if (typeof module !== "undefined" && module.exports) module.exports = root.ChatPerformanceSentinel;
})(typeof globalThis !== "undefined" ? globalThis : this);
