(() => {
  const seen = new Set();
  let scheduled = false;

  function hashText(text) {
    let h = 2166136261;
    for (let i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0).toString(16).padStart(8, "0");
  }

  function conversationId() {
    const match = location.pathname.match(/\/c\/([A-Za-z0-9-]+)/);
    return match ? match[1] : `visible-page-${hashText(location.origin + location.pathname)}`;
  }

  function collect() {
    scheduled = false;
    const nodes = [...document.querySelectorAll("[data-message-author-role]")];
    const events = [];
    nodes.forEach((node, index) => {
      const role = node.getAttribute("data-message-author-role") || "observer";
      const content = (node.innerText || "").trim();
      if (!content) return;
      const domId = node.getAttribute("data-message-id") || node.id || `${role}-${index + 1}-${hashText(content)}`;
      const fingerprint = `${conversationId()}:${domId}:${hashText(content)}`;
      if (seen.has(fingerprint)) return;
      seen.add(fingerprint);
      events.push({
        schema: "FEDERATION-LIVE-BIBLE-CAPTURE-EVENT-2",
        source_id: "chatgpt-browser-extension",
        source_type: "BROWSER_CAPTURE",
        conversation_id: conversationId(),
        message_id: domId.replace(/[^A-Za-z0-9._:@/-]/g, "_").slice(0, 240),
        sequence: index + 1,
        role: ["user", "assistant", "system", "tool"].includes(role) ? role : "observer",
        content,
        occurred_at: new Date().toISOString(),
        observed_at: new Date().toISOString(),
        privacy_tier: "P2_CONFIDENTIAL",
        authority_class: "A1",
        case_wall: "GENERAL",
        metadata: {url_path: location.pathname, capture_mode: "VISIBLE_DOM_ONLY"}
      });
    });
    if (events.length) chrome.runtime.sendMessage({type: "LIVE_BIBLE_EVENTS", events});
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(collect, 750);
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, {childList: true, subtree: true, characterData: true});
  schedule();
})();
