package seb

default decision := {"allow": false, "reasons": ["policy_evaluation_failed"]}

authority_rank := {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4, "A5": 5}

reason contains "authority_exceeds_runtime" if {
  authority_rank[input.mission.authority_class] > authority_rank[input.runtime.max_authority]
}
reason contains "external_effects_disabled" if {
  input.request.external_effect == true
  input.runtime.allow_external_effects != true
}
reason contains "tool_not_allowed" if {
  input.request.tool != null
  not input.request.tool in input.mission.allowed_tools
}
reason contains "effect_explicitly_prohibited" if {
  input.request.tool != null
  input.request.tool in input.mission.prohibited_effects
}
reason contains "secret_data_external_route_denied" if {
  input.mission.data_class == "secret"
  input.request.tool == "openrouter"
}

decision := {"allow": count(reason) == 0, "reasons": sort([r | reason[r]])} if {
  input.mission.fingerprint != ""
  input.mission.authority_class in object.keys(authority_rank)
  input.runtime.max_authority in object.keys(authority_rank)
  input.mission.data_class in {"public", "private", "legal", "secret"}
  is_array(input.mission.allowed_tools)
  is_array(input.mission.prohibited_effects)
  is_boolean(input.request.external_effect)
  is_boolean(input.runtime.allow_external_effects)
}
