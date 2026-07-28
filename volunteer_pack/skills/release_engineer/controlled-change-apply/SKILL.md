---
name: controlled-change-apply
description: Prepare or execute an explicitly approved, immutable, reversible change while preserving provenance and stop conditions.
---

# Controlled Change Apply

## Use When

- an authorized environment has approved a bounded change;
- the immutable unit, rollback target, and verifier are known;
- apply evidence must be captured.

## Inputs

- explicit authorization and approved action packet;
- immutable source or artifact identity;
- rollback target, health checks, and stop conditions.

## Procedure

1. Reconfirm scope, target, identity, and authority.
2. Verify the rollback target is available before action.
3. Execute only the approved steps in order.
4. Stop on identity, health, or contract mismatch.
5. Record commands or API actions, timestamps, results, and deviations.
6. Hand the target to an independent verifier.

## Output

Apply result, provenance, rollback readiness, and verifier handoff.

## Stop Conditions

This public Pack grants no external write authority. Stop when authorization,
identity, rollback, or independent verification is missing.
