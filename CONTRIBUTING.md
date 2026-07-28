# Contributing

Arion Volunteer welcomes small, reviewable contributions to Core contracts,
role boundaries, reusable Skills, local examples, tests, and documentation.

## Before Opening a Pull Request

```bash
python -m pip install -e '.[test]'
python scripts/verify_public_boundary.py
pytest
```

Keep changes bounded and explain:

- which responsibility or contract changes;
- why existing behavior is insufficient;
- what evidence or tests support the change;
- what remains intentionally unresolved.

## Public Boundary

Do not contribute:

- business semantic definitions, metric catalogs, source maps, or field
  dictionaries;
- account configuration, credentials, tokens, sessions, private keys, or
  connection values;
- identifying or proprietary data;
- private infrastructure names, endpoints, paths, incidents, or release
  procedures;
- generated runtime state or model artifacts.

Use generated examples and placeholders. A Skill must state its trigger,
inputs, bounded procedure, outputs, stop conditions, and safety limits.

## Role Changes

Role changes must preserve responsibility conservation. A Skill may help a role
work, but it must not create new authority or collapse independent verification
into implementation.
