(() => {
  const $ = (id) => document.getElementById(id);
  let token = sessionStorage.getItem("fuseSession") || "";
  $("token").value = token;
  let missionId = "";

  function headers(json = false) {
    const value = token.trim();
    if (!value) throw new Error("FUSE_SESSION_REQUIRED");
    const h = {"X-Fuse-Authorization": value.startsWith("Bearer ") ? value : "Bearer " + value};
    if (json) h["Content-Type"] = "application/json";
    return h;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, options);
    const text = await response.text();
    let body = {};
    try { body = text ? JSON.parse(text) : {}; } catch (_) { body = {raw: text}; }
    if (!response.ok) throw new Error((body.detail && body.detail.reason) || body.reason || ("HTTP_" + response.status));
    return body;
  }

  async function health() {
    try {
      const h = await api("/health");
      $("health").textContent = h.ok ? "SOL runtime online" : "runtime held";
      $("health").dataset.ok = h.ok ? "1" : "0";
    } catch (error) {
      $("health").textContent = "runtime unavailable";
    }
  }

  $("saveToken").onclick = () => {
    token = $("token").value.trim();
    sessionStorage.setItem("fuseSession", token);
    $("saveToken").textContent = "Session bound";
  };

  document.querySelectorAll(".tab").forEach((button) => {
    button.onclick = () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => {
        if (p.id === "chatPanel" || p.id === "missionPanel") p.classList.add("hidden");
      });
      button.classList.add("active");
      $(button.dataset.target).classList.remove("hidden");
    };
  });

  $("sendChat").onclick = async () => {
    const intent = $("chatIntent").value.trim();
    if (!intent) return;
    const log = $("chatLog");
    const user = document.createElement("div");
    user.className = "msg user";
    user.textContent = intent;
    log.appendChild(user);
    $("chatIntent").value = "";
    try {
      const result = await api("/v1/chat", {
        method: "POST",
        headers: headers(true),
        body: JSON.stringify({intent, mode: $("chatMode").value})
      });
      const assistant = document.createElement("div");
      assistant.className = "msg fuse";
      assistant.textContent = result.text || "";
      log.appendChild(assistant);
    } catch (error) {
      const fail = document.createElement("div");
      fail.className = "msg error";
      fail.textContent = String(error.message || error);
      log.appendChild(fail);
    }
    log.scrollTop = log.scrollHeight;
  };

  $("createMission").onclick = async () => {
    try {
      const result = await api("/v1/missions", {
        method: "POST",
        headers: headers(true),
        body: JSON.stringify({
          objective: $("objective").value.trim(),
          initial_state: JSON.parse($("initialState").value),
          target_state: JSON.parse($("targetState").value)
        })
      });
      missionId = result.mission_id || (result.client && result.client.mission_id) || "";
      $("missionId").textContent = missionId;
      $("missionStatus").textContent = JSON.stringify(result, null, 2);
      $("missionCard").classList.remove("hidden");
    } catch (error) {
      $("missionStatus").textContent = String(error.message || error);
      $("missionCard").classList.remove("hidden");
    }
  };

  $("wakeMission").onclick = async () => {
    if (!missionId) return;
    try {
      const result = await api("/v1/missions/" + encodeURIComponent(missionId) + "/wake", {
        method: "POST",
        headers: headers(true),
        body: JSON.stringify({inline: false})
      });
      $("missionStatus").textContent = JSON.stringify(result, null, 2);
    } catch (error) {
      $("missionStatus").textContent = String(error.message || error);
    }
  };

  health();
})();
