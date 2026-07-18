from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.artifacts import artifact_static_url, ensure_artifact_directory
from app.main import app
from app.settings import PROJECT_ROOT, Settings


def test_settings_exposes_default_artifact_static_directory():
    settings = Settings.from_env({})

    assert settings.artifact_static_dir == PROJECT_ROOT / "backend/data/artifacts"


def test_settings_allows_artifact_static_directory_override(tmp_path):
    settings = Settings.from_env({"ARTIFACT_STATIC_DIR": str(tmp_path / "outputs")})

    assert settings.artifact_static_dir == tmp_path / "outputs"


def test_ensure_artifact_directory_creates_directory(tmp_path):
    artifact_dir = tmp_path / "nested" / "artifacts"

    assert ensure_artifact_directory(artifact_dir) == artifact_dir
    assert artifact_dir.is_dir()


def test_artifact_static_url_quotes_safe_relative_paths():
    assert artifact_static_url("charts/revenue by region.png") == (
        "/artifacts/charts/revenue%20by%20region.png"
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "",
        "/absolute/file.png",
        "../outside.png",
        "charts/../../outside.png",
    ],
)
def test_artifact_static_url_rejects_unsafe_paths(relative_path):
    with pytest.raises(ValueError):
        artifact_static_url(relative_path)


def test_static_artifact_files_are_served_locally():
    artifact_dir = Settings.from_env({}).artifact_static_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "test-static-artifact.txt"
    artifact_path.write_text("local artifact", encoding="utf-8")

    try:
        response = TestClient(app).get("/artifacts/test-static-artifact.txt")
    finally:
        artifact_path.unlink(missing_ok=True)

    assert response.status_code == 200
    assert response.text == "local artifact"
