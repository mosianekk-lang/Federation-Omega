# Authenticated Apps Script activation

Run this from a terminal where Google sign-in can complete:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mosianekk-lang/Federation-Omega/main/ops/clasp_authenticated_activate.sh)
```

The launcher installs `clasp` when absent, requires an authenticated `clasp` session, clones the canonical repository, tries the primary Apps Script project, fails over to the secondary project, pushes the recovery source and manifest, invokes `installSentinelProcessor`, and emits a completion receipt.

Success is not established until both are present:

- `FEDOMEGA-GAS-ACTIVATION-VERIFIED`
- a fresh row in the `Heartbeat` sheet for the active script ID

When authentication is absent, run `clasp login` in the same terminal and rerun the launcher. Do not paste OAuth codes or credentials into chat.
