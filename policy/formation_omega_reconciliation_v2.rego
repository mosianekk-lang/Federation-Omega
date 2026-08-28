package formationomega.reconciliation.v2

import rego.v1

default allow := false

deny contains "SEMANTIC_CONFLICT" if {
    input.semantic_conflict == true
}

deny contains "EXACT_PROVIDER_SNAPSHOT_REQUIRED" if {
    input.exact_snapshot_bound != true
}

deny contains "REQUIRED_CHECKS_INCOMPLETE" if {
    input.required_checks_passed != true
}

deny contains "ROLLBACK_UNPROVEN" if {
    input.rollback_available != true
}

deny contains "A1_INTERNAL_NO_EXTERNAL_EFFECT" if {
    input.external_effect == true
    input.authority_ceiling == "A1_INTERNAL"
}

deny contains "OWNER_AUTHORIZATION_REQUIRED" if {
    input.external_effect == true
    input.authority_ceiling != "A1_INTERNAL"
    input.owner_authorized != true
}

allow if {
    count(deny) == 0
}

decision := {
    "allow": allow,
    "deny": sort([reason | reason := deny[_]]),
}
