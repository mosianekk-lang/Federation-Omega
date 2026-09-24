from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "clients" / "sol62_browser_companion"


class Sol62BrowserCompanionSourceContractTests(unittest.TestCase):
    def test_manifest_is_fuse_owned_scoped_controller_not_arbitrary_script_injector(self):
        manifest = json.loads((COMPANION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("https://chatgpt.com/*", manifest["host_permissions"])
        self.assertIn("tabs", manifest["permissions"])
        self.assertNotIn("scripting", manifest["permissions"])

    def test_exact_chat_load_failure_maps_to_route_local_failure_code(self):
        content = (COMPANION / "content.js").read_text(encoding="utf-8")
        self.assertIn("Could not load this ChatGPT conversation", content)
        self.assertIn("CHATGPT_CONVERSATION_LOAD_FAILED", content)
        self.assertNotIn("Retry", content)

    def test_stream_cache_expiry_is_detected_without_autonomous_ui_retry(self):
        content = (COMPANION / "content.js").read_text(encoding="utf-8")
        self.assertIn("Stream cache expired", content)
        self.assertIn("STREAM_CACHE_EXPIRED", content)
        self.assertIn("Connection interrupted. Waiting for the complete answer", content)
        self.assertIn("CHATGPT_STREAM_INTERRUPTED", content)
        self.assertNotIn("Retry", content)

    def test_stream_failure_can_enqueue_durable_sol_wake(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        self.assertIn("enqueueDurableWake", worker)
        self.assertIn('"/wake"', worker)
        self.assertIn("AUTO_DURABLE_MISSION_WAKE", worker)
        self.assertIn("STREAM_CACHE_FAILURE_RECOVERY", worker)
        self.assertIn("durableWakeTaskId", worker)
        self.assertIn("ownerRetryRequired", worker)
        self.assertIn("uiRetryRequired", worker)

    def test_companion_never_embeds_provider_or_fuse_credentials(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        manifest = (COMPANION / "manifest.json").read_text(encoding="utf-8")
        combined = worker + manifest
        self.assertNotIn("OPENAI_API_KEY", combined)
        self.assertNotIn("sk-", combined)
        self.assertIn("chrome.storage.session", worker)
        self.assertIn("NO_FUSE_SESSION", worker)

    def test_companion_durably_queues_before_transport(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        enqueue_index = worker.index("await enqueueCarrierEvent(event)")
        flush_index = worker.index("await flushOutbox()", enqueue_index)
        self.assertGreaterEqual(enqueue_index, 0)
        self.assertGreater(flush_index, enqueue_index)
        self.assertIn("pendingCarrierEvents", worker)
        self.assertIn("event_id", worker)
        self.assertIn("IDEMPOTENT_REPLAY", worker)

    def test_persistent_outbox_does_not_store_access_token(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        self.assertIn("chrome.storage.session", worker)
        self.assertNotIn('chrome.storage.local.set({ fuseAccessToken', worker)
        self.assertIn("providerCredentialsIncluded: false", worker)

    def test_relay_failure_never_asserts_mission_failure(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        readme = (COMPANION / "README.md").read_text(encoding="utf-8")
        self.assertIn("Do not turn a relay failure into a mission-state assertion", worker)
        self.assertIn("preserve mission identity/state", readme)
        self.assertIn("READBACK FIRST", readme)

    def test_failover_hydration_receipt_is_checkpoint_bound_and_redacted(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        for marker in (
            "pendingMissionHydration",
            "durabilityCheckpointSha256",
            "replayGuardVerified",
            "eventHistoryHead",
            "inflightEffectIds",
            "providerCredentialsIncluded: false",
            "transcriptIncluded: false",
            "SOL62_GET_PENDING_HYDRATION",
            "SOL62_ACK_PENDING_HYDRATION",
            "HYDRATION_CHECKPOINT_MISMATCH",
        ):
            self.assertIn(marker, worker)
        self.assertNotIn("fuseAccessToken: receipt", worker)

    def test_new_chat_tab_resilience_is_semantic_and_persistent(self):
        manifest = json.loads((COMPANION / "manifest.json").read_text(encoding="utf-8"))
        content = (COMPANION / "content.js").read_text(encoding="utf-8")
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        self.assertIn("contextMenus", manifest["permissions"])
        self.assertIn("semanticNewChatTarget", content)
        self.assertIn('document.addEventListener("contextmenu"', content)
        self.assertIn('document.addEventListener("auxclick"', content)
        self.assertIn("event.ctrlKey || event.metaKey", content)
        self.assertIn("result.nativeLink", content)
        self.assertIn("FUSE — Open New Chat in New Tab", worker)
        self.assertIn("chrome.contextMenus.onClicked", worker)
        self.assertIn("chrome.tabs.create", worker)
        self.assertIn("NEW_CHAT_DEDUP_MS", worker)
        self.assertIn("safeChatGptNewChatUrl", worker)

    def test_semantic_snapshot_uses_accessibility_and_stable_identity(self):
        content = (COMPANION / "content.js").read_text(encoding="utf-8")
        self.assertIn("semanticSnapshot", content)
        self.assertIn("accessibleName", content)
        self.assertIn("stable_id", content)
        self.assertIn("SEMANTIC_TARGET_AMBIGUOUS", content)
        self.assertIn("querySelectorAll", content)

    def test_browser_command_executor_supports_bounded_tab_and_history_controls(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        for marker in (
            "LIST_TABS",
            "CREATE_TAB",
            "ACTIVATE_TAB",
            "CLOSE_TAB",
            "RELOAD_TAB",
            "GO_BACK",
            "GO_FORWARD",
            "NAVIGATE_CHATGPT",
            "SEMANTIC_SNAPSHOT",
        ):
            self.assertIn(marker, worker)
        self.assertIn("safeChatGptTab", worker)
        self.assertIn("safeChatGptNewChatUrl", worker)
        self.assertIn("action_observed", worker)

    def test_website_state_command_requires_runtime_authority_preflight(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        content = (COMPANION / "content.js").read_text(encoding="utf-8")
        self.assertIn("/authorize", worker)
        self.assertIn("authority_bound", worker)
        self.assertIn('command.effect_class !== "WEBSITE_STATE"', worker)
        self.assertIn("command.authority_bound !== true", content)

    def test_new_chat_opening_and_semantic_control_are_origin_bounded(self):
        content = (COMPANION / "content.js").read_text(encoding="utf-8")
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        self.assertIn('url.hostname !== "chatgpt.com"', content)
        self.assertIn('url.hostname !== "chatgpt.com"', worker)
        self.assertIn('url.protocol !== "https:"', worker)
        self.assertNotIn("eval(", content)
        self.assertNotIn("new Function", content)
        self.assertIn("WEBSITE_STATE_AUTHORITY_NOT_BOUND", content)


if __name__ == "__main__":
    unittest.main()
