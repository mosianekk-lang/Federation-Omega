# Project memory — BCO-Prime Chat Forensics v2

## Current checkpoint

V2.0.0 is implemented, locally tested and ready. It preserves v1 files and the
100-function core. It adds a v1.1 truth repair and a 134-identifier unified
registry.

## Hash-bound implementation

| Artifact | SHA-256 |
|---|---|
| canonical core v1 | 58cb8a59caf63cee9ba4dc3e07de732bbd2f727c2ccd8c7fb961a919406b6cf9 |
| chat forensics v1 | 067950e2fc4436992875e3514404b680bc68636e1342bb51b0832e0d1575fad9 |
| meta-executive v1 source | 0f04e5a1e08159325563432695ce3c6d1faec294324c45df327b831f9fdb1902 |
| chat forensics v2 implementation | 6865ab5906181cd0e5d2443398b3f3f6a696fab7e35ab0bd939bed927d2c136e |
| v2 machine contract | f517ff53a19e0f1653581d26ab4c5fbc364725cf9bec826a9b4a37b69147aa77 |
| core v1 tests with truthful safe-manifest binding | b88a22390d3147d4a216770762fc7a8a54aff8ac57ba9643d150f719bd7026dd |
| v2 tests | 2b7ebf9a38267c1ae52ac34bbc507097ea4d94bacd4e7aeb03ef8ac53a4e4f66 |
| CFF v2 engine | e56e002e7e0c5e95cc0b5cc13279f12da6e45fd8eb137156f5f661f0cf67e016 |
| restored CFF v1 dependency | 6226812cbf69335cfb74e3be244d107202eb065019321767411cdb951f1bbe7b |

The CFF engine and restored dependency hashes are runtime allowlist values. The
remaining hashes are release integrity references and must be recomputed after
any code, test or contract change.

## Test checkpoint

- syntax compilation: pass;
- selected legacy tests: 12/12;
- v2 tests: 15/15;
- selected combined total: 27/27;
- repository-wide total: 36/36;
- canonical registry sweep: 100/100;
- native CFF output contract: 7/7;
- ledger chain: valid;
- ChatBridge 1.1: valid;
- deterministic v2 incident replay: pass.

## Known boundary

bco_prime_meta_executive_v1.py imports three modules absent from the harvested
snapshot:

- federation_autopilot_metacognition_v1;
- bubbles.chat_governor_omega3.continuity; and
- formation_omega.reconciliation_fabric_v2.

V2 preserves the exact source algorithm for rank_strategies and the capability
manifest in an A1 shadow-only subset. It must not claim the full meta decision
compiler is ready.

## Next eligible engineering route

Add a v2 flight-recorder envelope around registry receipts: append-only local
JSONL, correlation/parent IDs, latency, failure taxonomy, replay fixtures and
drift detectors. This requires a new owner-authorized build cycle. It does not
require deployment authority.
