# Public Risk Methods

This catalog contains transferable method contracts that grew out of
risk-management work without carrying company definitions, data locations,
account configuration, or private operating history.

Each method states:

- the question it investigates;
- required evidence;
- bounded outputs;
- whether an implementation adapter is required.

Methods remain role-neutral. `volunteer_pack/method_bindings.yaml` assigns a
method to a governance role and a local Connector for the included example.

No business semantic layer is shipped. Downstream projects may bind these
methods to their own separately governed definitions and adapters.
