(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = {token: "", epoch: 0, refreshVersion: 0, services: [], bindings: [], missionId: "", pendingMission: "", pendingRequest: null, retryPending: false, chatBusy: false, missionBusy: false, wakeBusy: false, wakeNeedsReadback: false};
  try { state.token = (sessionStorage.getItem("fuseSession") || "").trim(); } catch (_) { /* In-memory sessions also work when storage is blocked. */ }
  $("token").value = state.token;

  function node(tag, className, value) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== undefined && value !== null) element.textContent = String(value);
    return element;
  }
  function text(id, value) { $(id).textContent = value; }
  function notice(id, message, error = false) { text(id, message); $(id).dataset.error = String(error); }
  function human(value) { return String(value || "Unknown").replace(/[_.-]+/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()); }
  function errorMessage(error) {
    if (error.code === "FUSE_SESSION_REQUIRED") return "Connect an existing FUSE session to continue.";
    if (error.status === 401 || error.status === 403) return "This session was not accepted. Update your session in Workspace access.";
    if (error.status === 404) return "The requested record or endpoint was not found for this session.";
    if (error.code === "INVALID_JSON") return "The runtime returned an unreadable response. Refresh readback before retrying an action.";
    if (error.code === "NETWORK_UNCONFIRMED") return "The request ended without a confirmed response. Check readback before retrying an action.";
    if (error.status === 503) return "The runtime is holding this request. Its execution binding needs attention.";
    if (error.status === 422) return "Check the input format and try again.";
    return "The request could not be confirmed. Refresh the runtime state for the latest readback.";
  }
  function headers(json = false) {
    const value = state.token.trim();
    if (!value) { const error = new Error(); error.code = "FUSE_SESSION_REQUIRED"; throw error; }
    const result = {"X-Fuse-Authorization": value.startsWith("Bearer ") ? value : "Bearer " + value};
    if (json) result["Content-Type"] = "application/json";
    return result;
  }
  async function api(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), options.method === "POST" ? 120000 : 20000);
    try {
      let response;
      try { response = await fetch(path, {...options, cache: "no-store", signal: controller.signal, credentials: "same-origin"}); }
      catch (_) { const error = new Error(); error.code = "NETWORK_UNCONFIRMED"; throw error; }
      let body;
      try { body = await response.json(); }
      catch (_) { const error = new Error(); error.code = controller.signal.aborted ? "NETWORK_UNCONFIRMED" : "INVALID_JSON"; error.status = response.status; throw error; }
      if (!response.ok) { const error = new Error(); error.status = response.status; error.code = body?.detail?.reason || body?.reason || "HTTP_ERROR"; throw error; }
      if (!body || typeof body !== "object" || Array.isArray(body)) { const error = new Error(); error.code = "INVALID_JSON"; throw error; }
      return body;
    } finally { clearTimeout(timer); }
  }
  function stringList(value) { return Array.isArray(value) && value.every((item) => typeof item === "string"); }
  function validServices(value) {
    return Array.isArray(value) && value.every((row) => row && typeof row === "object" &&
      typeof row.service_id === "string" && typeof row.family === "string" && typeof row.source_supported === "boolean" &&
      (row.required_capabilities === null || stringList(row.required_capabilities)) &&
      (row.optional_capabilities === null || row.optional_capabilities === undefined || stringList(row.optional_capabilities)));
  }
  function validBindings(value) {
    return Array.isArray(value) && value.every((row) => row && typeof row === "object" &&
      typeof row.capability_id === "string" && typeof row.family === "string" && typeof row.transport === "string" &&
      typeof row.maturity === "string" && typeof row.callable === "boolean" && typeof row.runtime_native === "boolean" && stringList(row.operations));
  }
  function showView(view, focus = false) {
    const panels = {overview: "overviewPanel", chat: "chatPanel", missions: "missionsPanel", connections: "connectionsPanel", catalog: "catalogPanel"};
    const names = {overview: "Overview", chat: "Assistant", missions: "Missions", connections: "Connections", catalog: "Service catalog"};
    if (!panels[view]) view = "overview";
    Object.entries(panels).forEach(([name, id]) => { $(id).hidden = name !== view; });
    document.querySelectorAll("[data-view]").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === view);
      if (button.dataset.view === view) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
    });
    text("viewName", names[view]);
    if (location.hash !== "#" + view) history.replaceState(null, "", "#" + view);
    if (focus) { const heading = $(panels[view]).querySelector("h1"); heading.tabIndex = -1; heading.focus(); }
  }
  document.querySelectorAll("[data-view], [data-go]").forEach((button) => { button.addEventListener("click", () => showView(button.dataset.view || button.dataset.go, true)); });
  window.addEventListener("hashchange", () => showView(location.hash.slice(1)));
  $("openSessionTop").onclick = $("openSession").onclick = () => { $("sessionPanel").hidden = !$("sessionPanel").hidden; if (!$("sessionPanel").hidden) $("token").focus(); };
  function setSignal(id, value, good, bad = false) { text(id, value); $(id).dataset.tone = good ? "good" : bad ? "error" : "held"; }
  function renderHealth(health) {
    if (!health) {
      text("health", "Readback unavailable"); $("health").dataset.tone = "error";
      setSignal("runtimeReady", "Unconfirmed", false);
      ["integrityReady", "sessionReady", "executionReady"].forEach((id) => setSignal(id, "Not assessed", false));
      text("lastReadback", "Runtime readback not confirmed");
      return;
    }
    const integrity = health.sol_integrity?.event_chain_valid;
    const allReady = health.ok === true && integrity === true && health.fuse_session_ready === true && health.fuse_execution_ready === true;
    text("health", allReady ? "Runtime responding" : "Runtime needs attention"); $("health").dataset.tone = allReady ? "good" : "held";
    setSignal("runtimeReady", health.ok === true ? "Responding" : "Held", health.ok === true);
    setSignal("integrityReady", integrity === true ? "Chain verified" : integrity === false ? "Integrity mismatch" : "Not assessed", integrity === true, integrity === false);
    setSignal("sessionReady", health.fuse_session_ready === true ? "Configured" : "Binding needed", health.fuse_session_ready === true);
    setSignal("executionReady", health.fuse_execution_ready === true ? "Configured" : "Binding needed", health.fuse_execution_ready === true);
    text("lastReadback", "Runtime readback · " + new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}));
  }
  function emptyList(id, message) { $(id).replaceChildren(node("div", "empty-card", message)); }
  function pair(list, name, value) { list.append(node("dt", "", name), node("dd", "", value || "Not specified")); }
  function badge(value, held = false) { const result = node("span", "badge", value); if (held) result.dataset.tone = "held"; return result; }

  function renderServices() {
    const query = $("serviceSearch").value.trim().toLowerCase();
    const filter = $("serviceFilter").value;
    const rows = state.services.filter((row) => {
      const matches = [row.service_id, row.family, row.description, ...(row.required_capabilities || [])].join(" ").toLowerCase().includes(query);
      return matches && (filter === "all" || (filter === "available" && row.source_supported === true) || (filter === "missing" && row.source_supported !== true));
    });
    $("serviceList").replaceChildren();
    if (!state.services.length) { emptyList("serviceList", state.token ? "No catalog rows have been read for this session." : "Connect your session to explore the existing source catalog."); return; }
    text("serviceSummary", `${rows.length} of ${state.services.length} services · Source coverage only; runtime verification is separate.`);
    if (!rows.length) { emptyList("serviceList", "No services match this search. Try another term or filter."); return; }
    for (const row of rows) {
      const card = node("article", "service-card");
      card.append(node("p", "card-family", human(row.family)), badge(row.source_state === "LEGACY_ALIAS" ? "Alias mapped" : row.source_supported === true ? "Source available" : "Definition needed", row.source_supported !== true), node("h2", "", human(row.service_id)), node("p", "card-id", row.service_id));
      card.append(node("p", "", row.description || (row.source_supported ? "Existing service definition is available for integration." : "This registered service still needs its source definition reconciled.")));
      card.append(node("p", "", "Runtime: " + human(row.runtime_readiness || "NOT_ASSESSED")));
      const details = node("details"); details.append(node("summary", "", "Capabilities & source")); const list = node("dl");
      pair(list, "Required capabilities", (row.required_capabilities || []).join(", ") || "Not defined");
      pair(list, "Optional capabilities", (row.optional_capabilities || []).join(", ") || "None declared");
      pair(list, "Implementation service", row.implementation_service_id || "Not resolved");
      pair(list, "Required maturity", row.required_maturity || "Not defined");
      if (row.alias_of) pair(list, "Alias of", row.alias_of);
      details.append(list); card.append(details); $("serviceList").append(card);
    }
  }
  function bindingLabel(row) {
    if (row.maturity === "SOURCE_BOUND") return "Source bound";
    if (row.maturity === "RUNTIME_BOUND") return "Runtime binding reported";
    if (row.transport === "CHAT_SESSION_TOOL") return "Client route";
    if (row.transport === "ESTATE_ROUTE_DISCOVERY") return "Discovery required";
    return human(row.maturity);
  }
  function renderConnections() {
    const query = $("connectionSearch").value.trim().toLowerCase(); const filter = $("connectionFilter").value;
    const rows = state.bindings.filter((row) => {
      const matches = [row.capability_id, row.family, row.transport, ...(row.operations || [])].join(" ").toLowerCase().includes(query);
      return matches && (filter === "all" || (filter === "native" && row.runtime_native === true) || (filter === "client" && row.transport === "CHAT_SESSION_TOOL") || (filter === "discovery" && row.transport === "ESTATE_ROUTE_DISCOVERY"));
    });
    $("connectionsList").replaceChildren();
    if (!state.bindings.length) { emptyList("connectionsList", state.token ? "No capability rows have been read for this session." : "Connect your session to inspect runtime capability reports."); return; }
    text("connectionSummary", `${rows.length} of ${state.bindings.length} registered routes · Binding reports are not provider execution proof.`);
    if (!rows.length) { emptyList("connectionsList", "No connections match this search. Try another term or filter."); return; }
    for (const row of rows) {
      const card = node("article", "service-card");
      card.append(node("p", "card-family", human(row.family)), badge(bindingLabel(row), row.callable !== true), node("h2", "", human(row.capability_id)), node("p", "card-id", row.capability_id));
      card.append(node("p", "", (row.operations || []).join(" · ")));
      const details = node("details"); details.append(node("summary", "", "Inspect binding")); const list = node("dl");
      pair(list, "Transport", row.transport); pair(list, "Reported maturity", row.maturity);
      pair(list, "Reported callable", row.callable === true ? "Yes — action-specific verification still required" : "Not established for this runtime");
      pair(list, "Native adapter", row.runtime_native === true ? "Source adapter present" : "Separate client or estate route");
      pair(list, "Authority", row.authority); if (row.notes) pair(list, "Binding note", row.notes);
      details.append(list); card.append(details); $("connectionsList").append(card);
    }
  }
  ["serviceSearch", "serviceFilter"].forEach((id) => $(id).addEventListener(id.endsWith("Search") ? "input" : "change", renderServices));
  ["connectionSearch", "connectionFilter"].forEach((id) => $(id).addEventListener(id.endsWith("Search") ? "input" : "change", renderConnections));
  async function refreshWorkspace() {
    const epoch = state.epoch; const version = ++state.refreshVersion;
    $("refreshWorkspace").disabled = true; $("globalNotice").hidden = true;
    const requests = [api("/health")];
    if (state.token) { requests.push(api("/v1/os/catalog", {headers: headers()}), api("/v1/capabilities", {headers: headers()})); text("serviceSummary", "Reading source catalog…"); text("connectionSummary", "Reading capability registry…"); }
    const results = await Promise.allSettled(requests);
    if (epoch !== state.epoch || version !== state.refreshVersion) return;
    $("refreshWorkspace").disabled = false;
    renderHealth(results[0].status === "fulfilled" ? results[0].value : null);
    if (!state.token) { renderServices(); renderConnections(); return; }
    const errors = [];
    if (results[1].status === "fulfilled" && validServices(results[1].value.services)) {
      const catalog = results[1].value; state.services = catalog.services.filter((row) => row && typeof row.service_id === "string");
      text("serviceCount", state.services.length);
      text("sourceCount", state.services.filter((row) => row.source_supported === true).length);
      text("gapCount", state.services.filter((row) => row.source_supported !== true).length);
      renderServices();
    } else {
      state.services = []; ["serviceCount", "sourceCount", "gapCount"].forEach((id) => text(id, "—")); renderServices();
      text("serviceSummary", "Catalog readback not confirmed."); errors.push(results[1].reason || {code: "INVALID_JSON"});
    }
    if (results[2].status === "fulfilled" && validBindings(results[2].value.bindings)) { state.bindings = results[2].value.bindings.filter((row) => row && typeof row.capability_id === "string"); renderConnections(); }
    else { state.bindings = []; renderConnections(); text("connectionSummary", "Capability readback not confirmed."); errors.push(results[2].reason || {code: "INVALID_JSON"}); }
    if (errors.some((error) => error.status === 401 || error.status === 403)) { text("sidebarSession", "Session not accepted"); notice("sessionNotice", errorMessage(errors.find((error) => error.status === 401 || error.status === 403)), true); }
    else if (results.slice(1).some((result) => result.status === "fulfilled")) { text("sidebarSession", "Session verified"); notice("sessionNotice", "Session verified. Stored only in this browser tab."); }
    else { text("sidebarSession", "Verification pending"); notice("sessionNotice", "Session verification not confirmed.", true); }
    if (errors.length) { text("globalNotice", errorMessage(errors[0])); $("globalNotice").hidden = false; }
  }
  $("refreshWorkspace").onclick = refreshWorkspace;
  function resetPrivateView() {
    state.epoch += 1; state.refreshVersion += 1; state.services = []; state.bindings = []; state.missionId = ""; state.pendingMission = ""; state.pendingRequest = null; state.retryPending = false;
    state.chatBusy = false; state.missionBusy = false; state.wakeBusy = false; state.wakeNeedsReadback = false;
    ["serviceCount", "sourceCount", "gapCount"].forEach((id) => text(id, "—"));
    ["serviceSearch", "connectionSearch", "chatIntent", "objective", "lookupMission"].forEach((id) => { $(id).value = ""; });
    $("initialState").value = '{"state":"OPEN"}'; $("targetState").value = '{"state":"DONE"}';
    $("serviceFilter").value = "all"; $("connectionFilter").value = "all";
    $("chatLog").querySelectorAll(".msg").forEach((item) => item.remove()); $("chatEmpty").hidden = false;
    ["chatNotice", "missionNotice", "missionStatus", "missionId", "missionSummary", "missionState", "wakeNotice"].forEach((id) => text(id, ""));
    $("missionCard").hidden = true; $("globalNotice").hidden = true;
    ["sendChat", "createMission", "wakeMission", "refreshMission", "loadMission", "refreshWorkspace"].forEach((id) => { $(id).disabled = false; });
    text("sendChat", "Send objective ↑"); text("createMission", "Create mission →"); text("wakeMission", "Request durable wake");
    text("serviceSummary", "Connect a session to read the source catalog."); text("connectionSummary", "Connect a session to read the capability registry.");
    renderServices(); renderConnections();
  }
  $("sessionForm").onsubmit = async (event) => {
    event.preventDefault(); const value = $("token").value.trim();
    if (!value) { notice("sessionNotice", "Enter an existing FUSE session token or clear this session.", true); return; }
    resetPrivateView(); state.token = value;
    try { sessionStorage.setItem("fuseSession", value); } catch (_) { /* Session remains in memory. */ }
    notice("sessionNotice", "Verifying your session…"); text("sidebarSession", "Verifying…"); await refreshWorkspace();
  };
  $("clearToken").onclick = () => {
    state.token = ""; try { sessionStorage.removeItem("fuseSession"); } catch (_) { /* No persisted session can be accessed. */ }
    $("token").value = ""; resetPrivateView(); text("sidebarSession", "Not connected"); notice("sessionNotice", "Session and displayed private data cleared from this tab. In-flight server work is not cancelled.");
  };
  document.querySelectorAll("[data-prompt]").forEach((button) => { button.onclick = () => { $("chatIntent").value = button.dataset.prompt; $("chatIntent").focus(); }; });
  function chatMessage(kind, message, proof = "") {
    $("chatEmpty").hidden = true;
    const card = node("article", "msg " + kind); card.append(node("div", "message-label", kind === "user" ? "YOU" : kind === "error" ? "REQUEST UPDATE" : "FUSE"), node("div", "message-body", message));
    if (proof) card.append(node("div", "message-proof", proof));
    $("chatLog").append(card); $("chatLog").scrollTop = $("chatLog").scrollHeight; return card;
  }
  $("chatForm").onsubmit = async (event) => {
    event.preventDefault(); if (state.chatBusy) return;
    const intent = $("chatIntent").value.trim(); if (!intent) return;
    if (!state.token) { notice("chatNotice", "Connect your session to send this objective.", true); $("sessionPanel").hidden = false; $("token").focus(); return; }
    const epoch = state.epoch; state.chatBusy = true; $("sendChat").disabled = true; text("sendChat", "Working…"); notice("chatNotice", "Waiting for the FUSE gateway. Your draft remains here until a response arrives.");
    const userCard = chatMessage("user", intent);
    try {
      const result = await api("/v1/chat", {method: "POST", headers: headers(true), body: JSON.stringify({intent, mode: $("chatMode").value})});
      if (epoch !== state.epoch) return;
      const proof = [result.provider, result.model, result.status, result.trace_id].filter(Boolean).join(" · ");
      chatMessage("fuse", result.text || "The runtime returned no answer text. Inspect the request status before continuing.", proof);
      if ($("chatIntent").value.trim() === intent) $("chatIntent").value = "";
      notice("chatNotice", "Response received from the existing gateway.");
    } catch (error) {
      if (epoch !== state.epoch) return;
      userCard.dataset.unconfirmed = "true";
      notice("chatNotice", errorMessage(error) + " Your draft has been retained.", true);
    } finally { if (epoch === state.epoch) { state.chatBusy = false; $("sendChat").disabled = false; text("sendChat", "Send objective ↑"); } }
  };
  function renderMission(result) {
    const missionId = result.mission_id || result.client?.mission_id;
    if (!missionId) { const error = new Error(); error.code = "INVALID_JSON"; throw error; }
    state.missionId = missionId;
    if (!state.pendingMission || state.pendingMission === missionId) { state.pendingMission = ""; state.pendingRequest = null; state.retryPending = false; }
    $("lookupMission").value = missionId;
    text("missionId", missionId); text("missionState", human(result.client?.state || result.mission_state?.state || result.state || "Readback received"));
    text("missionSummary", result.client?.last_reason ? human(result.client.last_reason) : "Mission state read from SOL. Completion depends on its required proofs and transitions.");
    text("missionStatus", JSON.stringify(result, null, 2)); $("missionCard").hidden = false;
  }
  async function readMission(id, epoch) { const result = await api("/v1/missions/" + encodeURIComponent(id), {headers: headers()}); if (epoch === state.epoch) { renderMission(result); state.wakeNeedsReadback = false; $("wakeMission").disabled = false; } return result; }
  function stateObject(id) { const value = JSON.parse($(id).value); if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("State must be a JSON object."); return value; }
  $("missionForm").onsubmit = async (event) => {
    event.preventDefault(); if (state.missionBusy) return;
    const objective = $("objective").value.trim(); if (!objective) return;
    let requestHeaders; let initial; let target;
    try { requestHeaders = headers(true); initial = stateObject("initialState"); target = stateObject("targetState"); }
    catch (error) { notice("missionNotice", error.code ? errorMessage(error) : "Initial and target states must each be valid JSON objects.", true); return; }
    const epoch = state.epoch; state.missionBusy = true; $("createMission").disabled = true; text("createMission", "Working…");
    try {
      if (state.pendingMission && !state.retryPending) {
        try {
          await readMission(state.pendingMission, epoch);
          if (epoch === state.epoch) notice("missionNotice", "Previous mission request found and read back. No duplicate mission was created.");
        } catch (error) {
          if (epoch !== state.epoch) return;
          if (error.status === 404) {
            state.retryPending = true;
            notice("missionNotice", "This mission is not present in the latest readback. You can retry registration with the same ID and original objective; no new mission ID will be created.", true);
          } else throw error;
        }
        return;
      }
      if (!state.pendingMission) {
        const missionId = "sol62-" + crypto.randomUUID().replace(/-/g, "");
        state.pendingMission = missionId; $("lookupMission").value = missionId;
        state.pendingRequest = {mission_id: missionId, objective, initial_state: initial, target_state: target};
      }
      state.retryPending = false;
      const result = await api("/v1/missions", {method: "POST", headers: requestHeaders, body: JSON.stringify(state.pendingRequest)});
      if (epoch !== state.epoch) return;
      renderMission(result); notice("missionNotice", "Mission registered. Add required execution bindings through the existing runtime before requesting work.");
    } catch (error) {
      if (epoch !== state.epoch) return;
      if ([400, 401, 403, 422].includes(error.status)) { state.pendingMission = ""; state.pendingRequest = null; state.retryPending = false; }
      notice("missionNotice", errorMessage(error) + (state.pendingMission ? " The mission ID is retained above; the next submit checks that request instead of repeating it." : ""), true);
    } finally { if (epoch === state.epoch) { state.missionBusy = false; $("createMission").disabled = false; text("createMission", state.retryPending ? "Retry same mission ID" : state.pendingMission ? "Check pending mission" : "Create mission →"); } }
  };
  $("lookupForm").onsubmit = async (event) => {
    event.preventDefault(); const id = $("lookupMission").value.trim(); if (!id || $("loadMission").disabled) return;
    const epoch = state.epoch; $("loadMission").disabled = true;
    try { await readMission(id, epoch); if (epoch === state.epoch) notice("missionNotice", "Mission readback received."); }
    catch (error) { if (epoch === state.epoch) notice("missionNotice", errorMessage(error), true); }
    finally { if (epoch === state.epoch) $("loadMission").disabled = false; }
  };
  $("refreshMission").onclick = async () => {
    if (!state.missionId || $("refreshMission").disabled) return; const epoch = state.epoch; $("refreshMission").disabled = true;
    try { await readMission(state.missionId, epoch); if (epoch === state.epoch) notice("wakeNotice", "Mission state refreshed."); }
    catch (error) { if (epoch === state.epoch) notice("wakeNotice", errorMessage(error), true); }
    finally { if (epoch === state.epoch) $("refreshMission").disabled = false; }
  };
  $("wakeMission").onclick = async () => {
    if (!state.missionId || state.wakeBusy || state.wakeNeedsReadback) return; const requestedMission = state.missionId; const epoch = state.epoch; state.wakeBusy = true; $("wakeMission").disabled = true; text("wakeMission", "Requesting…");
    try {
      const result = await api("/v1/missions/" + encodeURIComponent(requestedMission) + "/wake", {method: "POST", headers: headers(true), body: JSON.stringify({inline: false})});
      if (epoch !== state.epoch) return;
      if (state.missionId !== requestedMission) return;
      text("missionStatus", JSON.stringify(result, null, 2));
      notice("wakeNotice", "Wake response received: " + human(result.status || result.state || "acknowledged") + ". Refresh state to inspect progress; this is not completion proof.");
    } catch (error) { if (epoch === state.epoch && state.missionId === requestedMission) { state.wakeNeedsReadback = true; notice("wakeNotice", errorMessage(error) + " Refresh mission state before another wake request.", true); } }
    finally { if (epoch === state.epoch) { state.wakeBusy = false; $("wakeMission").disabled = state.wakeNeedsReadback; text("wakeMission", state.wakeNeedsReadback ? "Readback required" : "Request durable wake"); } }
  };
  showView(location.hash.slice(1)); renderServices(); renderConnections(); refreshWorkspace();
})();
