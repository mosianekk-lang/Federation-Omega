from __future__ import annotations

import unittest
from dataclasses import replace

from evidenceops.capability_heartbeat.foundation.contracts import Authority, Classification, NodeType, digest
from evidenceops.capability_heartbeat.foundation.errors import (
    AuthorityError,
    ContractError,
    FreshnessError,
    PrivacyError,
    ReplayError,
    SignatureError,
    StopFencedError,
)
from evidenceops.capability_heartbeat.foundation.mailboxes import Inbox, Outbox, ReceiptStore
from evidenceops.capability_heartbeat.foundation.propagation import accept_envelope, build_envelope, forward_envelope
from evidenceops.capability_heartbeat.foundation.registry import NodeRegistry
from evidenceops.capability_heartbeat.foundation.stop_control import GenerationLease, RecommendationDelegation, StopControl

from evidenceops.capability_heartbeat.foundation_tests.helpers import (
    EXPIRES,
    MATTER,
    NOW,
    OBSERVED,
    OWNER,
    envelope,
    hash_of,
    ledger,
    node_signer,
    registry_with_chain,
    signer,
    stop_control,
)


def accept_legitimate(
    *,
    lineage,
    destination_node_id,
    registry,
    control=None,
    now=NOW,
    material_code="LEGITIMATE",
):
    control = control or stop_control()
    return accept_envelope(
        lineage=lineage,
        destination_node_id=destination_node_id,
        registry=registry,
        stop_control=control,
        runtime_verifiers={
            item.signing_node_id: node_signer(
                item.signing_node_id,
                rotation_generation=item.control_generation,
                material_code=material_code,
                signing_version=item.signer_identity.signing_version,
            )
            for item in lineage
        },
        destination_signer=node_signer(
            destination_node_id,
            rotation_generation=lineage[-1].control_generation,
            material_code=material_code,
        ),
        now=now,
    )


def forward_legitimate(
    *, lineage, forwarding_node_id, registry, control=None, now=NOW, material_code="LEGITIMATE"
):
    control = control or stop_control()
    return forward_envelope(
        lineage=lineage,
        forwarding_node_id=forwarding_node_id,
        registry=registry,
        stop_control=control,
        runtime_verifiers={
            item.signing_node_id: node_signer(
                item.signing_node_id,
                rotation_generation=item.control_generation,
                material_code=material_code,
                signing_version=item.signer_identity.signing_version,
            )
            for item in lineage
        },
        forwarding_signer=node_signer(
            forwarding_node_id,
            rotation_generation=lineage[-1].control_generation,
            material_code=material_code,
        ),
        now=now,
    )


def reseal(item, *, runtime_signer, **changes):
    provisional = replace(
        item,
        envelope_id="sha256:" + "0" * 64,
        idempotency_key="sha256:" + "0" * 64,
        signature="hmac-sha256:" + "0" * 64,
        **changes,
    )
    idempotency_key = digest(provisional.identity_body())
    envelope_id = digest(
        {
            "kind": "HEARTBEAT_ENVELOPE",
            "idempotency_key": idempotency_key,
            "trace_id": provisional.trace_id,
            "sequence": provisional.sequence,
        }
    )
    return runtime_signer.sign_envelope(
        replace(
            provisional,
            envelope_id=envelope_id,
            idempotency_key=idempotency_key,
        )
    )


def reseal_receipt(item, *, runtime_signer, **changes):
    provisional = replace(
        item,
        receipt_id="sha256:" + "0" * 64,
        signature="hmac-sha256:" + "0" * 64,
        **changes,
    )
    receipt_id = digest(
        {"kind": "HEARTBEAT_RECEIPT", "identity": provisional.identity_body()}
    )
    return runtime_signer.sign_receipt(replace(provisional, receipt_id=receipt_id))


class RegistryTests(unittest.TestCase):
    def test_master_bible_parent_child_inheritance(self):
        policy, registry, nodes = registry_with_chain(2)
        child = nodes[1]
        self.assertEqual(child.parent_node_id, policy.root_node_id)
        self.assertEqual(child.owner_code, OWNER)
        self.assertEqual(child.matter_code, MATTER)
        self.assertEqual(child.authority_ceiling, Authority.A0)
        self.assertTrue(registry.semantic_readback()["valid"])

    def test_child_authority_widening_rejected(self):
        policy, registry, nodes = registry_with_chain(1)
        child = policy.inherit_child(
            registry=registry,
            parent_node_id=nodes[0].node_id,
            child_node_id="NODE-WIDE",
            node_type=NodeType.AGENT_SPAWN,
            observed_at=OBSERVED,
            expires_at=EXPIRES,
            capability_hash=hash_of("CAP-WIDE"),
            endpoint_reference_hash=hash_of("ENDPOINT-WIDE"),
            registration_receipt=hash_of("RECEIPT-WIDE"),
            signer_identity=node_signer("NODE-WIDE").identity,
            requested_authority=Authority.A1,
        )
        with self.assertRaisesRegex(AuthorityError, "WIDENING"):
            registry.register(child)

    def test_child_classification_weakening_rejected(self):
        policy, registry, nodes = registry_with_chain(1)
        child = policy.inherit_child(
            registry=registry,
            parent_node_id=nodes[0].node_id,
            child_node_id="NODE-WEAK",
            node_type=NodeType.BIBLE_NODE,
            observed_at=OBSERVED,
            expires_at=EXPIRES,
            capability_hash=hash_of("CAP-WEAK"),
            endpoint_reference_hash=hash_of("ENDPOINT-WEAK"),
            registration_receipt=hash_of("RECEIPT-WEAK"),
            signer_identity=node_signer("NODE-WEAK").identity,
            requested_classification=Classification.PUBLIC_META,
        )
        with self.assertRaisesRegex(AuthorityError, "WEAKENING"):
            registry.register(child)

    def test_registration_conflict_rejected(self):
        _, registry, nodes = registry_with_chain(2)
        with self.assertRaisesRegex(ReplayError, "REGISTRATION_CONFLICT"):
            registry.register(replace(nodes[1], capability_hash=hash_of("DIFFERENT")))

    def test_child_signing_version_must_equal_parent(self):
        _, registry, nodes = registry_with_chain(2)
        with self.assertRaisesRegex(PrivacyError, "FIELD_CODE_NAMESPACE_MISMATCH"):
            replace(nodes[1].signer_identity, signing_version="HMAC-0.2")

    def test_root_signing_version_must_be_supported(self):
        _, _, nodes = registry_with_chain(1)
        with self.assertRaisesRegex(PrivacyError, "FIELD_CODE_NAMESPACE_MISMATCH"):
            replace(nodes[0].signer_identity, signing_version="HMAC-9.9")


class PropagationTests(unittest.TestCase):
    def test_frozen_tuple_contracts_snapshot_external_lists(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope()
        raw_records = [registry.get("NODE-ROOT")]
        frozen_registry = NodeRegistry(raw_records)
        raw_records.append(registry.get("NODE-CHILD-1"))
        self.assertIsInstance(frozen_registry.records, tuple)
        self.assertEqual(len(frozen_registry.records), 1)

        raw_events = list(ledger().events)
        frozen_ledger = type(ledger())(raw_events)
        raw_events.clear()
        self.assertIsInstance(frozen_ledger.events, tuple)
        self.assertEqual(len(frozen_ledger.events), 1)

        raw_envelopes = [item]
        outbox = Outbox(raw_envelopes)
        inbox = Inbox(raw_envelopes)
        raw_envelopes.clear()
        self.assertEqual(len(outbox.envelopes), 1)
        self.assertEqual(len(inbox.envelopes), 1)

        receipt = accept_legitimate(
            lineage=(item,), destination_node_id="NODE-CHILD-1", registry=registry
        )
        raw_receipts = [receipt]
        store = ReceiptStore(raw_receipts)
        raw_receipts.clear()
        self.assertIsInstance(store.receipts, tuple)
        self.assertEqual(len(store.receipts), 1)
    def test_valid_acceptance_returns_verifiable_receipt(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope()
        receipt = accept_legitimate(
            lineage=(item,),
            destination_node_id="NODE-CHILD-1",
            registry=registry,
        )
        destination_signer = node_signer("NODE-CHILD-1")
        destination_signer.verify_receipt(
            receipt,
            accepted_envelope=item,
            destination_record=registry.get("NODE-CHILD-1"),
            stop_control=stop_control(),
            now=NOW,
        )
        self.assertEqual(receipt.envelope_id, item.envelope_id)

    def test_forwarded_envelope_requires_complete_signed_lineage(self):
        _, registry, _ = registry_with_chain(3)
        root = envelope()
        child_signer = node_signer("NODE-CHILD-1")
        forged_child = reseal(
            root,
            runtime_signer=child_signer,
            signing_node_id="NODE-CHILD-1",
            signer_identity=child_signer.identity,
            parent_envelope_id=hash_of("NONEXISTENT-PARENT"),
            hop_count=1,
            visited_node_ids=("NODE-ROOT", "NODE-CHILD-1"),
            sequence=root.sequence + 1,
        )
        with self.assertRaisesRegex(ContractError, "LINEAGE_PARENT_ENVELOPE_MISMATCH"):
            accept_envelope(
                lineage=(root, forged_child),
                destination_node_id="NODE-CHILD-2",
                registry=registry,
                stop_control=stop_control(),
                runtime_verifiers={"NODE-ROOT": signer(), "NODE-CHILD-1": child_signer},
                destination_signer=node_signer("NODE-CHILD-2"),
                now=NOW,
            )

    def test_malformed_lineage_sequence_payload_and_completeness_are_rejected(self):
        _, registry, _ = registry_with_chain(3)
        root = envelope()
        child_signer = node_signer("NODE-CHILD-1")
        legitimate_child = forward_legitimate(
            lineage=(root,), forwarding_node_id="NODE-CHILD-1", registry=registry
        )
        with self.assertRaisesRegex(ContractError, "LINEAGE_HOP_SEQUENCE_MISMATCH"):
            accept_envelope(
                lineage=(legitimate_child,),
                destination_node_id="NODE-CHILD-2",
                registry=registry,
                stop_control=stop_control(),
                runtime_verifiers={"NODE-CHILD-1": child_signer},
                destination_signer=node_signer("NODE-CHILD-2"),
                now=NOW,
            )
        bad_sequence = reseal(
            legitimate_child,
            runtime_signer=child_signer,
            sequence=root.sequence + 2,
        )
        with self.assertRaisesRegex(ContractError, "LINEAGE_SEQUENCE_MISMATCH"):
            accept_envelope(
                lineage=(root, bad_sequence),
                destination_node_id="NODE-CHILD-2",
                registry=registry,
                stop_control=stop_control(),
                runtime_verifiers={"NODE-ROOT": signer(), "NODE-CHILD-1": child_signer},
                destination_signer=node_signer("NODE-CHILD-2"),
                now=NOW,
            )
        mutated_payload = reseal(
            legitimate_child,
            runtime_signer=child_signer,
            matter_code="MATTER-F4A5B6C7",
        )
        with self.assertRaisesRegex(ContractError, "LINEAGE_SEMANTIC_PAYLOAD_MUTATION"):
            accept_envelope(
                lineage=(root, mutated_payload),
                destination_node_id="NODE-CHILD-2",
                registry=registry,
                stop_control=stop_control(),
                runtime_verifiers={"NODE-ROOT": signer(), "NODE-CHILD-1": child_signer},
                destination_signer=node_signer("NODE-CHILD-2"),
                now=NOW,
            )

    def test_receipt_scope_is_cross_bound_to_accepted_envelope(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope()
        destination = registry.get("NODE-CHILD-1")
        destination_signer = node_signer("NODE-CHILD-1")
        receipt = accept_legitimate(
            lineage=(item,), destination_node_id=destination.node_id, registry=registry
        )
        with self.assertRaisesRegex(SignatureError, "RECEIPT_CREATION_SCOPE_MISMATCH"):
            destination_signer.make_receipt(
                envelope=replace(item, owner_code="OWNER-D4E5F6A7"),
                accepting_record=destination,
                stop_control=stop_control(),
                accepted_at=NOW,
            )
        variations = (
            {"owner_code": "OWNER-D4E5F6A7"},
            {"matter_code": "MATTER-E4F5A6B7"},
            {"envelope_id": hash_of("OTHER-ENVELOPE")},
            {"semantic_hash": hash_of("OTHER-SEMANTIC")},
        )
        for changes in variations:
            with self.subTest(changes=changes), self.assertRaisesRegex(
                SignatureError, "RECEIPT_ACCEPTED_ENVELOPE_SCOPE_MISMATCH"
            ):
                destination_signer.verify_receipt(
                    reseal_receipt(receipt, runtime_signer=destination_signer, **changes),
                    accepted_envelope=item,
                    destination_record=destination,
                    stop_control=stop_control(),
                    now=NOW,
                )
        rotated = node_signer("NODE-CHILD-1", rotation_generation=1)
        changed_control = reseal_receipt(
            receipt,
            runtime_signer=rotated,
            signer_identity=rotated.identity,
            control_generation=1,
        )
        with self.assertRaises(SignatureError):
            destination_signer.verify_receipt(
                changed_control,
                accepted_envelope=item,
                destination_record=destination,
                stop_control=stop_control(),
                now=NOW,
            )

    def test_receipt_acceptance_time_is_bounded_and_fresh(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope()
        destination = registry.get("NODE-CHILD-1")
        destination_signer = node_signer("NODE-CHILD-1")
        receipt = accept_legitimate(
            lineage=(item,), destination_node_id=destination.node_id, registry=registry
        )
        cases = (
            ("2026-08-02T12:01:00Z", NOW, "FUTURE_DATED"),
            ("2026-08-02T11:59:59Z", NOW, "OUTSIDE_(?:DESTINATION_REGISTRATION|ENVELOPE)_WINDOW"),
            (OBSERVED, "2026-08-02T12:05:01Z", "STALE_OR_ENVELOPE_EXPIRED"),
            (NOW, "2026-08-02T12:11:00Z", "(?:DESTINATION_REGISTRATION_NOT_FRESH|STALE_OR_ENVELOPE_EXPIRED)"),
        )
        for accepted_at, verify_now, code in cases:
            mutated = reseal_receipt(
                receipt,
                runtime_signer=destination_signer,
                accepted_at=accepted_at,
            )
            with self.subTest(accepted_at=accepted_at, now=verify_now), self.assertRaisesRegex(
                SignatureError, code
            ):
                destination_signer.verify_receipt(
                    mutated,
                    accepted_envelope=item,
                    destination_record=destination,
                    stop_control=stop_control(),
                    now=verify_now,
                )

    def test_receipt_verification_requires_fresh_destination_registration(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope()
        destination = registry.get("NODE-CHILD-1")
        destination_signer = node_signer("NODE-CHILD-1")
        receipt = accept_legitimate(
            lineage=(item,), destination_node_id=destination.node_id, registry=registry
        )
        expired_destination = replace(destination, expires_at="2026-08-02T12:00:05Z")
        with self.assertRaisesRegex(SignatureError, "DESTINATION_REGISTRATION_NOT_FRESH"):
            destination_signer.verify_receipt(
                receipt,
                accepted_envelope=item,
                destination_record=expired_destination,
                stop_control=stop_control(),
                now=NOW,
            )

    def test_invalid_envelope_signature_rejected(self):
        _, registry, _ = registry_with_chain(2)
        with self.assertRaisesRegex(SignatureError, "INVALID_ENVELOPE_SIGNATURE"):
            accept_legitimate(
                lineage=(replace(envelope(), signature="hmac-sha256:" + "1" * 64),),
                destination_node_id="NODE-CHILD-1",
                registry=registry,
            )

    def test_invalid_receipt_signature_rejected(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope()
        receipt = accept_legitimate(
            lineage=(item,), destination_node_id="NODE-CHILD-1", registry=registry
        )
        with self.assertRaisesRegex(SignatureError, "INVALID_RECEIPT_SIGNATURE"):
            node_signer("NODE-CHILD-1").verify_receipt(
                replace(receipt, signature="hmac-sha256:" + "2" * 64),
                accepted_envelope=item,
                destination_record=registry.get("NODE-CHILD-1"),
                stop_control=stop_control(),
                now=NOW,
            )

    def test_attacker_signer_reusing_registered_key_id_is_rejected(self):
        _, registry, _ = registry_with_chain(2)
        attacker = node_signer(
            "NODE-ROOT",
            material_code="ATTACKER",
            key_id=signer().key_id,
        )
        forged = envelope(runtime_signer=attacker)
        with self.assertRaisesRegex(SignatureError, "SIGNER_REGISTRY_BINDING_MISMATCH"):
            accept_envelope(
                lineage=(forged,),
                destination_node_id="NODE-CHILD-1",
                registry=registry,
                stop_control=stop_control(),
                runtime_verifiers={"NODE-ROOT": attacker},
                destination_signer=node_signer("NODE-CHILD-1"),
                now=NOW,
            )

    def test_unregistered_signing_node_is_rejected(self):
        _, registry, _ = registry_with_chain(2)
        attacker = node_signer("NODE-UNREGISTERED", material_code="ATTACKER")
        root = envelope()
        forged = reseal(
            root,
            runtime_signer=attacker,
            signing_node_id="NODE-UNREGISTERED",
            signer_identity=attacker.identity,
            parent_envelope_id=root.envelope_id,
            hop_count=1,
            visited_node_ids=("NODE-ROOT", "NODE-UNREGISTERED"),
            sequence=2,
        )
        with self.assertRaisesRegex(ContractError, "NODE_NOT_REGISTERED"):
            accept_envelope(
                lineage=(root, forged),
                destination_node_id="NODE-CHILD-1",
                registry=registry,
                stop_control=stop_control(),
                runtime_verifiers={"NODE-ROOT": signer(), "NODE-UNREGISTERED": attacker},
                destination_signer=node_signer("NODE-CHILD-1"),
                now=NOW,
            )

    def test_forged_destination_receipt_is_rejected(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope()
        receipt = accept_legitimate(
            lineage=(item,), destination_node_id="NODE-CHILD-1", registry=registry
        )
        attacker = node_signer(
            "NODE-CHILD-1",
            material_code="ATTACKER",
            key_id=node_signer("NODE-CHILD-1").key_id,
        )
        forged = attacker.sign_receipt(
            replace(
                receipt,
                signer_identity=attacker.identity,
                signature="hmac-sha256:" + "0" * 64,
            )
        )
        with self.assertRaisesRegex(SignatureError, "SIGNER_REGISTRY_BINDING_MISMATCH"):
            attacker.verify_receipt(
                forged,
                accepted_envelope=item,
                destination_record=registry.get("NODE-CHILD-1"),
                stop_control=stop_control(),
                now=NOW,
            )

    def test_stale_rotation_generation_is_rejected(self):
        _, rotated_registry, _ = registry_with_chain(
            2,
            control_generation=1,
            material_code="ROTATED",
        )
        stale_signer = signer(rotation_generation=0)
        with self.assertRaisesRegex(SignatureError, "SIGNER_REGISTRY_BINDING_MISMATCH"):
            stale_signer.assert_binding(
                node_record=rotated_registry.get("NODE-ROOT"),
                stop_control=StopControl(generation=1),
            )

    def test_legitimate_rotation_generation_passes(self):
        _, rotated_registry, _ = registry_with_chain(
            2,
            control_generation=1,
            material_code="ROTATED",
        )
        root_signer = signer(rotation_generation=1, material_code="ROTATED")
        item = envelope(
            control_generation=1,
            runtime_signer=root_signer,
        )
        receipt = accept_envelope(
            lineage=(item,),
            destination_node_id="NODE-CHILD-1",
            registry=rotated_registry,
            stop_control=StopControl(generation=1),
            runtime_verifiers={"NODE-ROOT": root_signer},
            destination_signer=node_signer(
                "NODE-CHILD-1",
                rotation_generation=1,
                material_code="ROTATED",
            ),
            now=NOW,
        )
        self.assertEqual(receipt.control_generation, 1)

    def test_weaker_envelope_classification_is_rejected(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope(classification=Classification.PUBLIC_META)
        with self.assertRaisesRegex(ContractError, "CLASSIFICATION_WEAKER"):
            accept_legitimate(
                lineage=(item,),
                destination_node_id="NODE-CHILD-1",
                registry=registry,
            )

    def test_destination_classification_fence_is_independent(self):
        policy, registry, nodes = registry_with_chain(1)
        child = policy.inherit_child(
            registry=registry,
            parent_node_id=nodes[0].node_id,
            child_node_id="NODE-RESTRICTED",
            node_type=NodeType.BIBLE_NODE,
            observed_at=OBSERVED,
            expires_at=EXPIRES,
            capability_hash=hash_of("CAP-RESTRICTED"),
            endpoint_reference_hash=hash_of("ENDPOINT-RESTRICTED"),
            registration_receipt=hash_of("RECEIPT-RESTRICTED"),
            signer_identity=node_signer("NODE-RESTRICTED").identity,
            requested_classification=Classification.RESTRICTED_META,
        )
        registry = registry.register(child)
        with self.assertRaisesRegex(ContractError, "CLASSIFICATION_WEAKER"):
            accept_envelope(
                lineage=(envelope(classification=Classification.INTERNAL_META),),
                destination_node_id="NODE-RESTRICTED",
                registry=registry,
                stop_control=stop_control(),
                runtime_verifiers={"NODE-ROOT": signer()},
                destination_signer=node_signer("NODE-RESTRICTED"),
                now=NOW,
            )

    def test_destination_parent_chain_mismatch_is_rejected(self):
        _, registry, _ = registry_with_chain(4)
        root = envelope()
        first = forward_legitimate(
            lineage=(root,), forwarding_node_id="NODE-CHILD-1", registry=registry
        )
        with self.assertRaisesRegex(ContractError, "DESTINATION_PARENT_CHAIN_MISMATCH"):
            accept_legitimate(
                lineage=(root, first),
                destination_node_id="NODE-CHILD-3",
                registry=registry,
            )

    def test_expired_envelope_rejected(self):
        _, registry, _ = registry_with_chain(2)
        with self.assertRaisesRegex(FreshnessError, "EXPIRED"):
            accept_legitimate(
                lineage=(envelope(),),
                destination_node_id="NODE-CHILD-1",
                registry=registry,
                now="2026-08-02T12:11:00Z",
            )

    def test_stale_but_unexpired_envelope_rejected(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope(observed_at="2026-08-02T11:50:00Z", expires_at="2026-08-02T12:20:00Z")
        with self.assertRaisesRegex(FreshnessError, "STALE"):
            accept_legitimate(
                lineage=(item,), destination_node_id="NODE-CHILD-1", registry=registry
            )

    def test_future_envelope_rejected(self):
        _, registry, _ = registry_with_chain(2)
        item = envelope(observed_at="2026-08-02T12:05:00Z", expires_at="2026-08-02T12:15:00Z")
        with self.assertRaisesRegex(FreshnessError, "FUTURE_DATED"):
            accept_legitimate(
                lineage=(item,), destination_node_id="NODE-CHILD-1", registry=registry
            )

    def test_stop_generation_invalidates_envelope(self):
        _, registry, _ = registry_with_chain(2)
        stopped = stop_control().stop("STOP-OWNER")
        with self.assertRaisesRegex(StopFencedError, "CONTROL_STOPPED"):
            accept_legitimate(
                lineage=(envelope(),),
                destination_node_id="NODE-CHILD-1",
                registry=registry,
                control=stopped,
            )

    def test_stop_generation_invalidates_lease_and_delegation(self):
        active = stop_control()
        lease = GenerationLease(
            lease_id=hash_of("LEASE-001"),
            node_id="NODE-ROOT",
            owner_code=OWNER,
            matter_code=MATTER,
            control_generation=0,
            issued_at=OBSERVED,
            expires_at="2026-08-02T12:04:00Z",
        )
        delegation = RecommendationDelegation(
            delegation_id=hash_of("DELEGATION-001"),
            from_node_id="NODE-ROOT",
            to_node_id="NODE-CHILD-1",
            owner_code=OWNER,
            matter_code=MATTER,
            recommendation_hash=hash_of("RECOMMENDATION-001"),
            control_generation=0,
            issued_at=OBSERVED,
            expires_at="2026-08-02T12:04:00Z",
        )
        lease.assert_current(stop_control=active, now=NOW)
        delegation.assert_current(stop_control=active, now=NOW)
        stopped = active.stop("STOP-OWNER")
        with self.assertRaises(StopFencedError):
            lease.assert_current(stop_control=stopped, now=NOW)
        with self.assertRaises(StopFencedError):
            delegation.assert_current(stop_control=stopped, now=NOW)

    def test_delegation_cannot_widen_authority(self):
        with self.assertRaisesRegex(ContractError, "DELEGATION_AUTHORITY_MUST_BE_A0"):
            RecommendationDelegation(
                delegation_id=hash_of("DELEGATION-WIDE"),
                from_node_id="NODE-ROOT",
                to_node_id="NODE-CHILD-1",
                owner_code=OWNER,
                matter_code=MATTER,
                recommendation_hash=hash_of("RECOMMENDATION-WIDE"),
                control_generation=0,
                issued_at=OBSERVED,
                expires_at="2026-08-02T12:04:00Z",
                authority_ceiling=Authority.A1,
            )

    def test_cross_owner_bleed_rejected(self):
        _, registry, _ = registry_with_chain(2)
        base = envelope()
        item = build_envelope(
            signer=signer(),
            trace_id=base.trace_id,
            origin_node_id=base.origin_node_id,
            root_transaction_id=base.root_transaction_id,
            mission_code=base.mission_code,
            owner_code="OWNER-D4E5F6A7",
            matter_code=base.matter_code,
            classification=base.classification,
            state=base.state,
            capability_hashes=base.capability_hashes,
            blocker_codes=base.blocker_codes,
            recommendations=base.recommendations,
            observed_at=base.observed_at,
            expires_at=base.expires_at,
            sequence=base.sequence,
            control_generation=base.control_generation,
        )
        with self.assertRaisesRegex(ContractError, "CROSS_OWNER"):
            accept_legitimate(
                lineage=(item,), destination_node_id="NODE-CHILD-1", registry=registry
            )

    def test_loop_and_hop_limit_rejected(self):
        item = envelope()
        _, long_registry, _ = registry_with_chain(5)
        with self.assertRaisesRegex(ReplayError, "LOOP"):
            forward_legitimate(
                lineage=(item,), forwarding_node_id="NODE-ROOT", registry=long_registry
            )
        first = forward_legitimate(
            lineage=(item,), forwarding_node_id="NODE-CHILD-1", registry=long_registry
        )
        second = forward_legitimate(
            lineage=(item, first), forwarding_node_id="NODE-CHILD-2", registry=long_registry
        )
        third = forward_legitimate(
            lineage=(item, first, second), forwarding_node_id="NODE-CHILD-3", registry=long_registry
        )
        self.assertEqual(third.hop_count, 3)
        receipt = accept_legitimate(
            lineage=(item, first, second, third),
            destination_node_id="NODE-CHILD-4",
            registry=long_registry,
        )
        self.assertEqual(receipt.accepting_node_id, "NODE-CHILD-4")
        with self.assertRaisesRegex(ContractError, "HOP_LIMIT"):
            forward_legitimate(
                lineage=(item, first, second, third),
                forwarding_node_id="NODE-CHILD-4",
                registry=long_registry,
            )

    def test_mailbox_replay_idempotency_conflict(self):
        item = envelope()
        self.assertEqual(len(Outbox().enqueue(item).enqueue(item).envelopes), 1)
        with self.assertRaisesRegex(ReplayError, "IDEMPOTENCY_CONFLICT"):
            Outbox().enqueue(item).enqueue(replace(item, signature="hmac-sha256:" + "3" * 64))
        self.assertEqual(len(Inbox().accept(item).accept(item).envelopes), 1)

    def test_receipt_store_semantic_conflict(self):
        _, registry, _ = registry_with_chain(2)
        receipt = accept_legitimate(
            lineage=(envelope(),), destination_node_id="NODE-CHILD-1", registry=registry
        )
        store = ReceiptStore().record(receipt).record(receipt)
        self.assertEqual(len(store.receipts), 1)
        conflicting = replace(
            receipt,
            receipt_id=hash_of("OTHER-RECEIPT"),
            semantic_hash=hash_of("OTHER-SEMANTIC"),
        )
        with self.assertRaisesRegex(ReplayError, "SEMANTIC_CONFLICT"):
            store.record(conflicting)


if __name__ == "__main__":
    unittest.main()
