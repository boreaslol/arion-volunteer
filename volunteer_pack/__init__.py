"""Public role-and-skill Pack shipped with Arion Volunteer."""

from pathlib import Path


def bundled_pack_root() -> Path:
    """Return the absolute path to the bundled Volunteer domain Pack."""
    return Path(__file__).resolve().parent


__all__ = ["bundled_pack_root"]
