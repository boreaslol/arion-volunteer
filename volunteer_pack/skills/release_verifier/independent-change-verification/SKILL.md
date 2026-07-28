---
name: independent-change-verification
description: Independently verify candidate identity, observed behavior, unchanged paths, and residual risk without repairing the target.
---

# Independent Change Verification

## Use When

- a candidate is ready for preflight;
- an authorized change has been applied;
- rollback or recovery claims require independent evidence.

## Inputs

- approved contract and immutable intended identity;
- candidate or observed target;
- changed-path, unchanged-path, health, and behavior probes.

## Procedure

1. Confirm verifier independence and read-only scope.
2. Compare intended and observed identities.
3. Verify changed behavior and critical unchanged behavior.
4. Check failure paths, health, observability, and rollback readiness.
5. Separate system failure, validator failure, and missing evidence.
6. Report pass, fail, or blocked with residual risk.

## Output

Verification result, exact evidence, mismatches, uncovered paths, and retry
conditions.

## Stop Conditions

Do not modify the candidate, target, or expected result. A repair requires a
new candidate and a new verification cycle.
