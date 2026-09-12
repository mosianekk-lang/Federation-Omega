import unittest

from federation.single_mind_collective_cognition_v1 import (
    BeliefClaim,
    ClaimState,
    ConflictClass,
    ContinuationCapsule,
    DedupeAction,
    EpistemicMode,
    SemanticObjective,
    SpawnRecord,
    choose_dedupe_action,
    classify_conflict,
    continuation_required,
    derive_active_cognition_map,
    preserve_contradictions,
    propagate_learning,
    sibling_preflight,
)


def spawn(
    sid,
    *,
    state="RUNNING",
    objective_hash="obj",
    read=(),
    write=(),
    effect=(),
    source_epoch="src1",
    provider_epoch="p1",
    canonical=False,
    known=True,
    checkpoint="cp",
):
    return SpawnRecord(
        spawn_id=sid,
        parent_spawn_id=None,
        mission_id="m1",
        packet_id="p1",
        semantic_role_id="role",
        worker_class="ARCHITECT",
        runtime="test",
        provider=None,
        model=None,
        state=state,
        dependencies=(),
        read_scope=tuple(read),
        write_scope=tuple(write),
        effect_scope=tuple(effect),
        source_epoch=source_epoch,
        provider_epoch=provider_epoch,
        authority_ceiling="A1",
        privacy_ceiling="P1",
        cost_ceiling="ZERO",
        idempotency_key=sid,
        fencing_token=1,
        heartbeat_at="2026-09-12T23:00:00+02:00",
        checkpoint_pointer=checkpoint,
        semantic_objective_hash=objective_hash,
        touches_canonical_state=canonical,
        scope_known=known,
    )


class SemanticObjectiveTests(unittest.TestCase):
    def test_deterministic_normalization(self):
        a = SemanticObjective.build(
            " Diagnose   Relay ",
            ["B", "a", "A"],
            "WOAF",
            ["/x", "/Y"],
            ["NONE"],
            "src",
            "provider",
        )
        b = SemanticObjective.build(
            "diagnose relay",
            ["a", "b"],
            "woaf",
            ["/y", "/x"],
            ["none"],
            "src",
            "provider",
        )
        self.assertEqual(a.fingerprint, b.fingerprint)

    def test_epoch_change_invalidates_identity(self):
        a = SemanticObjective.build("x", ["done"], "cap", source_epoch="s1")
        b = SemanticObjective.build("x", ["done"], "cap", source_epoch="s2")
        self.assertNotEqual(a.fingerprint, b.fingerprint)


class ConflictTests(unittest.TestCase):
    def test_disjoint_read(self):
        self.assertEqual(classify_conflict(spawn("a", read=("x",)), spawn("b", read=("y",))), ConflictClass.DISJOINT_READ)

    def test_shared_read(self):
        self.assertEqual(classify_conflict(spawn("a", read=("x",)), spawn("b", read=("x",))), ConflictClass.SHARED_READ)

    def test_disjoint_write(self):
        self.assertEqual(classify_conflict(spawn("a", write=("x",)), spawn("b", write=("y",))), ConflictClass.DISJOINT_WRITE)

    def test_overlapping_write(self):
        self.assertEqual(classify_conflict(spawn("a", write=("x",)), spawn("b", write=("x",))), ConflictClass.OVERLAPPING_WRITE)

    def test_write_read_overlap_is_serialized(self):
        self.assertEqual(classify_conflict(spawn("a", write=("x",)), spawn("b", read=("x",))), ConflictClass.OVERLAPPING_WRITE)

    def test_shared_effect(self):
        self.assertEqual(classify_conflict(spawn("a", effect=("deploy:svc",)), spawn("b", effect=("deploy:svc",))), ConflictClass.SHARED_EFFECT)

    def test_canonical_state_serializes(self):
        self.assertEqual(classify_conflict(spawn("a", canonical=True), spawn("b")), ConflictClass.CANONICAL_STATE)

    def test_unknown_scope_fails_closed(self):
        self.assertEqual(classify_conflict(spawn("a", known=False), spawn("b")), ConflictClass.UNKNOWN)


class DedupeTests(unittest.TestCase):
    def test_duplicate_active_joins(self):
        n = spawn("n", objective_hash="same")
        s = spawn("s", objective_hash="same", state="RUNNING")
        self.assertEqual(choose_dedupe_action(n, [s]), DedupeAction.JOIN_EXISTING)

    def test_completed_duplicate_consumes_result(self):
        n = spawn("n", objective_hash="same")
        s = spawn("s", objective_hash="same", state="ACKED")
        self.assertEqual(choose_dedupe_action(n, [s]), DedupeAction.CONSUME_RESULT)

    def test_different_epoch_is_not_duplicate(self):
        n = spawn("n", objective_hash="same", source_epoch="s2")
        s = spawn("s", objective_hash="same", source_epoch="s1")
        self.assertEqual(choose_dedupe_action(n, [s]), DedupeAction.START)

    def test_blind_challenger_stays_independent(self):
        n = spawn("n", objective_hash="same")
        s = spawn("s", objective_hash="same")
        self.assertEqual(
            choose_dedupe_action(n, [s], epistemic_mode=EpistemicMode.BLIND_CHALLENGER),
            DedupeAction.BECOME_CRITIC,
        )


class ContinuityAndKnowledgeTests(unittest.TestCase):
    def test_continuation_capsule_is_stable(self):
        c = ContinuationCapsule(
            mission_id="m",
            packet_id="p",
            objective_hash="o",
            terminal_predicates_closed=("a",),
            terminal_predicates_open=("b",),
            accepted_fact_refs=("f1",),
            contradiction_refs=("c1",),
            completed_work_refs=("w1",),
            failure_fingerprints=("e1",),
            active_owner_refs=("a1",),
            source_epoch="s",
            provider_epochs=("p",),
            artifact_refs=("z",),
            checkpoint_hash="cp",
            authority_ceiling="A1",
            effect_ceiling="NONE",
            next_dependency_ready_action="next",
        )
        self.assertEqual(c.digest, c.digest)
        self.assertEqual(c.owner_action_required, "NONE")

    def test_running_without_checkpoint_is_detected(self):
        self.assertTrue(continuation_required(spawn("a", checkpoint=None)))
        self.assertFalse(continuation_required(spawn("a", checkpoint="cp")))

    def test_contradictions_are_preserved(self):
        claims = (
            BeliefClaim("c1", "provider-live", "true", ClaimState.EVIDENCE_SUPPORTED, "t1"),
            BeliefClaim("c2", "provider-live", "false", ClaimState.EVIDENCE_SUPPORTED, "t2"),
        )
        self.assertEqual(preserve_contradictions(claims), claims)

    def test_learning_never_inherits_authority(self):
        out = propagate_learning(
            learning_refs=["L1"],
            receiver_scope=["WOAF"],
            authority_ceiling="A3",
            provider_permissions=["admin"],
        )
        self.assertFalse(out["authority_inherited"])
        self.assertFalse(out["provider_permissions_inherited"])


class ProjectionTests(unittest.TestCase):
    def test_active_map_excludes_terminal(self):
        records = [spawn("b", state="RUNNING"), spawn("a", state="TERMINATED"), spawn("c", state="WAITING")]
        view = derive_active_cognition_map(records)
        self.assertEqual([x["spawn_id"] for x in view], ["b", "c"])
        self.assertNotIn("read_scope", view[0])
        self.assertIn("read_scope_digest", view[0])

    def test_preflight_blocks_overlap_but_allows_disjoint(self):
        actor = spawn("a", write=("x",), objective_hash="oa")
        siblings = [spawn("b", write=("x",), objective_hash="ob"), spawn("c", read=("z",), objective_hash="oc")]
        out = sibling_preflight(actor, siblings)
        self.assertEqual(out["conflicts"]["b"], ConflictClass.OVERLAPPING_WRITE.value)
        self.assertEqual(out["conflicts"]["c"], ConflictClass.DISJOINT_WRITE.value)
        self.assertEqual(out["blocking_siblings"], ("b",))


if __name__ == "__main__":
    unittest.main()
