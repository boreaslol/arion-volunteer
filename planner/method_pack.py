"""Public analytical-method pack contracts for Arion composition."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

import yaml


METHOD_PACK_SCHEMA_VERSION = "1.0"
METHOD_CATALOG_SCHEMA_VERSION = "1.0"
METHOD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
METHOD_IMPLEMENTATION_STATES = {
    "contract_only",
    "adapter_required",
    "executable",
}
FORBIDDEN_PUBLIC_METHOD_FIELDS = {
    "credential",
    "credential_ref",
    "endpoint",
    "required_knowledge",
    "resource_id",
    "role_owner",
    "secret",
    "secret_ref",
    "shared_modules",
}
PUBLIC_METHOD_FIELDS = {
    "id",
    "status",
    "summary",
    "intent_tags",
    "inputs",
    "outputs",
    "implementation",
}
PRIVATE_METHOD_BINDING_FIELDS = {
    "method_id",
    "role_owner",
    "required_knowledge",
    "default_outputs",
    "entry_signals",
    "shared_modules",
    "handoff_targets",
    "handoff_conditions",
    "connector_bindings",
}
METHOD_PACK_IDENTITY_FIELDS = (
    "schema_version",
    "pack_id",
    "pack_version",
    "manifest",
    "content_sha256",
)


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"expected Method Pack mapping: {path}")
    return payload


def _inside_root(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Method Pack path escapes pack root: {path}") from exc
    return resolved


def _relative_file(root: Path, value: Any, *, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Method Pack {field} must be a relative path string")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Method Pack {field} must be root-relative")
    resolved = _inside_root(root, root / relative)
    if not resolved.is_file():
        raise ValueError(f"Method Pack {field} is missing: {resolved}")
    return resolved


def _string_list(value: Any, *, field: str, method_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"method[{method_id}].{field} must be a non-empty list"
        )
    normalized = tuple(str(item).strip() for item in value)
    if any(not item for item in normalized):
        raise ValueError(f"method[{method_id}].{field} contains an empty value")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"method[{method_id}].{field} must be unique")
    return normalized


@dataclass(frozen=True)
class MethodPack:
    root: Path
    manifest_path: Path
    catalog_path: Path
    pack_id: str
    pack_version: str
    methods: dict[str, dict[str, Any]]
    content_sha256: str

    @property
    def identity(self) -> dict[str, str]:
        return {
            "schema_version": METHOD_PACK_SCHEMA_VERSION,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "manifest": self.manifest_path.relative_to(self.root).as_posix(),
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True)
class ResolvedMethodBinding:
    method_id: str
    role_owner: str
    required_knowledge: tuple[str, ...]
    connector_bindings: tuple[str, ...]
    binding_sha256: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_knowledge"] = list(self.required_knowledge)
        payload["connector_bindings"] = list(self.connector_bindings)
        return payload


def _content_sha256(root: Path, paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_method_binding(
    method_id: str,
    binding: Mapping[str, Any],
) -> ResolvedMethodBinding:
    canonical = json.dumps(
        dict(binding),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ResolvedMethodBinding(
        method_id=method_id,
        role_owner=str(binding.get("role_owner") or "").strip(),
        required_knowledge=tuple(
            str(value)
            for value in binding.get("required_knowledge", []) or []
        ),
        connector_bindings=tuple(
            str(value)
            for value in binding.get("connector_bindings", []) or []
        ),
        binding_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def validate_method_pack_identity(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["method_pack identity is required"]
    issues: list[str] = []
    for field in METHOD_PACK_IDENTITY_FIELDS:
        if not isinstance(value.get(field), str) or not value[field].strip():
            issues.append(f"method_pack.{field} is required")
    if (
        str(value.get("schema_version") or "").strip()
        and value.get("schema_version") != METHOD_PACK_SCHEMA_VERSION
    ):
        issues.append(
            "method_pack.schema_version must be "
            f"{METHOD_PACK_SCHEMA_VERSION}"
        )
    manifest = Path(str(value.get("manifest") or ""))
    if manifest.is_absolute() or ".." in manifest.parts:
        issues.append("method_pack.manifest must be a root-relative path")
    content_sha256 = str(value.get("content_sha256") or "")
    if (
        content_sha256
        and (
            len(content_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in content_sha256
            )
        )
    ):
        issues.append("method_pack.content_sha256 must be lowercase SHA-256")
    return issues


def load_method_pack(
    *,
    pack_root: str | Path,
    manifest_path: str | Path,
) -> MethodPack:
    root = Path(pack_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Method Pack root is not a directory: {root}")
    raw_manifest = Path(manifest_path).expanduser()
    if not raw_manifest.is_absolute():
        raw_manifest = root / raw_manifest
    resolved_manifest = _inside_root(root, raw_manifest)
    if not resolved_manifest.is_file():
        raise ValueError(f"Method Pack manifest is missing: {resolved_manifest}")
    manifest = _read_yaml(resolved_manifest)
    if manifest.get("schema_version") != METHOD_PACK_SCHEMA_VERSION:
        raise ValueError(
            "Method Pack schema_version must be "
            f"{METHOD_PACK_SCHEMA_VERSION}"
        )
    pack_id = str(manifest.get("pack_id") or "").strip()
    pack_version = str(manifest.get("pack_version") or "").strip()
    if not pack_id:
        raise ValueError("Method Pack pack_id is required")
    if not pack_version:
        raise ValueError("Method Pack pack_version is required")
    catalog_path = _relative_file(
        root,
        manifest.get("catalog"),
        field="catalog",
    )
    catalog = _read_yaml(catalog_path)
    if catalog.get("schema_version") != METHOD_CATALOG_SCHEMA_VERSION:
        raise ValueError(
            "Method catalog schema_version must be "
            f"{METHOD_CATALOG_SCHEMA_VERSION}"
        )
    raw_methods = catalog.get("methods")
    if not isinstance(raw_methods, list) or not raw_methods:
        raise ValueError("Method catalog methods must be a non-empty list")

    methods: dict[str, dict[str, Any]] = {}
    for index, raw_method in enumerate(raw_methods):
        if not isinstance(raw_method, dict):
            raise ValueError(f"methods[{index}] must be a mapping")
        method = dict(raw_method)
        method_id = str(method.get("id") or "").strip()
        if not METHOD_ID_PATTERN.fullmatch(method_id):
            raise ValueError(f"methods[{index}].id is invalid: {method_id!r}")
        if method_id in methods:
            raise ValueError(f"duplicate public method id: {method_id}")
        forbidden = sorted(FORBIDDEN_PUBLIC_METHOD_FIELDS & set(method))
        if forbidden:
            raise ValueError(
                f"method[{method_id}] contains private binding fields: "
                + ", ".join(forbidden)
            )
        unsupported = sorted(set(method) - PUBLIC_METHOD_FIELDS)
        if unsupported:
            raise ValueError(
                f"method[{method_id}] contains unsupported fields: "
                + ", ".join(unsupported)
            )
        status = str(method.get("status") or "").strip()
        if status not in {"active", "experimental"}:
            raise ValueError(f"method[{method_id}].status is unsupported: {status}")
        implementation = str(method.get("implementation") or "").strip()
        if implementation not in METHOD_IMPLEMENTATION_STATES:
            raise ValueError(
                f"method[{method_id}].implementation is unsupported: "
                f"{implementation}"
            )
        summary = str(method.get("summary") or "").strip()
        if not summary:
            raise ValueError(f"method[{method_id}].summary is required")
        method["intent_tags"] = list(
            _string_list(
                method.get("intent_tags"),
                field="intent_tags",
                method_id=method_id,
            )
        )
        method["inputs"] = list(
            _string_list(
                method.get("inputs"),
                field="inputs",
                method_id=method_id,
            )
        )
        method["outputs"] = list(
            _string_list(
                method.get("outputs"),
                field="outputs",
                method_id=method_id,
            )
        )
        methods[method_id] = method

    return MethodPack(
        root=root,
        manifest_path=resolved_manifest,
        catalog_path=catalog_path,
        pack_id=pack_id,
        pack_version=pack_version,
        methods=methods,
        content_sha256=_content_sha256(
            root,
            (resolved_manifest, catalog_path),
        ),
    )


def load_method_bindings(
    path: str | Path,
    *,
    method_pack: MethodPack,
) -> dict[str, dict[str, Any]]:
    binding_path = Path(path).expanduser().resolve()
    payload = _read_yaml(binding_path)
    if payload.get("schema_version") != "1.0":
        raise ValueError("Method bindings schema_version must be 1.0")
    raw_bindings = payload.get("bindings")
    if not isinstance(raw_bindings, list):
        raise ValueError("Method bindings must contain a bindings list")
    bindings: dict[str, dict[str, Any]] = {}
    for index, raw_binding in enumerate(raw_bindings):
        if not isinstance(raw_binding, dict):
            raise ValueError(f"method bindings[{index}] must be a mapping")
        binding = dict(raw_binding)
        method_id = str(binding.get("method_id") or "").strip()
        if method_id not in method_pack.methods:
            raise ValueError(
                f"method binding references unknown public method: {method_id}"
            )
        if method_id in bindings:
            raise ValueError(f"duplicate method binding: {method_id}")
        unsupported = sorted(set(binding) - PRIVATE_METHOD_BINDING_FIELDS)
        if unsupported:
            raise ValueError(
                f"method binding[{method_id}] contains unsupported fields: "
                + ", ".join(unsupported)
            )
        for field in (
            "role_owner",
            "required_knowledge",
            "connector_bindings",
        ):
            if field not in binding:
                raise ValueError(f"method binding[{method_id}].{field} is required")
        for field in ("required_knowledge", "connector_bindings"):
            if not isinstance(binding[field], list):
                raise ValueError(
                    f"method binding[{method_id}].{field} must be a list"
                )
        forbidden_keys = {
            key
            for key in binding
            if any(
                token in key.casefold()
                for token in ("password", "secret_value", "access_token", "api_key")
            )
        }
        if forbidden_keys:
            raise ValueError(
                f"method binding[{method_id}] contains credential fields: "
                + ", ".join(sorted(forbidden_keys))
            )
        bindings[method_id] = binding
    return bindings
