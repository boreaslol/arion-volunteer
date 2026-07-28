# Roles and Skills

## Responsibility Model

Roles answer irreducible questions. Skills describe reusable ways to answer
them. A Skill does not become a role and does not grant permission.

| Role | Primary question | Core Skill |
|---|---|---|
| Lead | What judgment remains accountable? | `judgment-closure` |
| Data Analyst | What does the evidence support? | `evidence-boundary-review` |
| Strategy Analyst | Which action worlds matter? | `counterfactual-policy-review` |
| Anti-Fraud Specialist | How could an adversary adapt? | `adversarial-adaptation-review` |
| Model Engineer | Where is model uncertainty understated? | `model-uncertainty-review` |
| Risk Platform Engineer | Does implementation preserve the contract? | `implementation-contract-review` |
| Release Engineer | Can the approved change be applied reversibly? | `controlled-change-apply` |
| Release Verifier | Does independent evidence support the claim? | `independent-change-verification` |

Shared Skills provide bounded task routing, evidence packaging, and a data
quality gate.

## Skill Contract

Every public Skill states:

- when it applies;
- required inputs;
- a bounded procedure;
- expected output;
- stop conditions and safety limits.

The canonical references live in `volunteer_pack/roles.yaml` and
`volunteer_pack/role_contracts.yaml`. Human-readable role instructions live in
`volunteer_pack/roles/`; Skills live in `volunteer_pack/skills/`.

## Activation

The registry stays fixed. The planner uses the current question and Working Set
to activate roles.

Examples:

- a bounded observation defaults to `Data Analyst`;
- a counterfactual activates `Strategy Analyst`;
- an adversarial or evasion question activates `Anti-Fraud Specialist`;
- model calibration or drift activates `Model Engineer`;
- an interface-failure question activates `Risk Platform Engineer`;
- a controlled-change plan activates `Release Engineer`;
- independent verification activates `Release Verifier`.

`Lead` remains the closure owner and does not replace specialist work.
