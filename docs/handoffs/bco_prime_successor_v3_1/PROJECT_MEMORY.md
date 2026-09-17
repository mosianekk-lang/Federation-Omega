# Project memory — BCO-Prime successor v3.1

## Checkpoint

V3.1 was built from a byte-verified extraction of the sealed v3.0 archive. The
first implementation adds four modules, nine routes and twelve failure-first
tests. An independent challenge exposed inherited flight append TOCTOU,
camelCase/punctuation effect-key escape and scalar coercion gaps; the isolated
v3.1 copy repairs them while the sealed v3.0 archive remains unchanged.

The first exhaustive run exposed a verifier fixture with a 31-byte signing
seed. The runtime correctly rejected it. The fixture now injects the required
exact 32 bytes, preserving fail-closed signer authority.

Current local proof: 67/67 repository tests and the standalone verifier pass.
The verifier covers 100 core, 24 legacy, two v2 meta, eight expected-blocked
engine, fourteen v3 and nine v3.1 operations. Its receipt is
`e91c8ca784e5e3853aa89de4d764733ae98bf6e3c044e771e2a82df9e433e94e`.

## Resume order

1. `README.md`
2. `BUILD_CONTRACT.json`
3. `docs/architecture/BCO_PRIME_SUCCESSOR_V3_1.md`
4. `benchmarking/cfbe_omega/BCO_PRIME_SUCCESSOR_V3_1.json`
5. `governance/BCO_PRIME_BASELINE_REGISTRY_V3_1.json`
6. `proof/bco_prime_successor_v3_1/RELEASE_PROOF.json`

Revalidate the baseline with the signer fingerprint in the external release
receipt, validate every source and archive-member hash, run all tests and the
standalone verifier, then confirm MODISA and RealityGuard.

## Truth boundary

The system is local and on demand. Baseline auto-advance, quarantine auto-clear,
source rewriting, network/provider effect, deployment, registration and stable
promotion remain false. The release package and receipt do not create runtime
authority.
