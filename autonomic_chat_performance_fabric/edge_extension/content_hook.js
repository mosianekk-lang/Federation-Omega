(function (root) {
  "use strict";

  if (root.__FACPF_EDGE_HOOK__) return;
  const api = root.chrome;
  const Diagnostic = root.FACPFNativeEdgeDiagnostic && root.FACPFNativeEdgeDiagnostic.NativeEdgeChatGPTDiagnostic;
  if (!api || !api.runtime || !Diagnostic) return;

  const diagnostic = new Diagnostic({
    config: {
      enabled: true,
      mode: "SHADOW_OBSERVE_ONLY",
      activation: {authorizedEdgeHookPresent: true}
    },
    performanceApi: root.performance,
    ObserverClass: root.PerformanceObserver,
    eventTarget: root.document
  });
  diagnostic.start({formationPermitValidated: true, operatorActivationValidated: true});

  const allowed = new Set([
    "FACPF_RECORD_HYDRATION",
    "FACPF_RECORD_TRANSPORT",
    "FACPF_RECORD_MEMORY",
    "FACPF_SNAPSHOT",
    "FACPF_ROLLBACK"
  ]);
  const listener = (message, sender, sendResponse) => {
    if (!message || !allowed.has(message.type) || sender.id !== api.runtime.id) {
      sendResponse({state: "REJECTED_MESSAGE"});
      return false;
    }
    if (message.type === "FACPF_RECORD_HYDRATION") sendResponse(diagnostic.recordHydration(message.milestone, message.atMs));
    if (message.type === "FACPF_RECORD_TRANSPORT") sendResponse(diagnostic.recordTransportState(message.transportState));
    if (message.type === "FACPF_RECORD_MEMORY") sendResponse(diagnostic.recordMemorySample(message.usedBytes, message.limitBytes));
    if (message.type === "FACPF_SNAPSHOT") sendResponse(diagnostic.snapshot());
    if (message.type === "FACPF_ROLLBACK") {
      diagnostic.rollback();
      api.runtime.onMessage.removeListener(listener);
      delete root.__FACPF_EDGE_HOOK__;
      sendResponse({state: "ROLLED_BACK"});
    }
    return false;
  };
  api.runtime.onMessage.addListener(listener);
  root.__FACPF_EDGE_HOOK__ = {state: "ATTACHED_AGGREGATE_ONLY"};
})(typeof globalThis !== "undefined" ? globalThis : this);
