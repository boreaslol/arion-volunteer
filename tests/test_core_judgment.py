from __future__ import annotations

from pathlib import Path

import pytest

from planner.domain_pack import load_domain_pack
from planner.runtime_event_store import RuntimeEventStore
from planner.secret_safety import require_secret_safe
from planner.execution_planner import plan_runtime
from planner.task_graph_execution import TaskGraphExecutionCoordinator
from planner.unified_execution import (
    UnifiedExecutionEngine,
    build_task_graph_executor_registry,
)
from planner.working_set_store import WorkingSetStore


ROOT = Path(__file__).resolve().parents[1]
VOLUNTEER_PACK_ROOT = ROOT / "volunteer_pack"


def _pack():
    return load_domain_pack(
        pack_root=VOLUNTEER_PACK_ROOT,
        manifest_path="manifest.yaml",
    )


def test_runtime_state_rejects_credential_material() -> None:
    with pytest.raises(ValueError, match="credential material"):
        require_secret_safe(
            {
                "question": (
                    "Inspect "
                    + "tok"
                    + "en="
                    + "AUDIT_RUNTIME_SECRET_7f91c2"
                ),
                "pass" + "word": "AUDIT_RUNTIME_SECRET_7f91c2",
            },
            label="runtime",
        )

    require_secret_safe(
        {
            "secret_ref": "profile://example-reader",
            "redacted": "token=<redacted>",
        },
        label="runtime",
    )


def test_open_items_create_parallel_agents_for_one_role() -> None:
    planned = plan_runtime(
        domain_pack=_pack(),
        question="Continue the bounded inquiry.",
        run_id="volunteer-multi-agent",
        working_set={
            "task_id": "volunteer-task",
            "version": 2,
            "unknowns": [
                {
                    "source_role": "Data Analyst",
                    "statement": "Test the observation boundary.",
                },
                {
                    "source_role": "Data Analyst",
                    "statement": "Test the comparison boundary.",
                },
            ],
        },
    )

    assert planned.direct_run is None
    assert planned.task_graph is not None
    assert len(planned.decision.agent_assignments) == 2
    agents = [
        node
        for node in planned.task_graph.nodes
        if node.kind == "role_runtime"
    ]
    assert len(agents) == 2
    assert all(node.assignee_role == "Data Analyst" for node in agents)
    assert agents[0].depends_on == agents[1].depends_on


def test_closure_cannot_hide_open_items(tmp_path: Path) -> None:
    pack = _pack()
    planned = plan_runtime(
        domain_pack=pack,
        question="Explore a counterfactual and competing hypothesis.",
        run_id="volunteer-closure",
    )
    working_sets = WorkingSetStore(tmp_path / "tasks")
    task, _ = working_sets.create_task(
        task_id="volunteer-closure-task",
        objective=planned.capability_plan.question,
        user_intent=planned.capability_plan.question,
        acceptance_boundary="Keep incompleteness explicit.",
        accountable_owner=pack.governance.orchestrator_role,
        initial_working_set={
            "unknowns": [
                {
                    "source_role": "Strategy Analyst",
                    "statement": "Will the observation persist?",
                }
            ],
            "counterfactuals": [
                {
                    "source_role": "Strategy Analyst",
                    "hypothesis": "An alternative cause explains the change.",
                    "status": "untested",
                }
            ],
        },
    )
    coordinator = TaskGraphExecutionCoordinator(
        engine=UnifiedExecutionEngine(
            store=RuntimeEventStore(tmp_path / "runtime.sqlite3"),
            registry=build_task_graph_executor_registry(domain_pack=pack),
            run_root=tmp_path / "runs",
        ),
        working_sets=working_sets,
    )
    coordinator.run(planned.task_graph, task_id=task.task_id)

    with pytest.raises(ValueError, match="closure disposition"):
        coordinator.resolve(
            planned.task_graph.run_id,
            "gate.orchestrator-closure",
            task_id=task.task_id,
            actor="Lead",
            decision="approve",
            output={
                "decision": "CLOSED",
                "judgment": "The bounded inquiry is sufficient.",
                "open_item_disposition": {
                    "unknowns": "none_open",
                    "counterfactuals": "none_open",
                    "reason": "Incorrectly hides open items.",
                },
                "revision_triggers": [
                    "A new observation contradicts the judgment."
                ],
                "observation_obligations": [],
            },
        )

    coordinator.resolve(
        planned.task_graph.run_id,
        "gate.orchestrator-closure",
        task_id=task.task_id,
        actor="Lead",
        decision="approve",
        output={
            "decision": "CLOSED",
            "judgment": "The bounded inquiry is sufficient and revisable.",
            "open_item_disposition": {
                "unknowns": "accepted_with_obligations",
                "counterfactuals": "accepted_with_obligations",
                "reason": "The remaining uncertainty is explicitly bounded.",
            },
            "revision_triggers": [
                "A new observation contradicts the judgment."
            ],
            "observation_obligations": [
                "Repeat the observation in the next bounded window."
            ],
        },
    )

    closed_task, working_set = working_sets.load_context(task.task_id)
    assert closed_task.status == "closed"
    assert working_set.unknowns
    assert working_set.counterfactuals
    open_counts = working_set.current_judgment["open_item_counts"]
    assert open_counts["unknowns"] == 1
    assert open_counts["counterfactuals"] >= 1
