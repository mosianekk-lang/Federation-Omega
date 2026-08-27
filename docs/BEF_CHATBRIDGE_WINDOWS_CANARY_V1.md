# BEF / ChatBridge Windows Runtime Canary v1

## Objective

Move the now-admitted BEF/ChatBridge native provenance courier from source admission to a reversible local Windows runtime canary without conflating installation, browser binding, live message delivery, DPF reconstruction or provider-native completeness.

## Runtime architecture

```text
ChatGPT rendered DOM
  -> ChatBridge Companion (fixed ID kacbginamagliaddmlkffhcadpamomjb)
  -> exact cross-extension delta egress
  -> SOVARA BEF Edge Agent (fixed ID apokbhjjgiaceigelkedcelcecfmgnia)
  -> Chromium nativeMessaging
  -> com.sovara.bef_edge Windows native host
  -> current-user DPAPI encryption
  -> content-addressed local spool
  -> readback verifier / DPF observable-scope evidence
```

ChatBridge remains browser bounded and does not receive nativeMessaging permission. The BEF Edge Agent is the only native-messaging browser component.

## One-command bootstrap

`bef-edge-agent/runtime/bootstrap_windows_canary.ps1` performs the executable portion of the local canary in one governed sequence:

1. verify Windows and exact source files;
2. derive Chromium extension IDs from the committed manifest keys and fail on drift;
3. verify BEF accepts external messages only from the exact ChatBridge identity;
4. build the native host with the existing approved local Python/PyInstaller environment, or accept an explicit prebuilt host executable;
5. execute native-host self-test;
6. register `com.sovara.bef_edge` for the current Windows user and Edge only;
7. read back registry + native host manifest bindings;
8. prepare a dedicated reversible Edge canary profile;
9. launch Edge with exactly the ChatBridge and BEF unpacked extensions unless `-NoLaunch` is supplied;
10. attempt profile-preferences readback for both fixed extension identities;
11. write a local hashable bootstrap receipt under `%LOCALAPPDATA%\SOVARA\BEF\runtime-receipts`.

The bootstrap does not download PyInstaller or any other dependency. Missing approved build tooling fails closed rather than silently fetching code.

## Progressive runtime proof

`verify_windows_canary.ps1` exposes only the highest state actually observed:

```text
RUNTIME_NOT_BOUND
  -> NATIVE_HOST_REGISTERED_VERIFIED
  -> BROWSER_PROFILE_BINDING_VERIFIED
  -> LIVE_ENCRYPTED_SPOOL_RECEIPT_OBSERVED
```

A spool receipt proves a rendered-DOM browser-to-native encrypted courier event. It does not prove provider-native hidden events, DPF semantic reconstruction, successor-chat restore or provider execution.

## Reversible rollback

`rollback_windows_canary.ps1`:

- removes only the current-user Edge native-host registration;
- stops only Edge processes whose command line is bound to the dedicated canary profile;
- removes the canary profile only when explicitly requested;
- removes native-host files only when explicitly requested;
- preserves the encrypted evidence spool by default.

## Remaining live gates

Source admission and bootstrap source do not prove a successful run on the owner workstation. Promotion requires fresh local receipts for:

1. native host executable build/self-test;
2. registry and manifest readback;
3. both extension identities present in the canary Edge profile;
4. live cross-extension + native-messaging delivery;
5. DPAPI spool receipt;
6. DPF observable-scope reconciliation and deterministic rendered-transcript reconstruction;
7. rollback drill;
8. repeat/soak evidence.

ChatGPT authentication in a new dedicated browser profile is a user/provider authentication boundary and is not manufactured by source code.
