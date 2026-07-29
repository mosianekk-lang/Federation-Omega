from modisa_v2.schemas import WorkflowCreateRequest, WorkflowStatus


def test_workflow_lease_state_and_recovery(services):
    workflow = services.workflows.create(
        WorkflowCreateRequest(
            matter_id="MAT-W",
            mission_id="MIS-W",
            workflow_type="TEST",
            input_payload={"x": 1},
        ),
        "owner",
    )
    leased = services.workflows.lease(workflow.workflow_id, "worker-1")
    assert leased.status == WorkflowStatus.RUNNING
    services.workflows.update_state(workflow.workflow_id, "worker-1", {"stage": "proof"})
    waiting = services.workflows.wait_for_approval(workflow.workflow_id, "worker-1", {"approval_id": "APR-X"})
    assert waiting.status == WorkflowStatus.WAITING_APPROVAL
    resumed = services.workflows.resume_after_approval(workflow.workflow_id, "owner")
    assert resumed.status == WorkflowStatus.PENDING
    leased2 = services.workflows.lease(workflow.workflow_id, "worker-2")
    completed = services.workflows.complete(workflow.workflow_id, "worker-2", {"done": True})
    assert leased2.attempts == 2
    assert completed.status == WorkflowStatus.COMPLETED


def test_nonretryable_runtime_gate_blocks_workflow(services):
    from modisa_v2.schemas import WorkflowCreateRequest, WorkflowStatus

    created = services.workflows.create(
        WorkflowCreateRequest(
            matter_id="MAT-BLOCK",
            mission_id="MIS-BLOCK",
            workflow_type="LEGAL_CHAMBERS_MISSION",
            input_payload={"mission": "test blocked runtime"},
        ),
        actor_id="test",
    )
    leased = services.workflows.lease(created.workflow_id, "worker-block")
    assert leased.status == WorkflowStatus.RUNNING
    blocked = services.workflows.block(
        created.workflow_id,
        worker_id="worker-block",
        reason="OPENAI_API_KEY is not injected",
    )
    assert blocked.status == WorkflowStatus.BLOCKED
    assert blocked.lease_owner is None
    assert "OPENAI_API_KEY" in (blocked.last_error or "")
