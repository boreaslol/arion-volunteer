---
name: bounded-task-routing
description: Compile an open request into a bounded Arion task and activate only the roles needed by unresolved questions.
---

# Bounded Task Routing

## Use When

- a new request enters Arion;
- the objective or acceptance boundary is ambiguous;
- several roles could contribute, but not all are needed.

## Inputs

- user intent;
- known constraints and available evidence;
- current Working Set, when one exists.

## Procedure

1. State the objective in one falsifiable sentence.
2. Record what is in scope, out of scope, and safety-critical.
3. Separate knowns, unknowns, assumptions, and requested actions.
4. Map each unresolved irreducible question to one governance role.
5. Use Direct Run for one bounded assignment; use TaskGraph only for real
   parallelism, dependency, waiting, retry, or governed action.
6. Define acceptance evidence and at least one revision trigger.

## Output

A task contract, selected roles, orchestration mode, and unresolved items.

## Stop Conditions

Stop when the objective cannot be bounded without a missing user decision or
when the requested action exceeds the available authority.
