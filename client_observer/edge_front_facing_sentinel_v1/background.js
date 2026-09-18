const ENDPOINT = "http://127.0.0.1:8765/v1/front-facing-status";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.kind !== "FUSE_FRONT_FACING_STATUS_V1") {
    return false;
  }

  fetch(ENDPOINT, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(message.snapshot),
    cache: "no-store",
  })
    .then(async (response) => {
      const body = await response.json().catch(() => ({}));
      sendResponse({
        ok: response.ok,
        status: response.status,
        body,
      });
    })
    .catch((error) => {
      sendResponse({
        ok: false,
        status: 0,
        body: {
          error: "LOCAL_FUSE_HOST_UNREACHABLE",
          detail: String(error && error.message ? error.message : error),
        },
      });
    });

  return true;
});
