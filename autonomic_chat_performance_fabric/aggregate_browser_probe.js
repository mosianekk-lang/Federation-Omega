(function (root) {
  "use strict";

  const MAX_LONG_TASK_SAMPLES = 256;

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
    const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * fraction) - 1));
    return rounded(sorted[index]);
  }

  class AggregateBrowserProbe {
    constructor(performanceApi, ObserverClass) {
      this.performanceApi = performanceApi;
      this.ObserverClass = ObserverClass;
      this.observer = null;
      this.longTaskDurations = [];
      this.droppedSamples = 0;
      this.started = false;
    }

    start() {
      const supported = Array.isArray(this.ObserverClass && this.ObserverClass.supportedEntryTypes)
        ? this.ObserverClass.supportedEntryTypes
        : [];
      if (!supported.includes("longtask")) return {state: "UNSUPPORTED", entryType: "longtask"};
      this.observer = new this.ObserverClass((entryList) => {
        for (const entry of entryList.getEntries()) {
          if (this.longTaskDurations.length >= MAX_LONG_TASK_SAMPLES) {
            this.droppedSamples += 1;
            continue;
          }
          this.longTaskDurations.push(finite(entry.duration));
        }
      });
      this.observer.observe({type: "longtask", buffered: true});
      this.started = true;
      return {state: "OBSERVING", entryType: "longtask"};
    }

    snapshot() {
      const entries = (type) => {
        if (!this.performanceApi || typeof this.performanceApi.getEntriesByType !== "function") return [];
        const result = this.performanceApi.getEntriesByType(type);
        return Array.isArray(result) ? result : [];
      };
      const navigation = entries("navigation")[0] || {};
      const resources = entries("resource");
      const resourceDurations = resources.map((entry) => finite(entry.duration));
      const longTaskTotal = this.longTaskDurations.reduce((sum, value) => sum + value, 0);
      return {
        schema: "FACPF-BROWSER-AGGREGATE-1",
        privacy: {
          messageTextCaptured: false,
          perMessageIdentifiersCaptured: false,
          rawDomCaptured: false,
          resourceNamesCaptured: false,
          attributionCaptured: false
        },
        navigation: {
          sampleCount: navigation.duration === undefined ? 0 : 1,
          durationMs: rounded(navigation.duration),
          responseMs: rounded(finite(navigation.responseEnd) - finite(navigation.requestStart)),
          domContentLoadedMs: rounded(navigation.domContentLoadedEventEnd),
          loadEventMs: rounded(navigation.loadEventEnd)
        },
        resources: {
          count: resources.length,
          totalDurationMs: rounded(resourceDurations.reduce((sum, value) => sum + value, 0)),
          maximumDurationMs: rounded(resourceDurations.length ? Math.max(...resourceDurations) : 0)
        },
        longTasks: {
          supported: this.started,
          count: this.longTaskDurations.length,
          totalDurationMs: rounded(longTaskTotal),
          maximumDurationMs: rounded(this.longTaskDurations.length ? Math.max(...this.longTaskDurations) : 0),
          p50DurationMs: percentile(this.longTaskDurations, 0.5),
          p95DurationMs: percentile(this.longTaskDurations, 0.95),
          droppedSamples: this.droppedSamples
        }
      };
    }

    stop() {
      if (this.observer && typeof this.observer.disconnect === "function") this.observer.disconnect();
      this.observer = null;
      this.started = false;
    }

    rollback() {
      this.stop();
      this.longTaskDurations.length = 0;
      this.droppedSamples = 0;
    }
  }

  root.ChatPerformanceAggregateProbe = {AggregateBrowserProbe, MAX_LONG_TASK_SAMPLES};
  if (typeof module !== "undefined" && module.exports) module.exports = root.ChatPerformanceAggregateProbe;
})(typeof globalThis !== "undefined" ? globalThis : this);
