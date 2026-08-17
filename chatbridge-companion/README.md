# ChatBridge Companion for ChatGPT

Status: `IMPLEMENTED / DETERMINISTICALLY TESTED / NO-ADMIN READINESS PREPARED / READY FOR LIVE BROWSER CANARY / NOT DEPLOYED`.

This Manifest V3 browser companion augments ChatGPT's maximum-conversation-length notice with **Start a new chat via ChatBridge**. It prepares bounded checkpoints before the warning appears, preserves the current GPT/project route, opens a successor chat, and injects a source-bound ChatBridge restore capsule.

## Truthful continuity boundary

The extension carries complete actionable state plus verified-source instructions and a bounded rendered transcript. It does not claim an unlimited verbatim transfer, invisible access to messages absent from the rendered DOM, modification of OpenAI's servers, or removal of ChatGPT limits.

## Architecture

- `src/bridge-core.js`: deterministic warning recognition, URL routing, transcript bounding, capsule and restore-prompt generation.
- `src/content-script.js`: MutationObserver, pre-limit checkpoints, accessible ChatBridge action, successor-composer restoration.
- `src/background.js`: session-scoped full capsule, transcript-free local summary, tab-bound one-time transfer.
- `options/`: local controls for capsule size, thresholds, and auto-send.
- `tests/`: dependency-free Node tests.

The full capsule is held in `chrome.storage.session` and is cleared when the browser restarts or the extension reloads. Only a transcript-free summary is retained in `chrome.storage.local`. No third-party endpoint or OpenAI API key is used.

## Validate

```sh
npm run check
python3 /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py BUILD_CONTRACT.json
```

## Browser canary

Load the directory as an unpacked extension in Chrome/Edge, open a test ChatGPT conversation, and verify: warning detection, exact ChatBridge button label, source route preservation, one successor tab, capsule injection, one-time consumption, and the native fallback button. Installation is a browser trust-boundary action and is not represented as completed without browser-native readback.

The supplied 14 August 2026 screenshot was inspected at original resolution. Its exact warning text and `/g/<surface>/c/<conversation>` route match the deterministic detector and route-preservation tests. This is source-fixture verification, not a live installed-extension canary.

## Managed Windows and no-administrator route

The extension itself requires no Windows service, driver, native-messaging host, API key or system-wide installation. `tools/ChatBridge-Readiness.ps1` performs a read-only inspection of the existing user/machine Edge and Chrome policy registry paths, the available browser executables and this manifest. It never requests elevation, changes registry policy, bypasses PowerShell execution policy, loads an extension by command line or claims installation.

The assessor emits one of three bounded routes:

- `USER_PROFILE_SIDELOAD_NOT_EXPLICITLY_BLOCKED`: no inspected policy explicitly blocks the candidate route; browser-native installation and canary proof are still required.
- `IT_MANAGED_DEPLOYMENT_REQUIRED`: a managed policy signal requires an approved allowlist, store or enterprise deployment.
- `NO_SUPPORTED_BROWSER_FOUND` or `UNSUPPORTED_OS`: the inspected environment cannot run this readiness path.

Registry inspection is not a substitute for `edge://policy` or live browser readback. The prepared administrator-facing security and deployment scope is in `enterprise/CHATBRIDGE_ENTERPRISE_HANDOFF.md`.

## Rollback

Disable or remove the extension. It never edits ChatGPT account data, native chats, project instructions, or server configuration. Session transfer data disappears when the extension/browser session ends; local summary data disappears when the extension is removed.
