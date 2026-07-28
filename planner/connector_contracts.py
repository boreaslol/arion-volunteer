"""Public Connector contracts and private binding validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from planner.secret_refs import parse_secret_ref


CONNECTOR_SCHEMA_VERSION = "1.0"
CONNECTOR_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
FORBIDDEN_RESOURCE_KEY_TOKENS = {
    "api_key",
    "credential",
    "password",
    "secret",
    "token",
}
CONNECTOR_CONTRACT_FIELDS = {
    "id",
    "capability",
    "side_effect_class",
    "resource_slots",
    "secret_slots",
}
CONNECTOR_BINDING_FIELDS = {
    "id",
    "connector_id",
    "resources",
    "secret_refs",
}
CONNECTOR_SIDE_EFFECT_CLASSES = {
    "none",
    "local_read",
    "local_write",
    "governed_remote_action",
}
CONNECTOR_SLOT_FIELDS = {"id", "required"}


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"expected Connector mapping: {path}")
    return payload


def _slot_map(value: Any, *, connector_id: str, field: str) -> dict[str, bool]:
    if not isinstance(value, list):
        raise ValueError(f"connector[{connector_id}].{field} must be a list")
    slots: dict[str, bool] = {}
    for index, raw_slot in enumerate(value):
        if not isinstance(raw_slot, dict):
            raise ValueError(
                f"connector[{connector_id}].{field}[{index}] must be a mapping"
            )
        unsupported = sorted(set(raw_slot) - CONNECTOR_SLOT_FIELDS)
        if unsupported:
            raise ValueError(
                f"connector[{connector_id}].{field}[{index}] contains "
                "unsupported fields: "
                + ", ".join(unsupported)
            )
        slot_id = str(raw_slot.get("id") or "").strip()
        if not CONNECTOR_ID_PATTERN.fullmatch(slot_id):
            raise ValueError(
                f"connector[{connector_id}].{field}[{index}].id is invalid"
            )
        if slot_id in slots:
            raise ValueError(
                f"connector[{connector_id}].{field} contains duplicate {slot_id}"
            )
        required = raw_slot.get("required")
        if not isinstance(required, bool):
            raise ValueError(
                f"connector[{connector_id}].{field}[{index}].required "
                "must be boolean"
            )
        slots[slot_id] = required
    return slots


@dataclass(frozen=True)
class ConnectorComposition:
    contracts_path: Path
    bindings_path: Path
    contracts: dict[str, dict[str, Any]]
    bindings: dict[str, dict[str, Any]]

    @property
    def binding_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.bindings))


def load_connector_composition(
    *,
    contracts_path: str | Path,
    bindings_path: str | Path,
) -> ConnectorComposition:
    resolved_contracts = Path(contracts_path).expanduser().resolve()
    resolved_bindings = Path(bindings_path).expanduser().resolve()
    contract_payload = _read_yaml(resolved_contracts)
    binding_payload = _read_yaml(resolved_bindings)
    if contract_payload.get("schema_version") != CONNECTOR_SCHEMA_VERSION:
        raise ValueError("Connector contracts schema_version must be 1.0")
    if binding_payload.get("schema_version") != CONNECTOR_SCHEMA_VERSION:
        raise ValueError("Connector bindings schema_version must be 1.0")

    raw_contracts = contract_payload.get("connectors")
    if not isinstance(raw_contracts, list) or not raw_contracts:
        raise ValueError("Connector contracts must contain connectors")
    contracts: dict[str, dict[str, Any]] = {}
    slot_contracts: dict[str, tuple[dict[str, bool], dict[str, bool]]] = {}
    for index, raw_contract in enumerate(raw_contracts):
        if not isinstance(raw_contract, dict):
            raise ValueError(f"connectors[{index}] must be a mapping")
        contract = dict(raw_contract)
        connector_id = str(contract.get("id") or "").strip()
        if not CONNECTOR_ID_PATTERN.fullmatch(connector_id):
            raise ValueError(f"connectors[{index}].id is invalid: {connector_id!r}")
        if connector_id in contracts:
            raise ValueError(f"duplicate connector contract: {connector_id}")
        unsupported = sorted(set(contract) - CONNECTOR_CONTRACT_FIELDS)
        if unsupported:
            raise ValueError(
                f"connector[{connector_id}] contains unsupported fields: "
                + ", ".join(unsupported)
            )
        capability = str(contract.get("capability") or "").strip()
        if not capability:
            raise ValueError(f"connector[{connector_id}].capability is required")
        side_effect_class = str(
            contract.get("side_effect_class") or ""
        ).strip()
        if side_effect_class not in CONNECTOR_SIDE_EFFECT_CLASSES:
            raise ValueError(
                f"connector[{connector_id}].side_effect_class is unsupported: "
                f"{side_effect_class}"
            )
        resource_slots = _slot_map(
            contract.get("resource_slots"),
            connector_id=connector_id,
            field="resource_slots",
        )
        secret_slots = _slot_map(
            contract.get("secret_slots"),
            connector_id=connector_id,
            field="secret_slots",
        )
        contracts[connector_id] = contract
        slot_contracts[connector_id] = (resource_slots, secret_slots)

    raw_bindings = binding_payload.get("bindings")
    if not isinstance(raw_bindings, list):
        raise ValueError("Connector bindings must contain a bindings list")
    bindings: dict[str, dict[str, Any]] = {}
    for index, raw_binding in enumerate(raw_bindings):
        if not isinstance(raw_binding, dict):
            raise ValueError(f"bindings[{index}] must be a mapping")
        binding = dict(raw_binding)
        binding_id = str(binding.get("id") or "").strip()
        connector_id = str(binding.get("connector_id") or "").strip()
        if not CONNECTOR_ID_PATTERN.fullmatch(binding_id):
            raise ValueError(f"bindings[{index}].id is invalid: {binding_id!r}")
        if binding_id in bindings:
            raise ValueError(f"duplicate connector binding: {binding_id}")
        unsupported = sorted(set(binding) - CONNECTOR_BINDING_FIELDS)
        if unsupported:
            raise ValueError(
                f"connector binding[{binding_id}] contains unsupported fields: "
                + ", ".join(unsupported)
            )
        if connector_id not in contracts:
            raise ValueError(
                f"connector binding[{binding_id}] references unknown contract: "
                f"{connector_id}"
            )
        resources = binding.get("resources") or {}
        secret_refs = binding.get("secret_refs") or {}
        if not isinstance(resources, dict):
            raise ValueError(
                f"connector binding[{binding_id}].resources must be a mapping"
            )
        if not isinstance(secret_refs, dict):
            raise ValueError(
                f"connector binding[{binding_id}].secret_refs must be a mapping"
            )
        forbidden_resource_keys = {
            str(key)
            for key in resources
            if any(
                token in str(key).casefold()
                for token in FORBIDDEN_RESOURCE_KEY_TOKENS
            )
        }
        if forbidden_resource_keys:
            raise ValueError(
                f"connector binding[{binding_id}] puts credentials in resources: "
                + ", ".join(sorted(forbidden_resource_keys))
            )
        invalid_resource_values = sorted(
            str(key)
            for key, value in resources.items()
            if not isinstance(value, str) or not value.strip()
        )
        if invalid_resource_values:
            raise ValueError(
                f"connector binding[{binding_id}] has invalid resource values: "
                + ", ".join(invalid_resource_values)
            )
        authenticated_resources = sorted(
            str(key)
            for key, value in resources.items()
            if isinstance(value, str)
            and "://" in value
            and "@" in value.split("://", 1)[1]
        )
        if authenticated_resources:
            raise ValueError(
                f"connector binding[{binding_id}] contains authenticated "
                "resource values: "
                + ", ".join(authenticated_resources)
            )
        resource_slots, secret_slots = slot_contracts[connector_id]
        unknown_resources = sorted(set(resources) - set(resource_slots))
        unknown_secrets = sorted(set(secret_refs) - set(secret_slots))
        if unknown_resources:
            raise ValueError(
                f"connector binding[{binding_id}] has unknown resource slots: "
                + ", ".join(unknown_resources)
            )
        if unknown_secrets:
            raise ValueError(
                f"connector binding[{binding_id}] has unknown secret slots: "
                + ", ".join(unknown_secrets)
            )
        missing_resources = sorted(
            slot
            for slot, required in resource_slots.items()
            if required and not str(resources.get(slot) or "").strip()
        )
        missing_secrets = sorted(
            slot
            for slot, required in secret_slots.items()
            if required and not str(secret_refs.get(slot) or "").strip()
        )
        if missing_resources:
            raise ValueError(
                f"connector binding[{binding_id}] misses resource slots: "
                + ", ".join(missing_resources)
            )
        if missing_secrets:
            raise ValueError(
                f"connector binding[{binding_id}] misses secret refs: "
                + ", ".join(missing_secrets)
            )
        for slot, secret_ref in secret_refs.items():
            try:
                parse_secret_ref(secret_ref)
            except ValueError as exc:
                raise ValueError(
                    f"connector binding[{binding_id}].secret_refs.{slot} "
                    "must be an external profile reference"
                ) from exc
        bindings[binding_id] = binding

    return ConnectorComposition(
        contracts_path=resolved_contracts,
        bindings_path=resolved_bindings,
        contracts=contracts,
        bindings=bindings,
    )
