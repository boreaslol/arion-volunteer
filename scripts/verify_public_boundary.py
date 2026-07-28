#!/usr/bin/env python3
"""Verify that Arion Volunteer stays inside its public release boundary."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
TEXT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
FORBIDDEN_PATH_PARTS = {
    "accounts",
    "credentials",
    "semantic_layer",
    "semantics",
}
FORBIDDEN_FILE_NAMES = {
    ".env",
    ".env.local",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
}
CONTENT_PATTERNS = {
    "private_network": re.compile(
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
    ),
    "internal_domain": re.compile(
        r"(?i)\b[a-z0-9][a-z0-9.-]*\.(?:internal|lo)\b"
    ),
    "machine_local_path": re.compile(
        r"/(?:Users|home)/[^/\s]+/"
    ),
    "credential_assignment": re.compile(
        r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|"
        r"client[_-]?secret|secret[_-]?key)\b\s*[:=]\s*"
        r"[\"'][^<${\n][^\"'\n]{2,}[\"']"
    ),
}
PRIVATE_IDENTIFIERS = (
    "no" + "ro",
    "risk-" + "control",
    "risk" + "model",
    "jump" + "server",
    "jupyter-" + "mx",
    "uru" + "le",
)


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"expected mapping: {path.relative_to(ROOT)}")
    return payload


def _public_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                path
                for path in ROOT.rglob("*")
                if path.is_file()
                and not any(part in SKIP_DIRECTORIES for part in path.parts)
            ),
            key=lambda path: path.relative_to(ROOT).as_posix(),
        )
    )


def validate_public_boundary() -> list[str]:
    errors: list[str] = []
    files = _public_files()

    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        relative = path.relative_to(ROOT)
        forbidden_parts = set(relative.parts) & FORBIDDEN_PATH_PARTS
        if forbidden_parts:
            errors.append(
                f"forbidden private path {sorted(forbidden_parts)}: {relative}"
            )

    symlinks = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_symlink()
        and not any(part in SKIP_DIRECTORIES for part in path.parts)
    ]
    if symlinks:
        errors.append("public tree contains symlinks: " + ", ".join(symlinks))

    for path in files:
        relative = path.relative_to(ROOT)
        if path.name in FORBIDDEN_FILE_NAMES:
            errors.append(f"forbidden account or key file: {relative}")
        if path.stat().st_size > 1_000_000:
            errors.append(f"public file exceeds 1 MB: {relative}")
        if path.suffix not in TEXT_SUFFIXES and path.name != "LICENSE":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"public file is not UTF-8 text: {relative}")
            continue
        for pattern_name, pattern in CONTENT_PATTERNS.items():
            if pattern.search(content):
                errors.append(f"{pattern_name} found in {relative}")
        lowered = content.casefold()
        for identifier in PRIVATE_IDENTIFIERS:
            if identifier in lowered:
                errors.append(
                    f"private infrastructure identifier found in {relative}"
                )

    pack_root = ROOT / "volunteer_pack"
    manifest = _read_yaml(pack_root / "manifest.yaml")
    if manifest.get("semantic_roots") != []:
        errors.append("volunteer_pack.semantic_roots must be an empty list")

    connectors = _read_yaml(pack_root / "connectors" / "bindings.yaml")
    for binding in connectors.get("bindings") or []:
        if not isinstance(binding, dict):
            errors.append("connector binding must be a mapping")
            continue
        secret_refs = binding.get("secret_refs")
        if secret_refs not in ({}, None):
            errors.append(
                "public Connector bindings must not contain secret references"
            )

    registry = _read_yaml(pack_root / "roles.yaml")
    roles = registry.get("roles")
    if not isinstance(roles, list) or len(roles) != 8:
        errors.append("volunteer_pack must declare exactly eight roles")
        roles = []
    for role in roles:
        if not isinstance(role, dict):
            errors.append("role registry entry must be a mapping")
            continue
        instruction_file = pack_root / str(role.get("instruction_file") or "")
        if not instruction_file.is_file():
            errors.append(
                f"missing role instruction: {role.get('instruction_file')}"
            )
        skill_files = role.get("skill_files")
        if not isinstance(skill_files, list) or not skill_files:
            errors.append(f"role has no skills: {role.get('name')}")
            continue
        for raw_skill_path in skill_files:
            skill_path = pack_root / str(raw_skill_path)
            if not skill_path.is_file():
                errors.append(f"missing Skill: {raw_skill_path}")
                continue
            skill_text = skill_path.read_text(encoding="utf-8")
            if not skill_text.startswith("---\n"):
                errors.append(f"Skill lacks frontmatter: {raw_skill_path}")
            for heading in (
                "## Use When",
                "## Inputs",
                "## Procedure",
                "## Output",
                "## Stop Conditions",
            ):
                if heading not in skill_text:
                    errors.append(
                        f"Skill lacks {heading}: {raw_skill_path}"
                    )

    if (ROOT / ".git").is_dir():
        completed = subprocess.run(
            ["git", "log", "--format=%ae%n%ce"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            errors.append("could not inspect Git commit identities")
        for email in completed.stdout.splitlines():
            normalized = email.strip().casefold()
            if normalized.endswith(".local") or normalized.endswith("@localhost"):
                errors.append("Git history contains a machine-local email")

    return errors


def main() -> int:
    errors = validate_public_boundary()
    print(
        json.dumps(
            {
                "status": "pass" if not errors else "fail",
                "error_count": len(errors),
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
