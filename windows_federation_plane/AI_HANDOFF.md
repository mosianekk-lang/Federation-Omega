# AI Handoff

1. Read `README.md`, `THREAT_MODEL.md`, `FORMATION_SPEC.md`, `BUILD_CONTRACT.json` and `governance/fuse_windows_execution_plane_v1.json`.
2. Fresh-read signed main and the FDOF repository lock before source mutation.
3. Run both test suites and the build-contract validator.
4. Source-admit only the exact listed files through one FDOF-fenced branch/PR.
5. Read the Windows workflow job and artifact; verify the receipt hash and Windows runner fields.
6. Do not describe owner-PC installation unless an owner-workstation receipt exists.
7. Stop after hosted-plane proof unless a separately authorized provider effect is required.
# Secure MCP Tunnel handoff (2026-09-14)

The direct private route is implemented in `tunnel_service.py` and the four `*FuseWindowsTunnel.ps1` scripts. Do not call it deployed from source or local tests. Promotion requires a current `main`-based admitted source, a physical Windows run, `tunnel-client doctor`, task persistence, ChatGPT tool discovery, a hash-bound endpoint health receipt and rollback readback. A secret-safe Remote Desktop Commander preflight later reached `MosianeKK-LPT`: Python and the FUSE root were present; `tunnel-client`, Git, tunnel ID and scoped runtime-key handles were absent. No endpoint mutation was attempted.
