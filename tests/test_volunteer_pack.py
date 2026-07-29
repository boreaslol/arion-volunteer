from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from pytest import MonkeyPatch
import yaml

from planner.direct_execution import (
    DirectRunEngine,
    build_direct_executor_registry,
)
from planner.domain_pack import load_domain_pack
from planner.runtime_event_store import RuntimeEventStore
from planner.execution_planner import plan_runtime
from planner.unified_execution import (
    UnifiedExecutionEngine,
    build_task_graph_executor_registry,
)
from planner.working_set_store import WorkingSetStore
from volunteer_pack import bundled_pack_root


ROOT = Path(__file__).resolve().parents[1]
VOLUNTEER_PACK_ROOT = bundled_pack_root()
EXPECTED_ROLES = (
    "Lead",
    "Data Analyst",
    "Strategy Analyst",
    "Anti-Fraud Specialist",
    "Model Engineer",
    "Risk Platform Engineer",
    "Release Engineer",
    "Release Verifier",
)


def _volunteer_pack():
    return load_domain_pack(
        pack_root=VOLUNTEER_PACK_ROOT,
        manifest_path="manifest.yaml",
    )


def test_bundled_pack_root_loads_assets_from_external_cwd(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    external_cwd = tmp_path / "outside-source"
    external_cwd.mkdir()
    assert ROOT not in external_cwd.parents
    monkeypatch.chdir(external_cwd)

    pack_root = bundled_pack_root()
    assert pack_root.is_absolute()
    manifest = yaml.safe_load(
        (pack_root / "manifest.yaml").read_text(encoding="utf-8")
    )
    registry = yaml.safe_load(
        (pack_root / "roles.yaml").read_text(encoding="utf-8")
    )
    for role in registry["roles"]:
        assert (pack_root / role["instruction_file"]).is_file()
        for skill_file in role["skill_files"]:
            assert (pack_root / skill_file).is_file()

    domain_pack = load_domain_pack(
        pack_root=pack_root,
        manifest_path="manifest.yaml",
    )
    planned = plan_runtime(
        domain_pack=domain_pack,
        question="Inspect one bounded local observation.",
        run_id="external-cwd-direct",
    )

    assert manifest["pack_id"] == "arion-volunteer"
    assert planned.direct_run is not None
    assert planned.direct_run.metadata["resolved_method_bindings"]


def test_volunteer_pack_registers_roles_skills_without_semantic_layer() -> None:
    manifest = yaml.safe_load(
        (VOLUNTEER_PACK_ROOT / "manifest.yaml").read_text(encoding="utf-8")
    )
    registry = yaml.safe_load(
        (VOLUNTEER_PACK_ROOT / "roles.yaml").read_text(encoding="utf-8")
    )
    pack = _volunteer_pack()

    assert manifest["semantic_roots"] == []
    assert pack.paths_for("semantic_roots") == ()
    assert pack.governance.role_order == EXPECTED_ROLES
    assert not any(
        path.name in {"semantics", "semantic_layer"}
        for path in VOLUNTEER_PACK_ROOT.rglob("*")
    )
    for role in registry["roles"]:
        assert (VOLUNTEER_PACK_ROOT / role["instruction_file"]).is_file()
        assert role["skill_files"]
        for skill_file in role["skill_files"]:
            assert (VOLUNTEER_PACK_ROOT / skill_file).is_file()


def test_volunteer_pack_executes_direct_run(tmp_path: Path) -> None:
    domain_pack = _volunteer_pack()
    planned = plan_runtime(
        domain_pack=domain_pack,
        question="Inspect one bounded local observation.",
        run_id="volunteer-direct",
    )
    assert planned.direct_run is not None
    assert planned.decision.selected_owner_role == "Data Analyst"
    assert planned.direct_run.metadata["method_pack"]["pack_id"] == (
        "arion-volunteer-methods"
    )
    assert [
        binding["method_id"]
        for binding in planned.direct_run.metadata["resolved_method_bindings"]
    ] == ["bounded_observation"]
    assert planned.direct_run.metadata["connector_bindings"] == [
        "generated_evidence"
    ]
    assert planned.direct_run.metadata["semantic_roots"] == []
    working_sets = WorkingSetStore(tmp_path / "tasks")
    task, _ = working_sets.create_task(
        task_id="volunteer-direct-task",
        objective=planned.capability_plan.question,
        user_intent=planned.capability_plan.question,
        acceptance_boundary="Keep generated evidence bounded.",
        accountable_owner=domain_pack.governance.orchestrator_role,
    )
    engine = DirectRunEngine(
        registry=build_direct_executor_registry(domain_pack=domain_pack),
        run_root=tmp_path / "runs",
        working_sets=working_sets,
    )

    result = engine.run(planned.direct_run, task_id=task.task_id)

    assert result["status"] == "succeeded"
    assert result["output"]["status"] == "bounded_observation_completed"
    assert (
        tmp_path
        / "runs"
        / "volunteer-direct"
        / "artifacts"
        / "bounded_observation.json"
    ).is_file()


def test_counterfactual_activates_strategy_role_and_lead_gate(
    tmp_path: Path,
) -> None:
    domain_pack = _volunteer_pack()
    planned = plan_runtime(
        domain_pack=domain_pack,
        question="Explore a counterfactual and competing hypothesis.",
        run_id="volunteer-graph",
    )
    assert planned.task_graph is not None
    assert planned.decision.active_roles == ("Strategy Analyst",)
    assert [
        item["method_id"]
        for item in planned.task_graph.metadata["resolved_method_bindings"]
    ] == ["counterfactual_probe"]
    store = RuntimeEventStore(tmp_path / "runtime.sqlite3")
    engine = UnifiedExecutionEngine(
        store=store,
        registry=build_task_graph_executor_registry(domain_pack=domain_pack),
        run_root=tmp_path / "runs",
    )

    waiting = engine.run(planned.task_graph)

    role_plan_nodes = [
        node
        for node in planned.task_graph.nodes
        if node.kind == "role_runtime"
    ]
    role_node_ids = {node.node_id for node in role_plan_nodes}
    role_nodes = [
        node
        for node in waiting["nodes"]
        if node["node_id"] in role_node_ids
    ]
    assert waiting["status"] == "waiting"
    assert len(role_plan_nodes) == 1
    assert role_plan_nodes[0].assignee_role == "Strategy Analyst"
    assert len(role_nodes) == 1
    assert role_nodes[0]["status"] == "succeeded"
    gate = next(
        node
        for node in waiting["nodes"]
        if node["node_id"] == "gate.orchestrator-closure"
    )
    gate_plan = next(
        node
        for node in planned.task_graph.nodes
        if node.node_id == "gate.orchestrator-closure"
    )
    assert gate_plan.assignee_role == "Lead"
    assert gate["status"] == "waiting_human"
    store.resolve_waiting_node(
        planned.task_graph.run_id,
        "gate.orchestrator-closure",
        actor="Lead",
        decision="approve",
        output={
            "decision": "CLOSED",
            "note": "Bounded volunteer inquiry complete.",
        },
    )

    assert engine.resume(planned.task_graph.run_id)["status"] == "succeeded"


def test_volunteer_pack_runs_with_private_modules_blocked(
    tmp_path: Path,
) -> None:
    script = f"""
import importlib.abc
from pathlib import Path
import tempfile

BLOCKED = (
    "domain_pack",
    "risk_core",
    "loan_metrics_analysis",
    "loan_metrics_queries",
    "scripts",
)

class PrivateModuleBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == prefix or fullname.startswith(prefix + ".") for prefix in BLOCKED):
            raise ImportError("private module blocked: " + fullname)
        return None

import sys
sys.meta_path.insert(0, PrivateModuleBlocker())

from planner.direct_execution import DirectRunEngine, build_direct_executor_registry
from planner.domain_pack import load_domain_pack
from planner.runtime_event_store import RuntimeEventStore
from planner.execution_planner import plan_runtime
from planner.unified_execution import UnifiedExecutionEngine, build_task_graph_executor_registry
from planner.working_set_store import WorkingSetStore

pack_root = Path({str(VOLUNTEER_PACK_ROOT)!r})
pack = load_domain_pack(pack_root=pack_root, manifest_path="manifest.yaml")
with tempfile.TemporaryDirectory() as raw_temp:
    temp = Path(raw_temp)
    direct = plan_runtime(
        domain_pack=pack,
        question="Inspect one bounded local observation.",
        run_id="blocked-direct",
    )
    working_sets = WorkingSetStore(temp / "tasks")
    task, _ = working_sets.create_task(
        task_id="blocked-task",
        objective="Inspect generated evidence.",
        user_intent="Inspect generated evidence.",
        acceptance_boundary="Generated evidence only.",
        accountable_owner=pack.governance.orchestrator_role,
    )
    DirectRunEngine(
        registry=build_direct_executor_registry(domain_pack=pack),
        run_root=temp / "runs",
        working_sets=working_sets,
    ).run(direct.direct_run, task_id=task.task_id)

    graph = plan_runtime(
        domain_pack=pack,
        question="Explore a counterfactual and competing hypothesis.",
        run_id="blocked-graph",
    )
    store = RuntimeEventStore(temp / "runtime.sqlite3")
    engine = UnifiedExecutionEngine(
        store=store,
        registry=build_task_graph_executor_registry(domain_pack=pack),
        run_root=temp / "runs",
    )
    waiting = engine.run(graph.task_graph)
    assert waiting["status"] == "waiting"
    store.resolve_waiting_node(
        graph.task_graph.run_id,
        "gate.orchestrator-closure",
        actor="Lead",
        decision="approve",
        output={{"decision": "CLOSED"}},
    )
    assert engine.resume(graph.task_graph.run_id)["status"] == "succeeded"
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
