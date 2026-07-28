"""Explicit, immutable Domain Pack loading for the Arion core."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from planner.connector_contracts import (
    ConnectorComposition,
    load_connector_composition,
)
from planner.method_pack import (
    MethodPack,
    ResolvedMethodBinding,
    load_method_bindings,
    load_method_pack,
    resolve_method_binding,
    validate_method_pack_identity,
)
from planner.role_registry import (
    GovernanceRegistry,
    compile_governance_registry,
    load_role_registry,
)


DOMAIN_PACK_SCHEMA_VERSION = "1.1"
REQUIRED_MANIFEST_PATH_FIELDS = (
    "role_registry",
    "runtime_policy",
    "role_contracts",
    "route_contracts",
    "executor_bindings",
    "method_pack",
    "method_bindings",
    "connector_contracts",
    "connector_bindings",
)
OPTIONAL_MANIFEST_FILE_FIELDS = ("golden_workflows",)
REQUIRED_MANIFEST_ROOT_FIELDS: tuple[str, ...] = ()
OPTIONAL_MANIFEST_ROOT_FIELDS = (
    "semantic_roots",
    "knowledge_roots",
    "capability_roots",
    "resource_adapters",
    "action_protocol_roots",
)
OPTIONAL_MANIFEST_DOCUMENT_FIELDS = (
    "reference_documents",
    "implementation_files",
)
DOMAIN_PACK_IDENTITY_FIELDS = (
    "schema_version",
    "pack_id",
    "pack_version",
    "manifest",
    "composition_sha256",
)
COMPOSITION_IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
COMPOSITION_IGNORED_FILES = {
    ".DS_Store",
}
COMPOSITION_IGNORED_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"expected Domain Pack mapping: {path}")
    return payload


def _inside_root(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Domain Pack path escapes pack root: {path}") from exc
    return resolved


@dataclass(frozen=True)
class DomainPack:
    root: Path
    manifest_path: Path
    pack_id: str
    pack_version: str
    manifest: dict[str, Any]
    governance: GovernanceRegistry
    method_pack: MethodPack
    method_bindings: dict[str, dict[str, Any]]
    connectors: ConnectorComposition
    paths: dict[str, Path]
    path_groups: dict[str, tuple[Path, ...]]
    composition_sha256: str

    def path(self, field: str) -> Path:
        try:
            return self.paths[field]
        except KeyError as exc:
            raise KeyError(f"Domain Pack does not define path field: {field}") from exc

    @property
    def identity(self) -> dict[str, str]:
        return {
            "schema_version": DOMAIN_PACK_SCHEMA_VERSION,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "manifest": self.manifest_path.relative_to(self.root).as_posix(),
            "composition_sha256": self.composition_sha256,
        }

    @property
    def method_pack_identity(self) -> dict[str, str]:
        return {
            **self.method_pack.identity,
            "manifest": str(self.manifest["method_pack"]),
        }

    def resolved_method_bindings(
        self,
        method_ids: Iterable[str] = (),
    ) -> tuple[ResolvedMethodBinding, ...]:
        selected = tuple(dict.fromkeys(str(value) for value in method_ids))
        unknown = sorted(set(selected) - set(self.method_bindings))
        if unknown:
            raise ValueError(
                "Domain Pack cannot resolve unknown public methods: "
                + ", ".join(unknown)
            )
        return tuple(
            resolve_method_binding(method_id, self.method_bindings[method_id])
            for method_id in selected
        )

    def composition_metadata(
        self,
        *,
        method_ids: Iterable[str] = (),
    ) -> dict[str, Any]:
        resolved_methods = self.resolved_method_bindings(method_ids)
        connector_bindings = tuple(
            dict.fromkeys(
                connector_id
                for binding in resolved_methods
                for connector_id in binding.connector_bindings
            )
        )
        return {
            "domain_pack": self.identity,
            "method_pack": self.method_pack_identity,
            "resolved_method_bindings": [
                binding.to_dict()
                for binding in resolved_methods
            ],
            "connector_bindings": list(connector_bindings),
            "semantic_roots": [
                path.relative_to(self.root).as_posix()
                for path in self.paths_for("semantic_roots")
            ],
        }

    def runtime_metadata(
        self,
        *,
        method_ids: Iterable[str] = (),
    ) -> dict[str, Any]:
        return {
            **self.composition_metadata(method_ids=method_ids),
            "governance_roles": list(self.governance.role_order),
            "orchestrator_role": self.governance.orchestrator_role,
            "role_output_files": dict(self.governance.role_output_files),
        }

    def paths_for(self, field: str) -> tuple[Path, ...]:
        return self.path_groups.get(field, ())

    @property
    def golden_workflows_path(self) -> Path:
        return self.path("golden_workflows")


def validate_domain_pack_identity(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["domain_pack identity is required"]
    issues: list[str] = []
    for field in DOMAIN_PACK_IDENTITY_FIELDS:
        if not isinstance(value.get(field), str) or not value[field].strip():
            issues.append(f"domain_pack.{field} is required")
    if (
        str(value.get("schema_version") or "").strip()
        and value.get("schema_version") != DOMAIN_PACK_SCHEMA_VERSION
    ):
        issues.append(
            "domain_pack.schema_version must be "
            f"{DOMAIN_PACK_SCHEMA_VERSION}"
        )
    manifest = Path(str(value.get("manifest") or ""))
    if manifest.is_absolute() or ".." in manifest.parts:
        issues.append("domain_pack.manifest must be a root-relative path")
    composition_sha256 = str(value.get("composition_sha256") or "")
    if (
        composition_sha256
        and (
            len(composition_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in composition_sha256
            )
        )
    ):
        issues.append(
            "domain_pack.composition_sha256 must be lowercase SHA-256"
        )
    return issues


def validate_composition_metadata(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["composition metadata is required"]
    issues = validate_domain_pack_identity(value.get("domain_pack"))
    issues.extend(validate_method_pack_identity(value.get("method_pack")))
    resolved_methods = value.get("resolved_method_bindings")
    if not isinstance(resolved_methods, list):
        issues.append("resolved_method_bindings must be a list")
        resolved_methods = []
    resolved_connector_bindings: list[str] = []
    resolved_method_ids: list[str] = []
    for index, binding in enumerate(resolved_methods):
        if not isinstance(binding, Mapping):
            issues.append(
                f"resolved_method_bindings[{index}] must be a mapping"
            )
            continue
        method_id = str(binding.get("method_id") or "").strip()
        role_owner = str(binding.get("role_owner") or "").strip()
        binding_sha256 = str(binding.get("binding_sha256") or "").strip()
        required_knowledge = binding.get("required_knowledge")
        method_connectors = binding.get("connector_bindings")
        if not method_id:
            issues.append(
                f"resolved_method_bindings[{index}].method_id is required"
            )
        else:
            resolved_method_ids.append(method_id)
        if not role_owner:
            issues.append(
                f"resolved_method_bindings[{index}].role_owner is required"
            )
        if (
            len(binding_sha256) != 64
            or any(character not in "0123456789abcdef" for character in binding_sha256)
        ):
            issues.append(
                f"resolved_method_bindings[{index}].binding_sha256 "
                "must be lowercase SHA-256"
            )
        for field, values in (
            ("required_knowledge", required_knowledge),
            ("connector_bindings", method_connectors),
        ):
            if not isinstance(values, list) or any(
                not isinstance(item, str) or not item.strip()
                for item in values or []
            ):
                issues.append(
                    f"resolved_method_bindings[{index}].{field} "
                    "must be a list of non-empty strings"
                )
        if isinstance(method_connectors, list):
            resolved_connector_bindings.extend(
                str(item)
                for item in method_connectors
                if isinstance(item, str) and item.strip()
            )
    if len(resolved_method_ids) != len(set(resolved_method_ids)):
        issues.append("resolved_method_bindings must contain unique method ids")
    connector_bindings = value.get("connector_bindings")
    if not isinstance(connector_bindings, list):
        issues.append("connector_bindings must be a list")
    elif (
        any(
            not isinstance(binding_id, str) or not binding_id.strip()
            for binding_id in connector_bindings
        )
        or len(connector_bindings) != len(set(connector_bindings))
    ):
        issues.append("connector_bindings must contain unique non-empty ids")
    elif connector_bindings != list(
        dict.fromkeys(resolved_connector_bindings)
    ):
        issues.append(
            "connector_bindings must exactly match resolved method bindings"
        )
    semantic_roots = value.get("semantic_roots")
    if not isinstance(semantic_roots, list):
        issues.append("semantic_roots must be a list")
    else:
        for semantic_root in semantic_roots:
            path = Path(str(semantic_root or ""))
            if (
                not isinstance(semantic_root, str)
                or not semantic_root.strip()
                or path.is_absolute()
                or ".." in path.parts
            ):
                issues.append(
                    "semantic_roots must contain root-relative paths"
                )
                break
    return issues


def _composition_file_paths(
    *,
    root: Path,
    manifest_path: Path,
    paths: Mapping[str, Path],
    path_groups: Mapping[str, tuple[Path, ...]],
    method_pack: MethodPack,
) -> tuple[Path, ...]:
    selected: dict[str, Path] = {}

    def include(path: Path) -> None:
        resolved = _inside_root(root, path)
        relative = resolved.relative_to(root)
        if (
            any(part in COMPOSITION_IGNORED_DIRECTORIES for part in relative.parts)
            or resolved.name in COMPOSITION_IGNORED_FILES
            or resolved.suffix in COMPOSITION_IGNORED_SUFFIXES
        ):
            return
        selected[relative.as_posix()] = resolved

    include(manifest_path)
    include(method_pack.catalog_path)
    for path in paths.values():
        include(path)
    for group in path_groups.values():
        for root_path in group:
            if root_path.is_file():
                include(root_path)
                continue
            for candidate in root_path.rglob("*"):
                if candidate.is_file():
                    include(candidate)
    return tuple(selected[key] for key in sorted(selected))


def _composition_sha256(
    *,
    root: Path,
    files: Iterable[Path],
) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _resolve_manifest_path(
    *,
    root: Path,
    field: str,
    raw_value: Any,
) -> Path:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError(f"Domain Pack {field} must be a relative path string")
    relative = Path(raw_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Domain Pack {field} must be a root-relative path")
    return _inside_root(root, root / relative)


def load_domain_pack(
    *,
    pack_root: str | Path,
    manifest_path: str | Path,
) -> DomainPack:
    root = Path(pack_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Domain Pack root is not a directory: {root}")
    raw_manifest_path = Path(manifest_path).expanduser()
    if not raw_manifest_path.is_absolute():
        raw_manifest_path = root / raw_manifest_path
    resolved_manifest = _inside_root(root, raw_manifest_path)
    if not resolved_manifest.is_file():
        raise ValueError(f"Domain Pack manifest is missing: {resolved_manifest}")
    manifest = _read_yaml(resolved_manifest)
    if manifest.get("schema_version") != DOMAIN_PACK_SCHEMA_VERSION:
        raise ValueError(
            "Domain Pack schema_version must be "
            f"{DOMAIN_PACK_SCHEMA_VERSION}"
        )
    pack_id = str(manifest.get("pack_id") or "").strip()
    pack_version = str(manifest.get("pack_version") or "").strip()
    if not pack_id:
        raise ValueError("Domain Pack pack_id is required")
    if not pack_version:
        raise ValueError("Domain Pack pack_version is required")

    paths: dict[str, Path] = {}
    for field in (*REQUIRED_MANIFEST_PATH_FIELDS, *OPTIONAL_MANIFEST_FILE_FIELDS):
        raw_value = manifest.get(field)
        if raw_value is None or raw_value == "":
            if field in REQUIRED_MANIFEST_PATH_FIELDS:
                raise ValueError(f"Domain Pack {field} is required")
            continue
        resolved = _resolve_manifest_path(
            root=root,
            field=field,
            raw_value=raw_value,
        )
        if not resolved.is_file():
            raise ValueError(f"Domain Pack {field} is missing: {resolved}")
        paths[field] = resolved

    path_groups: dict[str, tuple[Path, ...]] = {}
    for field in (
        *REQUIRED_MANIFEST_ROOT_FIELDS,
        *OPTIONAL_MANIFEST_ROOT_FIELDS,
        *OPTIONAL_MANIFEST_DOCUMENT_FIELDS,
    ):
        raw_values = manifest.get(field)
        if raw_values is None:
            if field in REQUIRED_MANIFEST_ROOT_FIELDS:
                raise ValueError(f"Domain Pack {field} is required")
            continue
        if not isinstance(raw_values, list) or (
            field in REQUIRED_MANIFEST_ROOT_FIELDS and not raw_values
        ):
            requirement = "a non-empty list" if field in REQUIRED_MANIFEST_ROOT_FIELDS else "a list"
            raise ValueError(f"Domain Pack {field} must be {requirement}")
        resolved_values: list[Path] = []
        for index, raw_value in enumerate(raw_values):
            resolved = _resolve_manifest_path(
                root=root,
                field=f"{field}[{index}]",
                raw_value=raw_value,
            )
            if field in (
                *REQUIRED_MANIFEST_ROOT_FIELDS,
                *OPTIONAL_MANIFEST_ROOT_FIELDS,
            ) and not resolved.is_dir():
                raise ValueError(
                    f"Domain Pack {field}[{index}] is not a directory: {resolved}"
                )
            if (
                field in OPTIONAL_MANIFEST_DOCUMENT_FIELDS
                and not resolved.is_file()
            ):
                raise ValueError(
                    f"Domain Pack {field}[{index}] is not a file: {resolved}"
                )
            resolved_values.append(resolved)
        path_groups[field] = tuple(resolved_values)

    role_registry = load_role_registry(paths["role_registry"])
    governance = compile_governance_registry(
        role_registry,
        registry_reference=str(manifest["role_registry"]),
    )
    method_pack = load_method_pack(
        pack_root=paths["method_pack"].parent,
        manifest_path=paths["method_pack"].name,
    )
    method_bindings = load_method_bindings(
        paths["method_bindings"],
        method_pack=method_pack,
    )
    missing_method_bindings = sorted(
        set(method_pack.methods) - set(method_bindings)
    )
    if missing_method_bindings:
        raise ValueError(
            "Domain Pack method bindings are missing public methods: "
            + ", ".join(missing_method_bindings)
        )
    governed_role_ids = {
        str(role.get("id") or "").strip()
        for role in role_registry["roles"]
        if isinstance(role, dict)
    }
    unknown_method_owners = sorted(
        {
            str(binding.get("role_owner") or "").strip()
            for binding in method_bindings.values()
        }
        - governed_role_ids
    )
    if unknown_method_owners:
        raise ValueError(
            "Domain Pack method bindings reference unknown role owners: "
            + ", ".join(unknown_method_owners)
        )
    connectors = load_connector_composition(
        contracts_path=paths["connector_contracts"],
        bindings_path=paths["connector_bindings"],
    )
    unknown_connector_bindings = sorted(
        {
            str(connector_binding)
            for binding in method_bindings.values()
            for connector_binding in binding["connector_bindings"]
        }
        - set(connectors.bindings)
    )
    if unknown_connector_bindings:
        raise ValueError(
            "Domain Pack methods reference unknown connector bindings: "
            + ", ".join(unknown_connector_bindings)
        )
    composition_sha256 = _composition_sha256(
        root=root,
        files=_composition_file_paths(
            root=root,
            manifest_path=resolved_manifest,
            paths=paths,
            path_groups=path_groups,
            method_pack=method_pack,
        ),
    )
    return DomainPack(
        root=root,
        manifest_path=resolved_manifest,
        pack_id=pack_id,
        pack_version=pack_version,
        manifest=manifest,
        governance=governance,
        method_pack=method_pack,
        method_bindings=method_bindings,
        connectors=connectors,
        paths=paths,
        path_groups=path_groups,
        composition_sha256=composition_sha256,
    )
