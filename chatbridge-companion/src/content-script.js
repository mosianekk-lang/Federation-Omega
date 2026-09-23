(function () {
  "use strict";

  const core = globalThis.ChatBridgeCore;
  if (!core || globalThis.__chatBridgeCompanionLoaded) return;
  globalThis.__chatBridgeCompanionLoaded = true;

  let checkpointTimer = null;
  let periodicTimer = null;
  let captureInFlight = false;
  let settings = {
    autoSend: true,
    maxReplayChars: 28000,
    tokenThreshold: 65000,
    messageThreshold: 80,
    captureIntervalMs: 30000
  };
  let autoHandoffInFlight = false;
  let autoHandoffComplete = false;
  let autoHandoffLastAttemptAt = 0;
  const AUTO_HANDOFF_RETRY_MS = 60000;

  function status(message, kind, timeoutMs) {
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
    chip.__hideTimer = setTimeout(() => { chip.hidden = true; }, timeoutMs || 6000);
  }

  function currentPacket() {
    const messages = core.collectMessages(document);
    return core.buildCapturePacket({
      sourceUrl: location.href,
      title: document.title,
      capturedAt: new Date().toISOString(),
      messages,
      terminalNotice: core.findLimitNotice(document)
    });
  }

  async function checkpoint(reason, options) {
    if (captureInFlight) return null;
    captureInFlight = true;
    try {
      const packet = currentPacket();
      const result = await chrome.runtime.sendMessage({type: "CHATBRIDGE_CAPTURE", packet, reason});
      if (!result || !result.ok) throw new Error(result && result.error || "CAPTURE_FAILED");
      const captured = {packet, result};
      if (!(options && options.suppressAuto) && core.shouldAutoHandoff(packet, settings)) {
        const triggerReason = packet.terminalNotice ? "TERMINAL_LIMIT_DETECTED" : "PRE_LIMIT_PRESSURE";
        status("ChatBridge Ω4.9 capacity pressure — automatic handoff starting", "ready", 10000);
        queueMicrotask(() => triggerAutomaticHandoff(captured, triggerReason).catch((error) => {
          status(`ChatBridge automatic handoff retry armed: ${String(error.message || error)}`, "error", 12000);
        }));
      }
      return captured;
    } finally {
      captureInFlight = false;
    }
  }

  function scheduleCheckpoint(reason) {
    clearTimeout(checkpointTimer);
    checkpointTimer = setTimeout(() => checkpoint(reason || "DOM_CHANGE").catch(() => {}), 1800);
  }

  function findLimitBanner() {
    const root = document.querySelector("main") || document.body;
    if (!root) return null;
    const candidates = Array.from(root.querySelectorAll("div, section, aside"))
      .filter((node) => node.textContent && node.textContent.length < 1600 && core.isLimitNotice(node.textContent));
    candidates.sort((a, b) => a.textContent.length - b.textContent.length);
    return candidates.find((node) => node.querySelector("button")) || candidates[0] || null;
  }

  async function openSuccessorForCapture(captured, reason) {
    if (!captured || !captured.packet) throw new Error("CAPTURE_REQUIRED");
    let durableEgress = null;
    try {
      durableEgress = await chrome.runtime.sendMessage({
        type: "CHATBRIDGE_EDGE_EGRESS_STATUS",
        conversationKey: captured.packet.conversationKey,
        reason: "CAPACITY_HANDOFF_PREDETACH"
      });
    } catch (_) {
      durableEgress = {ok: false, state: "EDGE_EGRESS_CALL_FAILED"};
    }
    const result = await chrome.runtime.sendMessage({
      type: "CHATBRIDGE_OPEN",
      conversationKey: captured.packet.conversationKey,
      reason: reason || "CAPACITY_HANDOFF"
    });
    if (!result || !result.ok) throw new Error(result && result.error || "OPEN_FAILED");
    status(
      `ChatBridge successor ${result.reused ? "reused" : "opened"} with ${result.packetCount} replay packets`,
      "ready",
      10000
    );
    return Object.assign({}, result, {durableEgress});
  }

  async function triggerAutomaticHandoff(captured, reason) {
    if (!captured || autoHandoffComplete || autoHandoffInFlight) return null;
    const now = Date.now();
    if (now - autoHandoffLastAttemptAt < AUTO_HANDOFF_RETRY_MS) return null;
    autoHandoffInFlight = true;
    autoHandoffLastAttemptAt = now;
    try {
      const result = await openSuccessorForCapture(captured, reason || "CAPACITY_HANDOFF");
      autoHandoffComplete = true;
      return result;
    } finally {
      autoHandoffInFlight = false;
    }
  }

  async function startSuccessor() {
    const captured = await checkpoint("SUCCESSOR_REQUEST", {suppressAuto: true});
    if (!captured) throw new Error("CAPTURE_BUSY");
    return openSuccessorForCapture(captured, "CAPACITY_HANDOFF_MANUAL_RETRY");
  }

  function decorateLimitBanner() {
    const banner = findLimitBanner();
    if (!banner || banner.querySelector("[data-chatbridge-start]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.chatbridgeStart = "true";
    button.className = "chatbridge-start-button";
    button.textContent = "Retry successor via ChatBridge Ω4.9";
    button.setAttribute("aria-label", "Retry the automatic ChatBridge successor handoff for this rendered conversation");
    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "Capturing full rendered ledger…";
      try {
        await startSuccessor();
        button.textContent = "ChatBridge successor opened";
      } catch (error) {
        button.disabled = false;
        button.textContent = "Retry successor via ChatBridge Ω4.9";
        status(`ChatBridge handoff failed: ${String(error.message || error)}`, "error", 10000);
      }
    });
    const nativeButton = Array.from(banner.querySelectorAll("button")).find((node) => /start new chat/i.test(node.textContent || ""));
    if (nativeButton && nativeButton.parentElement) nativeButton.parentElement.insertBefore(button, nativeButton);
    else banner.appendChild(button);
    checkpoint("TERMINAL_WARNING_DETECTED").catch(() => {});
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

  function assistantCount() {
    return document.querySelectorAll("[data-message-author-role='assistant']").length;
  }

  async function waitForAssistantAfter(previousCount, timeoutMs) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      if (assistantCount() > previousCount) return true;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    return false;
  }

  async function sendPendingPackets() {
    while (true) {
      const result = await chrome.runtime.sendMessage({type: "CHATBRIDGE_GET_PENDING"});
      const pending = result && result.pending;
      if (!pending) return;
      const composer = await waitForComposer(45000);
      if (!composer) {
        status("ChatBridge successor opened; composer not available", "error", 10000);
        return;
      }
      setComposerText(composer, pending.prompt.text);
      if (!settings.autoSend) {
        status(`ChatBridge packet ${pending.packetIndex}/${pending.packetCount} prepared for review`, "ready", 12000);
        return;
      }
      const before = assistantCount();
      await new Promise((resolve) => setTimeout(resolve, 450));
      const sendButton = document.querySelector("button[data-testid='send-button'], button[aria-label*='Send']");
      if (!sendButton || sendButton.disabled) {
        status(`ChatBridge packet ${pending.packetIndex}/${pending.packetCount} prepared; send button unavailable`, "error", 12000);
        return;
      }
      sendButton.click();
      const isFinal = pending.packetIndex === pending.packetCount;
      if (!isFinal) {
        const acknowledged = await waitForAssistantAfter(before, 180000);
        if (!acknowledged) {
          status(`ChatBridge packet ${pending.packetIndex} sent; acknowledgement timeout`, "error", 12000);
          return;
        }
      }
      const consumed = await chrome.runtime.sendMessage({
        type: "CHATBRIDGE_PACKET_CONSUMED",
        transferId: pending.transferId
      });
      if (!consumed || !consumed.ok || consumed.complete) {
        if (consumed && consumed.complete) status("ChatBridge Ω4.9 replay packets delivered", "ready", 12000);
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
  }

  async function exportLedger() {
    const packet = currentPacket();
    await checkpoint("USER_EXPORT");
    const result = await chrome.runtime.sendMessage({type: "CHATBRIDGE_EXPORT_LEDGER", conversationKey: packet.conversationKey});
    if (!result || !result.ok) throw new Error(result && result.error || "EXPORT_FAILED");
    status("ChatBridge Ω4.9 ledger export created", "ready", 10000);
  }

  document.addEventListener("keydown", (event) => {
    if (!event.altKey || !event.shiftKey) return;
    if (event.code === "KeyB") {
      event.preventDefault();
      checkpoint("KEYBOARD_CHECKPOINT").then(() => status("ChatBridge checkpoint verified", "ready")).catch((error) => status(String(error.message || error), "error"));
    }
    if (event.code === "KeyE") {
      event.preventDefault();
      exportLedger().catch((error) => status(String(error.message || error), "error", 10000));
    }
  });

  chrome.runtime.sendMessage({type: "CHATBRIDGE_SETTINGS"}).then((result) => {
    if (result && result.ok) settings = Object.assign(settings, result.settings);
    sendPendingPackets().catch((error) => status(String(error.message || error), "error", 10000));
    scheduleCheckpoint("INITIAL_LOAD");
    clearInterval(periodicTimer);
    periodicTimer = setInterval(() => checkpoint("PERIODIC_WRITE_AHEAD").catch(() => {}), Math.max(10000, Number(settings.captureIntervalMs) || 30000));
  });

  const observer = new MutationObserver(() => {
    decorateLimitBanner();
    scheduleCheckpoint("DOM_CHANGE");
  });
  observer.observe(document.documentElement, {subtree: true, childList: true, characterData: true});
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") checkpoint("VISIBILITY_HIDDEN").catch(() => {});
  });
  decorateLimitBanner();
})();
