"""EvidenceOps v8.1 ProofLoop living-matter runtime."""

from .proofloop import (
    AuthorityDecision,
    AuthorityGateway,
    MatterTwin,
    ProofContractError,
    ValueLedger,
    compile_proof_contract,
    run_bounded_cycle,
    verify_release_state,
)

__all__ = [
    "AuthorityDecision",
    "AuthorityGateway",
    "MatterTwin",
    "ProofContractError",
    "ValueLedger",
    "compile_proof_contract",
    "run_bounded_cycle",
    "verify_release_state",
]

__version__ = "8.1.0"
