(function (root) {
  "use strict";

  const ORIGIN = "https://chatgpt.com/*";
  const CONFIG_DEFAULTS = Object.freeze({
    enabled: false,
    authorizedEdgeHookPresent: false,
    formationPermitValidated: false,
    operatorActivationValidated: false,
    allowedOrigin: ORIGIN
  });
  const SCRIPT_FILES = Object.freeze([
    "aggregate_browser_probe.js",
    "native_edge_chatgpt_diagnostic.js",
    "content_hook.js"
  ]);
  const MESSAGE_TYPES = new Set(["FACPF_STATUS", "FACPF_ATTACH", "FACPF_DETACH", "FACPF_SNAPSHOT"]);

  function positiveTabId(value) {
    return Number.isInteger(value) && value > 0;
  }

  function activationState(config) {
    if (config.enabled !== true) return "DISABLED_CONFIG";
    if (config.allowedOrigin !== ORIGIN) return "ORIGIN_POLICY_MISMATCH";
    if (config.authorizedEdgeHookPresent !== true) return "AUTHORIZED_EDGE_HOOK_REQUIRED";
    if (config.formationPermitValidated !== true || config.operatorActivationValidated !== true) {
      return "ACTIVATION_EVIDENCE_INCOMPLETE";
    }
    return "POLICY_ADMITTED";
  }

  function createController(api) {
    if (!api || !api.runtime || !api.storage || !api.permissions || !api.scripting || !api.tabs) {
      throw new TypeError("complete extension API adapter required");
    }

    async function managedConfig() {
      const value = await api.storage.managed.get(CONFIG_DEFAULTS);
      return {...CONFIG_DEFAULTS, ...(value || {})};
    }

    async function status() {
      const config = await managedConfig();
      const permission = await api.permissions.contains({permissions: ["scripting"], origins: [ORIGIN]});
      return {
        schema: "FACPF-EDGE-HOOK-STATUS-1",
        state: activationState(config),
        optionalPermissionPresent: permission === true,
        runtimeBoundary: "AUTHORIZED_MANAGED_POLICY_AND_INTERNAL_ATTACH_REQUIRED",
        contentCaptured: false
      };
    }

    async function handle(message, sender = {}) {
      if (!message || !MESSAGE_TYPES.has(message.type)) return {state: "REJECTED_MESSAGE"};
      if (sender.id !== api.runtime.id) return {state: "REJECTED_SENDER"};
      if (message.type === "FACPF_STATUS") return status();
      if (!positiveTabId(message.tabId)) return {state: "REJECTED_TAB_ID"};

      if (message.type === "FACPF_DETACH") {
        try {
          return await api.tabs.sendMessage(message.tabId, {type: "FACPF_ROLLBACK"});
        } catch (_error) {
          return {state: "ALREADY_DETACHED"};
        }
      }

      if (message.type === "FACPF_SNAPSHOT") {
        try {
          return await api.tabs.sendMessage(message.tabId, {type: "FACPF_SNAPSHOT"});
        } catch (_error) {
          return {state: "NOT_ATTACHED"};
        }
      }

      const config = await managedConfig();
      const admission = activationState(config);
      if (admission !== "POLICY_ADMITTED") return {state: "ATTACH_DENIED", reason: admission};
      const permitted = await api.permissions.contains({permissions: ["scripting"], origins: [ORIGIN]});
      if (permitted !== true) return {state: "ATTACH_DENIED", reason: "OPTIONAL_PERMISSION_REQUIRED"};
      await api.scripting.executeScript({target: {tabId: message.tabId}, files: SCRIPT_FILES.slice()});
      return {state: "ATTACHED", aggregateOnly: true};
    }

    return {handle, status, managedConfig};
  }

  function register(api) {
    const controller = createController(api);
    api.runtime.onMessage.addListener((message, sender, sendResponse) => {
      controller.handle(message, sender).then(sendResponse, () => sendResponse({state: "INTERNAL_ERROR"}));
      return true;
    });
    return controller;
  }

  const exported = {ORIGIN, CONFIG_DEFAULTS, SCRIPT_FILES, MESSAGE_TYPES, activationState, createController, register};
  if (typeof module !== "undefined" && module.exports) module.exports = exported;
  if (root.chrome && root.chrome.runtime && root.chrome.runtime.onMessage) register(root.chrome);
})(typeof globalThis !== "undefined" ? globalThis : this);
