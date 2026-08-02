# Legacy-to-v4 integration coverage map

The 24 pre-reconciliation tests were audited individually. Valid behavior is preserved; unsafe hash-only, raw-content, catalogue-authority, or false-live expectations are replaced by stricter regressions. The corrected integration suite contains 30 tests.

| Original test | v4 replacement | Disposition |
|---|---|---|
| `test_current_workflow_receives_all_named_heartbeats` | `test_inventory_preserves_named_system_facades_without_granting_authority` | Preserved as inventory, not authority |
| `test_current_workflow_selects_primary_and_cross_system_assistants` | `test_verified_v4_is_the_only_recommendation_authority` | Replaced independent scoring with foundation scoring |
| `test_effectful_routes_are_held_without_permit` | `test_external_catalogue_routes_are_never_selected` | Strengthened to A0-only/no effect path |
| `test_missing_evidence_degrades_and_holds_capability` | Same behavior in `test_missing_evidence_degrades_and_foundation_holds_candidate` | Preserved |
| `test_duplicate_semantic_route_is_collapsed` | `test_duplicate_semantic_capability_is_coalesced_by_foundation` | Moved to sole authority |
| `test_safety_regression_cannot_win_on_quality` | `test_external_catalogue_routes_are_never_selected` | Stronger fail-closed substitute; facade quality cannot override v4 eligibility |
| `test_unknown_requirement_returns_gap` | `test_unknown_requirement_returns_gap_without_fallback_authority` | Preserved |
| `test_source_fingerprint_changes_with_evidence` | Same behavior in `test_source_fingerprint_changes_when_local_evidence_changes` | Preserved |
| `test_registry_rejects_path_escape` | `test_registry_rejects_path_escape_and_non_synthetic_static_data` | Strengthened |
| `test_authorized_child_inherits_verified_contract` | `test_registered_child_scaffold_inherits_scope_and_a0` | Strengthened with owner, matter, classification and A0 |
| `test_unauthorized_child_is_rejected` | `test_unregistered_child_has_no_scaffold_or_inherited_capability` | Preserved |
| `test_propagation_loop_is_rejected` | Verified-v4 foundation `test_loop_and_hop_limit_rejected` plus complete-lineage integration | Moved to cryptographic authority |
| `test_private_workflow_identifiers_are_hashed` | `test_raw_turn_content_and_static_fixture_are_rejected` and metadata-only signed storage | Strengthened: workflow identifiers are not transported |
| `test_reconciliation_distinguishes_active_stale_missing_and_unregistered` | `test_reconciliation_is_registry_readback_not_live_chat_claim` plus foundation freshness tests | Replaced false chat inference with registered-node readback |
| `test_hash_tampering_is_rejected` | `test_forged_signature_fails_closed` | Strengthened from hash to registry-bound HMAC |
| `test_older_heartbeat_replay_is_rejected` | `test_signed_sequence_gap_is_sync_pending_and_replay_is_rejected` | Preserved with signed identity |
| `test_current_report_contains_bible_node_envelope` | `test_report_does_not_emit_hash_only_bible_envelope` | Unsafe expectation inverted; only signed lineage is accepted |
| `test_all_documented_surfaces_receive_nodes_and_gap_cases` | `test_surface_and_scheduler_paths_are_inventory_only` | Preserved as inventory; removed automatic remediation authority |
| `test_turn_is_atomic_idempotent_and_returns_assistance` | `test_signed_turn_is_atomic_idempotent_and_destination_receipted` | Strengthened with complete signed lineage and receipt |
| `test_replay_sequence_is_rejected_and_gap_is_sync_pending` | Same behavior in signed sequence-gap regression | Preserved |
| `test_p2_event_projects_chat_and_task_details` | `test_p1_signed_storage_contains_no_raw_chat_or_task_fields` | Strengthened at every privacy tier |
| `test_stale_reconciliation_does_not_infer_liveness` | `test_reconciliation_does_not_infer_live_chat_awareness` | Preserved and strengthened |
| `test_kimmie_seed_requires_pre_before_post_and_hashes_private_results` | `test_connector_post_requires_committed_pre_event` plus no-raw-result regression | Preserved |
| `test_unindexed_or_unbound_surface_cannot_submit_turn` | `test_unhosted_or_catalogue_available_surface_cannot_authorize_ingress` | Strengthened |

The separate verified-v4 foundation suite remains the controlling regression corpus for lineage, rotation, stop generation, receipt freshness, privacy, respawn and immutable readback.
