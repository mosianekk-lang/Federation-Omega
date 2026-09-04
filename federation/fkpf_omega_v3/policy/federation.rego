package federation.fkpf_omega_v3

# Default deny: the model/executor never creates authority by assertion.
default allow := false

proof_rank := {
  "DESCRIBED": 0,
  "BUILT": 1,
  "TESTED": 2,
  "SOURCE_ADMITTED": 3,
  "PROVIDER_READBACK": 4,
  "BEHAVIOUR_VERIFIED": 5,
  "VALUE_OBSERVED": 6,
}

authority_rank := {
  "A0_OBSERVE": 0,
  "A1_INTERNAL": 1,
  "A2_PROVIDER_REVERSIBLE": 2,
  "A3_OWNER_RESERVED": 3,
}

effect_rank := {
  "NONE": 0,
  "INTERNAL_REVERSIBLE": 1,
  "PROVIDER_REVERSIBLE": 2,
  "CONSEQUENTIAL": 3,
}

allow if {
  input.kind == "knowledge_delta"
  d := input.delta
  r := input.receiver
  d.privacy in r.accepted_privacy
  proof_rank[d.proof] >= proof_rank[r.minimum_proof]
  authority_rank[d.authority] <= authority_rank[r.authority]
  effect_rank[d.effect] <= effect_rank[r.effect]
  matter_allowed(d, r)
}

matter_allowed(d, r) if {
  count(d.matter_scope) == 0
}

matter_allowed(d, r) if {
  count(r.matter_scopes) == 0
}

matter_allowed(d, r) if {
  some scope in d.matter_scope
  scope in r.matter_scopes
}

allow if {
  input.kind == "mission_effect"
  m := input.mission
  i := input.identity
  m.mission_id == i.mission_id
  authority_rank[m.authority] <= authority_rank[i.authority]
  effect_rank[m.effect] <= effect_rank[i.effect]
  m.effect != "CONSEQUENTIAL"
}

allow if {
  input.kind == "mission_effect"
  m := input.mission
  i := input.identity
  m.mission_id == i.mission_id
  m.effect == "CONSEQUENTIAL"
  input.owner_approval == true
  input.provider_readback_required == true
  input.independent_verification_required == true
}

# Legal/evidence contamination firewall.
deny_reason contains "LEGAL_FACT_CANNOT_ORIGINATE_FROM_SYSTEM_DESIGN_DELTA" if {
  input.kind == "knowledge_delta"
  input.receiver.domain == "LEGAL_EVIDENCE"
  input.delta.discovery_type == "SYSTEM_DESIGN"
  input.delta.proof != "PROVIDER_READBACK"
}

deny_reason contains "RAW_SECRET_VALUE_FORBIDDEN" if {
  input.contains_raw_secret == true
}

deny_reason contains "MATTER_WALL" if {
  input.kind == "knowledge_delta"
  d := input.delta
  r := input.receiver
  count(d.matter_scope) > 0
  count(r.matter_scopes) > 0
  not matter_allowed(d, r)
}
