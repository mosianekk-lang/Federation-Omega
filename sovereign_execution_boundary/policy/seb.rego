package seb

default allow := false

allow if {
  input.objective_signature_valid == true
  input.objective_fingerprint == input.canonical_objective_fingerprint
  input.authority_class in {"A0", "A1", "A2"}
  not input.prohibited_effect
}
