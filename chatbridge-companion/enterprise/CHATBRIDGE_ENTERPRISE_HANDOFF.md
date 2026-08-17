# ChatBridge enterprise deployment handoff

Status: `PREPARED / NOT SUBMITTED / NOT APPROVED / NOT DEPLOYED`.

This handoff supports lawful deployment of the existing ChatBridge Companion on a managed Windows browser. It is not a request to weaken security policy, install an unsigned unknown extension, or grant Windows administrator rights to the end user.

## Requested outcome

Allow or centrally deploy one reviewed Manifest V3 extension that adds **Start a new chat via ChatBridge** on `https://chatgpt.com/*` and performs a one-time, tab-bound transfer of a bounded continuity capsule.

## Security scope

- Browser permissions: `storage` only.
- Host permission: `https://chatgpt.com/*` only.
- Network endpoints: none.
- Native messaging, Windows service, driver, scheduled task and registry writes: none.
- Credentials or API keys: none.
- Full capsule storage: browser session storage only.
- Durable storage: transcript-free capsule metadata only.
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
6. All eight checks in `LIVE_CANARY.md` pass.

Until those checks pass, keep the state at `TESTED_NOT_DEPLOYED`.

