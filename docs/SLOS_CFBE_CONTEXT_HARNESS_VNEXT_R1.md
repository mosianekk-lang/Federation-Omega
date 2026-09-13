# SLOS CFBE Context + Harness vNext R1

Status: SOURCE CANDIDATE / REPOSITORY CI OPEN
Date: 2026-09-13

R1 adds competitive context selection and complete-harness comparison while reusing the existing SLOS engineering runtime and Frontier Convergence value-selection machinery.

Source additions:
- superior_logic/context_tournament.py
- superior_logic/harness_tournament.py

Test additions:
- tests/test_slos_context_tournament_vnext.py
- tests/test_slos_harness_tournament_vnext.py

Context Tournament selects provenance-aware context under a hard token budget and refuses an efficiency gain that reduces accepted-task rate, verified readback, or regression quality.

Harness Tournament treats model, agent-computer interface, context policy, skills, tools, workspace policy, fleet shape, and verifier profile as one engineering harness. Exact experiment identity is delegated to the existing Frontier Convergence ExperimentIdentityCompiler. Measured outcomes are converted to existing ValueReceipt records and selection is delegated to the existing FinOpsParetoRouter.

No second provider router, execution authority, proof authority, or 10x court is created. Existing TenXEngineeringCourt remains authoritative for any 10x claim.

This source wave does not prove runtime superiority, market superiority, provider performance, stable SLOS promotion, or 10x value. Required next gates are repository CI, Airlock/ProofOS/Leak Guard, shadow real missions, matched harness comparison, and paired empirical value.
