"""Local artifact file serving helpers."""

from pathlib import Path
from urllib.parse import quote


ARTIFACTS_ROUTE = "/artifacts"


def ensure_artifact_directory(directory: Path) -> Path:
    """Create and return the local artifact directory."""

    directory.mkdir(parents=True, exist_ok=True)
    return directory


def artifact_static_url(relative_path: str) -> str:
    """Return the local URL path for a stored artifact file."""

    parts = _safe_relative_parts(relative_path)
    return f"{ARTIFACTS_ROUTE}/" + "/".join(quote(part) for part in parts)


def _safe_relative_parts(relative_path: str) -> tuple[str, ...]:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError("Artifact path must be relative.")

    parts = tuple(part for part in path.parts if part not in {"", "."})
    if not parts or any(part == ".." for part in parts):
        raise ValueError("Artifact path must stay inside the artifact directory.")

    return parts
