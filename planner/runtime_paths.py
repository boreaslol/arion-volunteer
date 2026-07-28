"""Resolve Arion runtime storage outside the source repository."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
import stat
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARION_HOME_ENV = "ARION_HOME"
ARION_PROJECTS_ROOT_ENV = "ARION_PROJECTS_ROOT"
ARION_SYNC_HOME_ENV = "ARION_SYNC_HOME"
RUNTIME_IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$"
)


def _expanded_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def runtime_identifier_issue(
    value: str,
    *,
    field_name: str = "run_id",
) -> str | None:
    text = str(value)
    if not text.strip():
        return f"{field_name} is required"
    if text != text.strip() or not RUNTIME_IDENTIFIER_PATTERN.fullmatch(text):
        return (
            f"{field_name} must be one safe ASCII path segment "
            "(letters, digits, dot, underscore, or hyphen)"
        )
    return None


def require_runtime_identifier(
    value: str,
    *,
    field_name: str = "run_id",
) -> str:
    issue = runtime_identifier_issue(value, field_name=field_name)
    if issue:
        raise ValueError(issue)
    return str(value)


def resolve_runtime_child(
    root: str | Path,
    identifier: str,
    *,
    field_name: str = "run_id",
) -> Path:
    resolved_root = _expanded_path(root)
    safe_identifier = require_runtime_identifier(
        identifier,
        field_name=field_name,
    )
    resolved = (resolved_root / safe_identifier).resolve()
    if resolved.parent != resolved_root:
        raise ValueError(
            f"{field_name} resolves outside its runtime root: {identifier}"
        )
    return resolved


def _ensure_owner_only_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"Runtime directory must not be a symlink: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    file_stat = path.stat()
    if not stat.S_ISDIR(file_stat.st_mode):
        raise NotADirectoryError(f"Runtime path is not a directory: {path}")
    if file_stat.st_uid != os.geteuid():
        raise PermissionError(
            f"Runtime directory must be owned by the current user: {path}"
        )
    if stat.S_IMODE(file_stat.st_mode) != 0o700:
        path.chmod(0o700)


def default_arion_home(
    *,
    environ: Mapping[str, str] | None = None,
    user_home: str | Path | None = None,
) -> Path:
    values = os.environ if environ is None else environ
    configured = str(values.get(ARION_HOME_ENV) or "").strip()
    if configured:
        return _expanded_path(configured)
    configured_projects_root = str(
        values.get(ARION_PROJECTS_ROOT_ENV) or ""
    ).strip()
    home = _expanded_path(user_home or Path.home())
    projects_root = (
        _expanded_path(configured_projects_root)
        if configured_projects_root
        else home / "Projects"
    )
    return projects_root / ".arion"


def resolve_arion_sync_home(
    value: str | Path | None = None,
    *,
    project_root: str | Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    values = os.environ if environ is None else environ
    configured = (
        str(value).strip()
        if value is not None
        else str(values.get(ARION_SYNC_HOME_ENV) or "").strip()
    )
    if not configured:
        return None
    return require_external_runtime_path(
        configured,
        project_root=project_root,
        purpose="ARION_SYNC_HOME",
    )


def resolve_arion_home(
    value: str | Path | None = None,
    *,
    project_root: str | Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
    user_home: str | Path | None = None,
) -> Path:
    resolved = (
        _expanded_path(value)
        if value is not None
        else default_arion_home(environ=environ, user_home=user_home)
    )
    repository = _expanded_path(project_root)
    if resolved == repository or resolved.is_relative_to(repository):
        raise ValueError(
            "ARION_HOME must be outside the source repository; "
            f"got {resolved}"
        )
    return resolved


def require_external_runtime_path(
    value: str | Path,
    *,
    project_root: str | Path = PROJECT_ROOT,
    purpose: str = "runtime payload",
) -> Path:
    resolved = _expanded_path(value)
    repository = _expanded_path(project_root)
    if resolved == repository or resolved.is_relative_to(repository):
        raise ValueError(
            f"{purpose} must be outside the source repository; got {resolved}"
        )
    return resolved


@dataclass(frozen=True)
class RuntimePaths:
    home: Path
    tasks: Path
    runs: Path
    artifacts: Path
    resources: Path
    models: Path
    datasets: Path
    cache: Path
    worktrees: Path
    state: Path
    backups: Path

    @property
    def runtime_state_db(self) -> Path:
        return self.state / "runtime_v1.sqlite3"

    @property
    def runtime_backup_root(self) -> Path:
        return self.backups / "runtime_v1"

    def ensure(self) -> "RuntimePaths":
        for path in asdict(self).values():
            _ensure_owner_only_directory(Path(path))
        return self

    def to_dict(self) -> dict[str, str]:
        payload = {key: str(value) for key, value in asdict(self).items()}
        payload["runtime_state_db"] = str(self.runtime_state_db)
        payload["runtime_backup_root"] = str(self.runtime_backup_root)
        return payload


def build_runtime_paths(
    arion_home: str | Path | None = None,
    *,
    project_root: str | Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
    user_home: str | Path | None = None,
    create: bool = False,
) -> RuntimePaths:
    home = resolve_arion_home(
        arion_home,
        project_root=project_root,
        environ=environ,
        user_home=user_home,
    )
    paths = RuntimePaths(
        home=home,
        tasks=home / "tasks",
        runs=home / "runs",
        artifacts=home / "artifacts",
        resources=home / "resources",
        models=home / "models",
        datasets=home / "datasets",
        cache=home / "cache",
        worktrees=home / "worktrees",
        state=home / "state",
        backups=home / "backups",
    )
    return paths.ensure() if create else paths


def resolve_portable_reference(
    reference: str | Path,
    *,
    project_root: str | Path = PROJECT_ROOT,
    arion_home: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> Path:
    """Resolve repository-relative and ``$ARION_HOME`` references.

    Relative references resolve from ``base_dir`` when provided, while still
    remaining inside ``project_root``.
    """

    value = str(reference).strip()
    resolved_project_root = _expanded_path(project_root)
    if value == "$ARION_HOME" or value.startswith("$ARION_HOME/"):
        runtime_home = build_runtime_paths(
            arion_home,
            project_root=resolved_project_root,
        ).home
        suffix = value.removeprefix("$ARION_HOME").lstrip("/")
        resolved = (runtime_home / suffix).resolve() if suffix else runtime_home
        if not resolved.is_relative_to(runtime_home):
            raise ValueError(f"Reference escapes ARION_HOME: {value}")
        return resolved

    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    resolved_base_dir = (
        _expanded_path(base_dir)
        if base_dir is not None
        else resolved_project_root
    )
    if not resolved_base_dir.is_relative_to(resolved_project_root):
        raise ValueError(
            "Portable reference base directory must be inside the project root: "
            f"{resolved_base_dir}"
        )
    resolved = (resolved_base_dir / path).resolve()
    if not resolved.is_relative_to(resolved_project_root):
        raise ValueError(f"Reference escapes project root: {value}")
    return resolved
