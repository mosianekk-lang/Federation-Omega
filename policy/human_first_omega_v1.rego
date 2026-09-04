package federation.human_first_omega

default allow := false

default human_required := false

default suppress_interrupt := false

human_required if {
  input.action.external_effect == true
}

human_required if {
  input.action.irreversible == true
}

human_required if {
  input.action.material_objective_change == true
}

human_required if {
  input.action.owner_only_fact_or_value_judgment == true
}

human_required if {
  input.action.privacy_envelope_expansion == true
}

human_required if {
  input.action.consequential == true
}

human_required if {
  input.action.teach_back_required == true
}

human_required if {
  input.action.authority_rank > input.contract.authority_ceiling_rank
}

human_required if {
  input.action.expected_owner_minutes > input.contract.cognitive_budget_minutes
}

human_required if {
  input.action.external_effect == true
  input.action.readback_plan_present != true
}

allow if {
  input.contract.mission_id != ""
  input.contract.owner != ""
  input.contract.intent != ""
  count(input.contract.success_conditions) > 0
  human_required == false
}

suppress_interrupt if {
  allow == true
  input.action.requested_owner_interrupt == true
}

# Human-First does not itself authorize external effects. Any proposal that
# requires human judgment is held for the existing owner/SOVARA authority path.
