# Public Boundary

Arion Volunteer is assembled with a fresh Git history and a default-deny
privacy posture.

## Included

- Arion Core planning and execution contracts;
- public role-neutral methods;
- generic governance roles and Skills;
- generated local evidence and tests;
- safety and boundary validation.

## Excluded

- business semantic layers, metric/source/field/dimension definitions;
- account profiles and all secret values;
- personal, customer, company, or proprietary data;
- internal hostnames, network addresses, local machine paths, and private
  operating history;
- production connectors, deployment procedures, runtime state, models, and
  artifacts;
- inherited private repository history.

## Automated Gates

`scripts/verify_public_boundary.py` verifies:

- the Volunteer Pack has an empty `semantic_roots` list;
- no semantic-layer directory exists;
- public Connector bindings contain no secret reference values;
- role instructions and Skill files exist;
- obvious private-network, machine-path, internal-domain, and credential
  patterns do not appear.

CI also runs the test suite, dependency audit, and complete-history Gitleaks
scan.

Automated checks reduce risk but do not replace human review of licensing,
copyright ownership, and contextual privacy.
