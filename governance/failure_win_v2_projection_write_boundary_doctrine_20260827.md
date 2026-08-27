# Failure-Win v2 projection/source boundary

Observed failure: a direct Google Sheets write into `Failure-Win Receiver Manifest v2!E6:L6` blocked the row-2 MAP/XLOOKUP spill and caused `#REF!` across the derived manifest.

Recovery: clear only the blocking user-entered values, preserve `Failure-Win Events v2`, and allow the manifest formulas to re-project the latest events. Provider readback confirmed the spill recovered without source-event loss.

Durable rule:

- behavior/currentness facts are appended to `Failure-Win Events v2`;
- `Failure-Win Receiver Manifest v2!E:M` is formula-owned derived state and is never directly written;
- manifest registry `A:D` is receiver-registry-manager owned;
- manifest snapshot metadata `O:P` is compiler owned;
- receiver aliases have their own manager;
- a write whose surface, role, or range does not match these contracts fails closed before provider mutation.

This rule prevents recurrence of the observed projection failure at source-policy level. It does not imply that every external client has already been bound to this source guard.
