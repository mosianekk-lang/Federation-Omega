# FACPF Edge extension source

This directory builds an unsigned, unpacked Manifest V3 diagnostic package.
The manifest has no automatic content script, mandatory host permission,
`tabs`, `debugger`, native-messaging, cookie, history or network permission.
The only mandatory permission is managed storage. Scripting and the exact
`https://chatgpt.com/*` origin are optional.

The service worker fails closed unless managed configuration, the authorized
hook flag, Formation evidence, operator evidence, optional scripting access and
the exact optional host grant all pass. It never requests permissions itself.
There is no popup, external message surface, remote code or automatic attach.

`enterprise_deployment_contract.json` is deliberately inactive and contains
no extension ID, update URL, registry command, MDM assignment or force-install
policy. Microsoft documents that force-installed extensions are installed
silently and cannot be disabled by users, so this package cannot enter that
state without a separate identity, review, canary and execution permit.

Build and verify:

```bash
node autonomic_chat_performance_fabric/edge_extension/test_edge_extension.js
node autonomic_chat_performance_fabric/edge_extension/permission_audit.js
node autonomic_chat_performance_fabric/edge_extension/build_edge_extension.js /tmp/facpf-edge-extension
```

Building proves source assembly only. It does not prove signing, installation,
policy assignment, browser execution, ChatGPT instrumentation or performance.
