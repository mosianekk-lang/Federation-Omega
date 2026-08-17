# ChatBridge Companion Ω4.9 enterprise deployment handoff

Status: `PREPARED / NOT SUBMITTED / NOT APPROVED / NOT DEPLOYED`.

This handoff supports lawful deployment of the reviewed ChatBridge Companion v0.3.0 on a managed Windows browser. It is not a request to weaken security policy, grant administrator rights to the end user, bypass enterprise extension governance or claim that installation has already occurred.

## Requested outcome

Allow or centrally deploy one reviewed Manifest V3 extension that captures the rendered ChatGPT conversation into an extension-local, append-only SHA-256 ledger and prepares ordered successor-chat replay packets for ChatBridge Ω4.9.

## Current security scope

- Browser permissions: `storage`, `unlimitedStorage`, `downloads`.
- Host permission: `https://chatgpt.com/*` only.
- Network endpoints: none in the admitted browser source.
- Native messaging, Windows service, driver, scheduled task and registry writes: none.
- Credentials or API keys: none.
- Durable browser storage: governed local transcript ledger and minimum continuity metadata.
- Export: owner-initiated local JSON ledger download.
- Rollback: disable or remove the extension.

## Policy routes for the browser administrator

The administrator should select the organisation's normal extension-distribution route and review the package before assigning an extension ID.

1. Microsoft Edge Add-ons or Chrome Web Store private/organisational publication; or
2. an enterprise-managed installation source and update mechanism supported by the organisation; then
3. an exact extension-ID rule in `ExtensionSettings`, `ExtensionInstallAllowlist`, or the organisation's force-install policy.

Do not use a wildcard allow rule. Do not bypass `ExtensionDeveloperModeSettings`, `ExtensionInstallBlocklist`, `ExtensionInstallTypeBlocklist`, `BlockExternalExtensions`, or `DeveloperToolsAvailability`. The final extension ID and update URL remain `UNVERIFIED` until the administrator packages or publishes the reviewed source.

## Evidence required before operational promotion

1. Package/source hash recorded by the administrator.
2. Exact assigned extension ID and approved update source.
3. Effective-policy readback from the target browser.
4. Installation readback from the intended Edge/Chrome profile.
5. Signed-in ChatGPT binding confirmation.
6. Real rendered-message capture, terminal-warning checkpoint and ledger export readback.
7. Ordered successor-chat replay with independent semantic-conformance receipt.
8. No unresolved sequence, integrity or required-artifact gap.

Until those checks pass, keep the state at `TESTED_NOT_DEPLOYED`.
