# Quick Start

## Install

```bash
git clone https://github.com/boreaslol/arion-volunteer.git
cd arion-volunteer
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

## Verify the Public Boundary

```bash
python scripts/verify_public_boundary.py
pytest
```

## Plan a Direct Run

```python
from planner.domain_pack import load_domain_pack
from planner.execution_planner import plan_runtime
from volunteer_pack import bundled_pack_root

pack = load_domain_pack(
    pack_root=bundled_pack_root(),
    manifest_path="manifest.yaml",
)
planned = plan_runtime(
    domain_pack=pack,
    question="Inspect one bounded local observation.",
    run_id="direct-example",
)

assert planned.direct_run is not None
print(planned.decision.selected_owner_role)
```

The selected owner is `Data Analyst`.

## Plan a TaskGraph

```python
planned = plan_runtime(
    domain_pack=pack,
    question="Explore a counterfactual and competing hypothesis.",
    run_id="graph-example",
)

assert planned.task_graph is not None
print(planned.decision.active_roles)
```

The active specialist is `Strategy Analyst`; `Lead` remains the human closure
gate.

## Build Your Own Pack

Copy the structure of `volunteer_pack/` and replace generated local methods,
routes, and executors with your own bounded adapters.

Keep business semantics and all access configuration outside this repository.
If your project needs them, place them in a separate governed Pack and keep
secret values in an external secret store.
