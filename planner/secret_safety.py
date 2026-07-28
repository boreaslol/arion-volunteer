"""Detect credential material before Arion persists runtime state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import re
from typing import Any

import yaml


_AUTHENTICATED_URI = re.compile(
    r"\b(?:mongodb(?:\+srv)?|mysql|mariadb|postgres(?:ql)?|redis(?:s)?|https?)"
    r"://[^/\s:@]+:(?P<secret>[^@\s/]+)@",
    re.IGNORECASE,
)
_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
    re.IGNORECASE,
)
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?P<kind>(?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY)-----"
    r".*?-----END (?P=kind)-----",
    re.IGNORECASE | re.DOTALL,
)
_BEARER_TOKEN = re.compile(
    r"\bBearer\s+(?P<secret>[A-Za-z0-9._~+/=-]{12,})",
    re.IGNORECASE,
)
_BASIC_AUTH = re.compile(
    r"\bBasic\s+(?P<secret>[A-Za-z0-9+/]{16,}={0,2})",
    re.IGNORECASE,
)
_EQUALS_FIELD_ASSIGNMENT = re.compile(
    r"\b(?P<field>[A-Za-z][A-Za-z0-9_.-]*)\s*=\s*"
    r"[\"']?(?P<secret>[^\s,;\"'}]+)",
    re.IGNORECASE,
)
_COLON_FIELD_ASSIGNMENT = re.compile(
    r"(?m)^\s*[\"']?(?P<field>[A-Za-z][A-Za-z0-9_.-]*)[\"']?\s*:\s*"
    r"[\"']?(?P<secret>[^\s,;\"'}]+)",
    re.IGNORECASE,
)
_FIELD_ASSIGNMENTS = (
    _EQUALS_FIELD_ASSIGNMENT,
    _COLON_FIELD_ASSIGNMENT,
)
_SENSITIVE_FIELD_TERMINALS = frozenset(
    {
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "passphrase",
        "password",
        "passwd",
        "pwd",
        "secret",
        "session",
        "token",
    }
)
_SENSITIVE_FIELD_SUFFIXES = (
    "api_key",
    "access_token",
    "access_key",
    "auth_token",
    "client_secret",
    "encryption_key",
    "id_token",
    "private_key",
    "refresh_token",
    "secret_key",
    "signing_key",
)
_SAFE_SECRET_METADATA_SUFFIXES = (
    "_available",
    "_configured",
    "_present",
    "_ref",
    "_refs",
    "_required",
    "_slot",
    "_slots",
)
_MANAGED_SECRET_PREFIXES = (
    "profile://",
    "target-profile://",
    "keychain://",
    "secret-manager://",
)
_PLACEHOLDERS = {
    "",
    "available",
    "configured",
    "environment",
    "example",
    "masked",
    "missing",
    "none",
    "null",
    "placeholder",
    "redacted",
    "required",
    "true",
    "false",
    "xxx",
}
CONTROL_ARTIFACT_SUFFIXES = frozenset(
    {".json", ".jsonl", ".log", ".md", ".toml", ".txt", ".yaml", ".yml"}
)
MAX_CONTROL_ARTIFACT_BYTES = 4 * 1024 * 1024


def _normalize_field_name(value: str) -> str:
    separated = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", value)
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", separated)
    return re.sub(r"[^a-z0-9]+", "_", separated.casefold()).strip("_")


def _is_sensitive_field_name(value: str) -> bool:
    normalized = _normalize_field_name(value)
    if not normalized or normalized.endswith(_SAFE_SECRET_METADATA_SUFFIXES):
        return False
    if normalized.split("_")[-1] in _SENSITIVE_FIELD_TERMINALS:
        return True
    return any(
        normalized == suffix or normalized.endswith("_" + suffix)
        for suffix in _SENSITIVE_FIELD_SUFFIXES
    )


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").casefold()
    if normalized in _PLACEHOLDERS:
        return True
    if normalized.startswith(_MANAGED_SECRET_PREFIXES):
        return True
    if normalized.startswith(("${", "$", "<", "[")) and normalized.endswith(
        ("}", ">", "]")
    ):
        return True
    if normalized and set(normalized) <= {"*", "x", "•"}:
        return True
    return False


def _string_findings(value: str) -> tuple[str, ...]:
    findings: list[str] = []
    if _PRIVATE_KEY.search(value):
        findings.append("private_key")
    for pattern, kind in (
        (_AUTHENTICATED_URI, "authenticated_uri"),
        (_BEARER_TOKEN, "bearer_token"),
        (_BASIC_AUTH, "basic_auth"),
    ):
        for match in pattern.finditer(value):
            if not _is_placeholder(match.group("secret")):
                findings.append(kind)
                break
    for pattern in _FIELD_ASSIGNMENTS:
        for match in pattern.finditer(value):
            if (
                _is_sensitive_field_name(match.group("field"))
                and not _is_placeholder(match.group("secret"))
            ):
                findings.append("credential_assignment")
                break
    return tuple(dict.fromkeys(findings))


def redact_secret_text(value: str) -> str:
    """Redact recognized credential material without exposing matched values."""

    redacted = _PRIVATE_KEY_BLOCK.sub("<redacted-private-key>", value)
    redacted = _PRIVATE_KEY.sub("<redacted-private-key-header>", redacted)
    redacted = _AUTHENTICATED_URI.sub(
        lambda match: (
            match.group(0).split("://", 1)[0]
            + "://<redacted>@"
        ),
        redacted,
    )

    def redact_group(match: re.Match[str]) -> str:
        offset = match.start("secret") - match.start()
        return match.group(0)[:offset] + "<redacted>"

    for pattern in (_BEARER_TOKEN, _BASIC_AUTH):
        redacted = pattern.sub(redact_group, redacted)
    for pattern in _FIELD_ASSIGNMENTS:
        redacted = pattern.sub(
            lambda match: (
                redact_group(match)
                if (
                    _is_sensitive_field_name(match.group("field"))
                    and not _is_placeholder(match.group("secret"))
                )
                else match.group(0)
            ),
            redacted,
        )
    return redacted


def redact_secret_material(value: Any) -> Any:
    """Return a JSON-friendly copy with recognized credential values removed."""

    if is_dataclass(value) and not isinstance(value, type):
        return redact_secret_material(asdict(value))
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if (
                _is_sensitive_field_name(key_text)
                and isinstance(item, str)
                and not _is_placeholder(item)
            ):
                redacted[key] = "<redacted>"
            elif (
                _is_sensitive_field_name(key_text)
                and isinstance(item, (bytes, bytearray))
                and item
            ):
                redacted[key] = "<redacted>"
            elif (
                _is_sensitive_field_name(key_text)
                and isinstance(item, (Mapping, Sequence))
                and not isinstance(item, (str, bytes, bytearray))
                and bool(item)
            ):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = redact_secret_material(item)
        return redacted
    if isinstance(value, tuple):
        return tuple(redact_secret_material(item) for item in value)
    if isinstance(value, list):
        return [redact_secret_material(item) for item in value]
    return value


def find_secret_material(
    value: Any,
    *,
    label: str = "$",
) -> list[str]:
    """Return redacted finding locations without returning secret values."""

    findings: list[str] = []

    def visit(candidate: Any, path: str) -> None:
        if is_dataclass(candidate) and not isinstance(candidate, type):
            visit(asdict(candidate), path)
            return
        if isinstance(candidate, str):
            findings.extend(
                f"{path} ({kind})"
                for kind in _string_findings(candidate)
            )
            return
        if isinstance(candidate, Mapping):
            for key, item in candidate.items():
                item_path = f"{path}.{key}"
                key_text = str(key)
                if (
                    _is_sensitive_field_name(key_text)
                    and isinstance(item, str)
                    and not _is_placeholder(item)
                ):
                    findings.append(
                        f"{item_path} (credential_field)"
                    )
                    continue
                if (
                    _is_sensitive_field_name(key_text)
                    and isinstance(item, (bytes, bytearray))
                    and item
                ):
                    findings.append(
                        f"{item_path} (credential_field)"
                    )
                    continue
                if (
                    _is_sensitive_field_name(key_text)
                    and isinstance(item, (Mapping, Sequence))
                    and not isinstance(item, (str, bytes, bytearray))
                    and bool(item)
                ):
                    findings.append(
                        f"{item_path} (credential_field)"
                    )
                    continue
                visit(item, item_path)
            return
        if isinstance(candidate, Sequence) and not isinstance(
            candidate,
            (str, bytes, bytearray),
        ):
            for index, item in enumerate(candidate):
                visit(item, f"{path}[{index}]")

    visit(value, label)
    return findings


def validate_secret_safe(
    value: Any,
    *,
    label: str = "$",
) -> list[str]:
    return [
        f"{label} contains credential material at {finding}"
        for finding in find_secret_material(value, label=label)
    ]


def require_secret_safe(
    value: Any,
    *,
    label: str = "$",
) -> None:
    issues = validate_secret_safe(value, label=label)
    if issues:
        raise ValueError("; ".join(issues))


def require_secret_safe_artifact(path: str | Path) -> None:
    """Inspect bounded text/control artifacts before runtime acceptance."""

    resolved = Path(path).resolve()
    if resolved.suffix.casefold() not in CONTROL_ARTIFACT_SUFFIXES:
        return
    size = resolved.stat().st_size
    if size > MAX_CONTROL_ARTIFACT_BYTES:
        raise ValueError(
            "control artifact exceeds credential scan limit: "
            f"{resolved} ({size} bytes)"
        )
    text = resolved.read_text(encoding="utf-8")
    suffix = resolved.suffix.casefold()
    payload: Any = text
    try:
        if suffix == ".json":
            payload = json.loads(text)
        elif suffix == ".jsonl":
            payload = [
                json.loads(line)
                for line in text.splitlines()
                if line.strip()
            ]
        elif suffix in {".yaml", ".yml"}:
            payload = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(
            f"control artifact is not valid {suffix}: {resolved}"
        ) from exc
    require_secret_safe(payload, label=f"runtime_artifact:{resolved.name}")
