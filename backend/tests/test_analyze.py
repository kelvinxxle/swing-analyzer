"""Tests for the `/analyze` endpoint: demo overrides (mock) + the real M5 gate."""

from __future__ import annotations

import io
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pose_helpers import make_synthetic_clip

from app.main import app

client = TestClient(app)


def _video(content: bytes = b"\x00\x01\x02fakevideo") -> dict[str, tuple[str, io.BytesIO, str]]:
    return {"file": ("swing.mp4", io.BytesIO(content), "video/mp4")}


def _clip_upload(
    path: Path, *, name: str = "clip.mp4", **kwargs: object
) -> dict[str, tuple[str, io.BytesIO, str]]:
    """Build a multipart upload from a real synthetic clip on disk."""
    make_synthetic_clip(path, **kwargs)  # type: ignore[arg-type]
    return {"file": (name, io.BytesIO(path.read_bytes()), "video/mp4")}


def test_analyze_happy_path_returns_flaws() -> None:
    # The default no-hint path now runs the real gate, so force the flaws demo.
    response = client.post("/analyze", files=_video(), data={"scenario": "flaws"})
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


def test_analyze_infers_flaws_from_filename() -> None:
    files = {"file": ("flaws-demo.mp4", io.BytesIO(b"data"), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "analyzed"


def test_analyze_explicit_scenario_overrides_filename() -> None:
    files = {"file": ("bad-angle.mp4", io.BytesIO(b"data"), "video/mp4")}
    response = client.post("/analyze", files=files, data={"scenario": "flaws"})
    assert response.status_code == 200
    assert response.json()["status"] == "analyzed"


# --- Real validation gate (no demo hint) ------------------------------------


def _reason_code(body: dict[str, object]) -> str:
    reason = body["reason"]
    assert isinstance(reason, dict)
    details = reason["details"]
    assert isinstance(details, list)
    return str(details[0]["code"])


def test_analyze_real_gate_rejects_unreadable() -> None:
    # A neutral-named, undecodable upload runs the real gate → unreadable.
    files = {"file": ("clip.mp4", io.BytesIO(b"\x00\x01not a video"), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "rejected"
    assert _reason_code(body) == "unreadable"


def test_analyze_real_gate_rejects_low_resolution(tmp_path: Path) -> None:
    files = _clip_upload(
        tmp_path / "tiny.mp4", frames=60, fps=30.0, width=64, height=48, background=128
    )
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert _reason_code(response.json()) == "low_resolution"


def test_analyze_real_gate_rejects_too_dark(tmp_path: Path) -> None:
    files = _clip_upload(
        tmp_path / "dark.mp4", frames=60, fps=30.0, width=720, height=1280, background=0
    )
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert _reason_code(response.json()) == "lighting"


def test_analyze_real_gate_rejects_too_short(tmp_path: Path) -> None:
    files = _clip_upload(
        tmp_path / "short.mp4", frames=10, fps=30.0, width=720, height=1280, background=128
    )
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert _reason_code(response.json()) == "too_short"


def test_analyze_real_gate_rejects_no_golfer(tmp_path: Path) -> None:
    # A bright, well-sized synthetic clip has no human → real MediaPipe finds no
    # pose → no_golfer, exercising the pose path end-to-end.
    files = _clip_upload(
        tmp_path / "empty.mp4", frames=60, fps=30.0, width=720, height=1280, background=128
    )
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert _reason_code(response.json()) == "no_golfer"


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
    response = client.post("/analyze", files=_video(), data={"scenario": "flaws"})
    assert response.status_code == 200
    # Ephemeral handling: no temp artifacts left behind after the request.
    assert list(temp_root.iterdir()) == []
