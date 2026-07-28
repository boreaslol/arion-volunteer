"""Opaque secret-reference contracts shared by public Connector schemas."""

from __future__ import annotations

from dataclasses import dataclass
import re


SECRET_REF_PATTERN = re.compile(
    r"^(?P<scheme>profile|target-profile|keychain|secret-manager)://"
    r"(?P<identifier>[A-Za-z0-9._/-]+)$"
)


@dataclass(frozen=True)
class SecretReference:
    scheme: str
    identifier: str

    @property
    def resolution_scope(self) -> str:
        if self.scheme == "profile":
            return "local"
        if self.scheme == "target-profile":
            return "target"
        return "external_provider"


def parse_secret_ref(value: str) -> SecretReference:
    if not isinstance(value, str):
        raise ValueError("secret_ref must be a string")
    match = SECRET_REF_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(
            "secret_ref must use profile://, target-profile://, "
            "keychain://, or secret-manager://"
        )
    identifier = match.group("identifier")
    if identifier.startswith("/") or ".." in identifier.split("/"):
        raise ValueError("secret_ref identifier must not escape its provider")
    return SecretReference(
        scheme=match.group("scheme"),
        identifier=identifier,
    )
