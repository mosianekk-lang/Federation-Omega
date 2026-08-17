(function () {
  "use strict";

  const core = globalThis.ChatBridgeCore;
  if (!core || globalThis.__chatBridgeCompanionLoaded) return;
  globalThis.__chatBridgeCompanionLoaded = true;

  let checkpointTimer = null;
  let checkpointInFlight = null;
  let installationId = "";
  let settings = {
    autoSend: true,
    autoUpload: false,
    connectorUrl: "",
    namespaceKey: "",
    sensitivity: "GOVERNED_LOCAL",
    sourceCompleteClaim: false,
    maxCapsuleChars: 60000,
    tokenThreshold: 65000,
    messageThreshold: 80
  };

  function status(message, kind) {
    let chip = document.querySelector("[data-chatbridge-status]");
    if (!chip) {
      chip = document.createElement("div");
      chip.dataset.chatbridgeStatus = "true";
      document.documentElement.appendChild(chip);
    }
    chip.dataset.kind = kind || "info";
    chip.textContent = message;
    chip.hidden = false;
    clearTimeout(chip.__hideTimer);
    chip.__hideTimer = setTimeout(() => { chip.hidden = true; }, 5000);
  }

  function findLimitBanner() {
    const root = document.querySelector("main") || document.body;
    if (!root) return null;
    const candidates = Array.from(root.querySelectorAll("div, section, aside"))
      .filter((node) => node.textContent && node.textContent.length < 1200 && core.isLimitNotice(node.textContent));
    candidates.sort((a, b) => a.textContent.length - b.textContent.length);
    return candidates.find((node) => node.querySelector("button")) || candidates[0] || null;
  }

  async function capture(reason, options) {
    const identity = core.parseConversationIdentity(location.href);
    if (!identity.bound) return {capsule: null, receipt: null, skipped: "CONVERSATION_ID_UNAVAILABLE"};
    if (checkpointInFlight) return checkpointInFlight;

    checkpointInFlight = (async () => {
      const capturedAt = new Date().toISOString();
      const messages = core.collectMessages(document);
      const terminalBanner = options && options.terminalBanner || findLimitBanner();
      const terminalObserved = Boolean(options && options.terminalObserved || terminalBanner);
      const terminalText = terminalBanner ? core.normalizeText(terminalBanner.textContent) : "";
      const envelope = await core.buildCaptureEnvelope({
        sourceUrl: location.href,
        title: document.title,
        capturedAt,
        messages,
        namespaceKey: settings.namespaceKey,
        installationId,
        sensitivity: settings.sensitivity,
        sourceCompleteClaim: settings.sourceCompleteClaim,
        terminalObserved,
        terminalText
      });
      const captureResult = await chrome.runtime.sendMessage({
        type: "CHATBRIDGE_CAPTURE_ENVELOPE",
        envelope,
        reason
      });
      if (!captureResult || !captureResult.ok) {
        throw new Error(captureResult && captureResult.error || "CAPTURE_FAILED");
      }
      const capsule = core.buildCapsule({
        sourceUrl: location.href,
        title: document.title,
        capturedAt,
        messages,
        maxChars: settings.maxCapsuleChars,
        captureReceipt: captureResult.receipt,
        snapshotSha256: envelope.snapshot.sha256
      });
      await chrome.runtime.sendMessage({type: "CHATBRIDGE_CHECKPOINT", capsule, reason});
      if (captureResult.receipt.providerReadbackVerified) {
        status("ChatBridge full-fidelity capture acknowledged", "ready");
      } else if (captureResult.receipt.locallyDurable) {
        status("ChatBridge capture stored locally; provider readback pending", "ready");
      }
      if (core.shouldPreempt(capsule.metrics, settings)) {
        status("ChatBridge pre-limit checkpoint and capture are ready", "ready");
      }
      return {capsule, receipt: captureResult.receipt, envelope};
    })();

    try {
      return await checkpointInFlight;
    } finally {
      checkpointInFlight = null;
    }
  }

  function scheduleCheckpoint(reason) {
    clearTimeout(checkpointTimer);
    checkpointTimer = setTimeout(() => capture(reason || "DOM_STABLE_DELTA").catch(() => {}), 1600);
  }

  function decorateLimitBanner() {
    const banner = findLimitBanner();
    if (!banner || banner.querySelector("[data-chatbridge-start]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.chatbridgeStart = "true";
    button.className = "chatbridge-start-button";
    button.textContent = "Start a new chat via ChatBridge";
    button.setAttribute("aria-label", "Start a new chat via ChatBridge with the verified checkpoint and capture receipt");
    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "Verifying ChatBridge capture…";
      try {
        const result = await capture("LIMIT_WARNING_CLICK", {terminalObserved: true, terminalBanner: banner});
        if (!result.capsule) throw new Error(result.skipped || "CAPSULE_UNAVAILABLE");
        const prompt = core.renderRestorePrompt(result.capsule);
        const opened = await chrome.runtime.sendMessage({
          type: "CHATBRIDGE_OPEN",
          capsule: result.capsule,
          prompt,
          targetUrl: result.capsule.source.successorUrl
        });
        if (!opened || !opened.ok) throw new Error(opened && opened.error || "OPEN_FAILED");
        button.textContent = "ChatBridge successor opened";
      } catch (error) {
        button.disabled = false;
        button.textContent = "Start a new chat via ChatBridge";
        status(`ChatBridge handoff failed: ${String(error.message || error)}`, "error");
      }
    });
    const nativeButton = Array.from(banner.querySelectorAll("button")).find((node) => /start new chat/i.test(node.textContent || ""));
    if (nativeButton && nativeButton.parentElement) nativeButton.parentElement.insertBefore(button, nativeButton);
    else banner.appendChild(button);
    capture("LIMIT_WARNING_DETECTED", {terminalObserved: true, terminalBanner: banner}).catch(() => {});
  }

  function setComposerText(composer, text) {
    composer.focus();
    if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
      const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(composer), "value");
      if (descriptor && descriptor.set) descriptor.set.call(composer, text);
      else composer.value = text;
    } else {
      composer.textContent = text;
    }
    composer.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: text}));
    composer.dispatchEvent(new Event("change", {bubbles: true}));
  }

  async function waitForComposer(timeoutMs) {
    const selectors = ["#prompt-textarea", "textarea[placeholder]", "div[contenteditable='true']"];
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      for (const selector of selectors) {
        const found = document.querySelector(selector);
        if (found && !found.closest("[aria-hidden='true']")) return found;
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    return null;
  }

  async function restorePendingTransfer() {
    const result = await chrome.runtime.sendMessage({type: "CHATBRIDGE_GET_PENDING"});
    const pending = result && result.pending;
    if (!pending) return;
    const composer = await waitForComposer(30000);
    if (!composer) {
      status("ChatBridge successor opened; composer not yet available", "error");
      return;
    }
    setComposerText(composer, pending.prompt);
    if (settings.autoSend) {
      await new Promise((resolve) => setTimeout(resolve, 400));
      const sendButton = document.querySelector("button[data-testid='send-button'], button[aria-label*='Send']");
      if (sendButton && !sendButton.disabled) sendButton.click();
      else status("ChatBridge restore prompt prepared for sending", "ready");
    } else {
      status("ChatBridge restore prompt prepared for review", "ready");
    }
    await chrome.runtime.sendMessage({type: "CHATBRIDGE_CONSUMED", transferId: pending.transferId});
  }

  chrome.runtime.sendMessage({type: "CHATBRIDGE_SETTINGS"}).then((result) => {
    if (result && result.ok) {
      settings = Object.assign(settings, result.settings);
      installationId = result.installationId || "";
    }
    restorePendingTransfer().catch((error) => status(String(error.message || error), "error"));
    scheduleCheckpoint("INITIAL_DOM_STABLE");
  });

  const observer = new MutationObserver(() => {
    decorateLimitBanner();
    scheduleCheckpoint("DOM_STABLE_DELTA");
  });
  observer.observe(document.documentElement, {subtree: true, childList: true, characterData: true});
  decorateLimitBanner();
})();
