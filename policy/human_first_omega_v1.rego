package federation.human_first_omega

default allow := false

default human_required := false

default suppress_interrupt := false

default external_effect_authorized := false

external_effect_authorized if {
  input.action.external_effect == true
  input.action.effect_class != ""
  input.action.effect_class != "NONE"
  input.action.authorization_ref != ""
  some i
  input.contract.authorized_external_effect_classes[i] == input.action.effect_class
  some j
  input.contract.authorization_refs[j] == input.action.authorization_ref
}

human_required if {
  input.action.external_effect == true
  not external_effect_authorized
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

# Human-First never self-mints provider authority. A reversible external effect
# may avoid a repeated owner interruption only when both its effect class and
# authorization reference are already present in the Human Mission Contract,
# the authority ceiling is sufficient, and an exact readback plan exists.
# Consequential, irreversible, privacy-expanding or objective-changing actions
# remain separately human-gated even if another effect class was authorized.
