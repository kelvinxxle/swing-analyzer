"""Tests for the mock `/analyze` endpoint (M3 walking skeleton)."""

from __future__ import annotations

import io
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _video(content: bytes = b"\x00\x01\x02fakevideo") -> dict[str, tuple[str, io.BytesIO, str]]:
    return {"file": ("swing.mp4", io.BytesIO(content), "video/mp4")}


def test_analyze_happy_path_returns_flaws() -> None:
    response = client.post("/analyze", files=_video())
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "analyzed"
    assert body["reason"] is None
    assert 2 <= len(body["flaws"]) <= 3
    for flaw in body["flaws"]:
        assert flaw["fix"].strip()
        assert flaw["title"].strip()


def test_analyze_clean_scenario_no_major_flaws() -> None:
    response = client.post("/analyze", files=_video(), data={"scenario": "clean"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "no_major_flaws"
    assert body["flaws"] == []
    assert body["reason"] is None


def test_analyze_rejected_scenario_returns_reason() -> None:
    response = client.post("/analyze", files=_video(), data={"scenario": "rejected"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "rejected"
    assert body["flaws"] == []
    assert body["reason"]["details"]
    codes = {detail["code"] for detail in body["reason"]["details"]}
    assert codes <= {"angle", "lighting", "no_golfer"}


def test_analyze_infers_rejection_from_filename() -> None:
    files = {"file": ("bad-angle.mp4", io.BytesIO(b"data"), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_analyze_infers_clean_from_filename() -> None:
    files = {"file": ("good-swing.mp4", io.BytesIO(b"data"), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "no_major_flaws"


def test_analyze_explicit_scenario_overrides_filename() -> None:
    files = {"file": ("bad-angle.mp4", io.BytesIO(b"data"), "video/mp4")}
    response = client.post("/analyze", files=files, data={"scenario": "flaws"})
    assert response.status_code == 200
    assert response.json()["status"] == "analyzed"


def test_analyze_rejects_missing_file() -> None:
    response = client.post("/analyze")
    assert response.status_code == 422


def test_analyze_rejects_empty_file() -> None:
    files = {"file": ("swing.mp4", io.BytesIO(b""), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 400


def test_analyze_rejects_non_video_content_type() -> None:
    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 400


@pytest.fixture
def temp_root() -> Iterator[Path]:
    """Point tempfile at an isolated dir so we can assert it ends up empty."""
    previous = tempfile.tempdir
    with tempfile.TemporaryDirectory() as root:
        tempfile.tempdir = root
        try:
            yield Path(root)
        finally:
            tempfile.tempdir = previous


def test_analyze_discards_uploaded_file(temp_root: Path) -> None:
    response = client.post("/analyze", files=_video())
    assert response.status_code == 200
    # Ephemeral handling: no temp artifacts left behind after the request.
    assert list(temp_root.iterdir()) == []
