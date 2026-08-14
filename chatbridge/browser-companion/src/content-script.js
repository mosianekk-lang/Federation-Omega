(function () {
  "use strict";

  const core = globalThis.ChatBridgeCore;
  if (!core || globalThis.__chatBridgeCompanionLoaded) return;
  globalThis.__chatBridgeCompanionLoaded = true;

  let checkpointTimer = null;
  let settings = {autoSend: true, maxCapsuleChars: 60000, tokenThreshold: 65000, messageThreshold: 80};

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

  function currentCapsule() {
    return core.buildCapsule({
      sourceUrl: location.href,
      title: document.title,
      capturedAt: new Date().toISOString(),
      messages: core.collectMessages(document),
      maxChars: settings.maxCapsuleChars
    });
  }

  async function checkpoint(reason) {
    const capsule = currentCapsule();
    await chrome.runtime.sendMessage({type: "CHATBRIDGE_CHECKPOINT", capsule, reason});
    if (core.shouldPreempt(capsule.metrics, settings)) status("ChatBridge pre-limit checkpoint ready", "ready");
    return capsule;
  }

  function scheduleCheckpoint() {
    clearTimeout(checkpointTimer);
    checkpointTimer = setTimeout(() => checkpoint("DOM_CHANGE").catch(() => {}), 1600);
  }

  function findLimitBanner() {
    const root = document.querySelector("main") || document.body;
    if (!root) return null;
    const candidates = Array.from(root.querySelectorAll("div, section, aside"))
      .filter((node) => node.textContent && node.textContent.length < 1200 && core.isLimitNotice(node.textContent));
    candidates.sort((a, b) => a.textContent.length - b.textContent.length);
    return candidates.find((node) => node.querySelector("button")) || candidates[0] || null;
  }

  function decorateLimitBanner() {
    const banner = findLimitBanner();
    if (!banner || banner.querySelector("[data-chatbridge-start]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.chatbridgeStart = "true";
    button.className = "chatbridge-start-button";
    button.textContent = "Start a new chat via ChatBridge";
    button.setAttribute("aria-label", "Start a new chat via ChatBridge with the current actionable context");
    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "Preparing ChatBridge handoff…";
      try {
        const capsule = await checkpoint("LIMIT_WARNING_CLICK");
        const prompt = core.renderRestorePrompt(capsule);
        const result = await chrome.runtime.sendMessage({
          type: "CHATBRIDGE_OPEN",
          capsule,
          prompt,
          targetUrl: capsule.source.successorUrl
        });
        if (!result || !result.ok) throw new Error(result && result.error || "OPEN_FAILED");
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
    checkpoint("LIMIT_WARNING_DETECTED").catch(() => {});
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
    if (result && result.ok) settings = Object.assign(settings, result.settings);
    restorePendingTransfer().catch((error) => status(String(error.message || error), "error"));
    scheduleCheckpoint();
  });

  const observer = new MutationObserver(() => {
    decorateLimitBanner();
    scheduleCheckpoint();
  });
  observer.observe(document.documentElement, {subtree: true, childList: true, characterData: true});
  decorateLimitBanner();
})();
