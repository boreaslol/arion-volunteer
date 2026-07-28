---
name: implementation-contract-review
description: Bind approved behavior to components, interfaces, failure states, and layered verification before any external action.
---

# Implementation Contract Review

## Use When

- a judgment must become code or configuration;
- several components share one behavior contract;
- failure, retry, timeout, or idempotency semantics matter.

## Inputs

- approved behavior and protected boundaries;
- component and interface map;
- changed, unchanged, and failure paths.

## Procedure

1. Identify the component that owns each state transition.
2. Define inputs, outputs, errors, timeouts, retries, and idempotency.
3. Trace the contract across all changed interfaces.
4. Design local, unit, contract, integration, and parity checks.
5. Record unsupported paths and independent verification requirements.

## Output

An implementation contract, change scope, test matrix, and residual risk.

## Stop Conditions

Do not implement when the approved behavior is ambiguous or when code would
silently redefine the decision.
