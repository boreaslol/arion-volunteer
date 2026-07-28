# Arion Volunteer

[简体中文](README.zh-CN.md)

> **Reality provides experience; counterfactuals produce agency.**

Arion Volunteer combines the [Arion Judgment Core](https://github.com/boreaslol/arion-core)
with an open eight-role governance model and a reusable Skill catalog.

It is a small framework for organizing how a collective judgment forms,
remains accountable, accepts challenge, and changes when reality contradicts
it. Roles keep responsibility stable; temporary Agent instances investigate
only the unresolved questions that matter in the current Run.

## What Ships

- the current Arion planning and execution Core;
- eight governance roles with explicit responsibility boundaries;
- eleven reusable `SKILL.md` operating methods;
- a local Volunteer Pack with role-neutral methods, routes, and generated
  evidence;
- tests for planning, parallel Agents, closure, role assets, and the public
  privacy boundary.

## What Does Not Ship

- no business semantic layer, metric catalog, source definitions, or field
  dictionary;
- no account profiles, credentials, tokens, sessions, private keys, or secret
  values;
- no company data, customer data, private knowledge, internal endpoints, or
  production adapters;
- no runtime state, model artifacts, deployment packages, or inherited private
  Git history.

The included Pack declares `semantic_roots: []` and its only Connector reads
generated local evidence with no secret slots.

## Eight Roles

| Role | Irreducible responsibility |
|---|---|
| Lead | Own the bounded collective judgment and closure |
| Data Analyst | Establish what the evidence actually supports |
| Strategy Analyst | Compare action counterfactuals and tradeoffs |
| Anti-Fraud Specialist | Test adversarial adaptation and evasion |
| Model Engineer | Bound model uncertainty and failure |
| Risk Platform Engineer | Preserve the judgment contract in implementation |
| Release Engineer | Prepare or apply an explicitly approved reversible change |
| Release Verifier | Independently verify the change claim |

Not every task activates every role. Core creates one Direct Run for one
bounded assignment and a TaskGraph only for real parallelism, dependency,
waiting, retry, or governed action.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python scripts/verify_public_boundary.py
pytest
```

```python
from pathlib import Path

from planner.domain_pack import load_domain_pack
from planner.execution_planner import plan_runtime

pack = load_domain_pack(
    pack_root=Path("volunteer_pack"),
    manifest_path="manifest.yaml",
)
planned = plan_runtime(
    domain_pack=pack,
    question="Explore a counterfactual and competing hypothesis.",
    run_id="example-run",
)

print(planned.orchestration_mode)
print(planned.decision.active_roles)
```

This question activates `Strategy Analyst` and leaves `Lead` as the accountable
closure gate.

## Project Map

| Path | Purpose |
|---|---|
| `planner/` | Task, Working Set, Direct Run, TaskGraph, role activation, execution, and safety |
| `risk_methods/` | Public role-neutral method contracts |
| `volunteer_pack/roles/` | Human-readable governance-role instructions |
| `volunteer_pack/skills/` | Reusable role and team Skills |
| `volunteer_pack/*.yaml` | Runnable role, route, method, Connector, and executor composition |
| `tests/` | Core, Pack, role-asset, privacy, and closure verification |

Read [Architecture](docs/architecture.md), [Roles and Skills](docs/roles-and-skills.md),
[Quick Start](docs/quickstart.md), and [Public Boundary](docs/public-boundary.md)
for the complete contract.

## Safety

Arion Volunteer defaults to local execution and does not grant external write
authority. Release roles model responsibility boundaries; another project must
provide its own explicit authorization, adapters, and independent controls.

Every change is expected to pass tests, dependency auditing, public-boundary
checks, and complete-history secret scanning.

## License

Apache License 2.0.
