"use strict";

importScripts("protocol.js");
const protocol = globalThis.SovaraBefEdgeProtocol;

chrome.runtime.onMessageExternal.addListener((request, sender, sendResponse) => {
  handleExternal(request, sender).then(sendResponse).catch((error) => {
    sendResponse({schema: protocol.ACK_SCHEMA, ok: false, state: "EDGE_AGENT_EXCEPTION", error: String(error && error.message || error)});
  });
  return true;
});

async function handleExternal(request, sender) {
  if (!sender || sender.id !== protocol.CHATBRIDGE_EXTENSION_ID) {
    return {schema: protocol.ACK_SCHEMA, ok: false, state: "SENDER_EXTENSION_REJECTED"};
  }
  if (!request || request.type !== "CHATBRIDGE_PROVENANCE_DELTA") {
    return {schema: protocol.ACK_SCHEMA, ok: false, state: "MESSAGE_TYPE_REJECTED"};
  }
  const envelope = request.envelope;
  const validation = await protocol.validateEnvelope(envelope);
  if (!validation.ok) {
    return {schema: protocol.ACK_SCHEMA, ok: false, state: validation.error || "ENVELOPE_REJECTED"};
  }
  try {
    const nativeAck = await chrome.runtime.sendNativeMessage(protocol.NATIVE_HOST_NAME, envelope);
    return protocol.normalizeNativeAck(nativeAck, envelope);
  } catch (error) {
    return {
      schema: protocol.ACK_SCHEMA,
      ok: false,
      state: "NATIVE_HOST_UNAVAILABLE",
      error: String(error && error.message || error)
    };
  }
}
