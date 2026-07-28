# Architecture

## Composition

Arion Volunteer has three public layers:

```text
Role-neutral Methods ----\
                          > Volunteer Pack -> Arion Core -> local Runtime
Roles + Skills + Routes -/
```

`planner/` owns the stable execution kernel. `volunteer_pack/` supplies one
explicit governance assembly. `risk_methods/` supplies methods that remain
independent from role ownership.

## Core State

Core keeps six long-lived concepts:

- **Task:** objective, boundary, owner, and lifecycle;
- **Working Set:** knowns, unknowns, assumptions, hypotheses, counterfactuals,
  consequences, judgment, obligations, and revision triggers;
- **Run:** one bounded attempt to revise the Working Set;
- **Resource:** an external object whose state may change;
- **Artifact:** a stable, inspectable output or evidence snapshot;
- **Knowledge:** durable memory that can change a future judgment.

Execution success does not close a Task. Closure must dispose open items
explicitly and preserve future observation obligations.

## Roles and Agent Instances

The eight governance roles are stable responsibility contracts. Agent
instances are temporary executors.

The planner activates only roles that own unresolved questions. Multiple
independent open items for one role may create multiple parallel Agent
instances without creating new governance roles.

## Direct Run and TaskGraph

Direct Run is the default for one bounded assignment.

TaskGraph appears only for:

- parallel assignments;
- explicit dependencies;
- waiting or human gates;
- retries and recovery;
- governed actions requiring independent stages.

## Pack Contract

The Pack declares:

- role registry and question contracts;
- runtime and route policy;
- public methods and role bindings;
- Connector contracts and local bindings;
- executor bindings;
- optional extension roots.

Business semantics are an optional external extension. This repository ships
no semantic definitions and declares `semantic_roots: []`.

The included Connector has no secret slots and reads only generated local
evidence. Core can validate secret references for downstream projects, but no
account profile or secret value is included here.

## Safety

Core rejects recognized credential material from durable runtime state and
defaults to local side effects. The public Pack cannot grant external write
authority.

Implementation, apply, and independent verification remain separate
responsibilities. A downstream adapter may narrow safety further; it must not
weaken the Core boundary.
