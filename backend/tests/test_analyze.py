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


@pytest.fixture
def passing_gate() -> Iterator[None]:
    """Stub the gate to 'passed' so success-screen selection can be tested.

    A passing real video is impossible to synthesize hermetically (a clip with no
    human is correctly rejected as ``no_golfer``), so success-path tests stub the
    gate and assert only which success screen the endpoint chooses.
    """
    import app.main as main
    from app.validation.result import ValidationResult

    def _passed(*_args: object, **_kwargs: object) -> tuple[ValidationResult, None]:
        return ValidationResult(), None

    original = main.validate_video
    main.validate_video = _passed  # type: ignore[assignment]
    try:
        yield
    finally:
        main.validate_video = original  # type: ignore[assignment]


def test_analyze_passing_video_returns_flaws(passing_gate: None) -> None:
    response = client.post("/analyze", files=_video())
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "analyzed"
    assert body["reason"] is None
    assert 2 <= len(body["flaws"]) <= 3
    for flaw in body["flaws"]:
        assert flaw["fix"].strip()
        assert flaw["title"].strip()


def test_analyze_clean_scenario_picks_no_major_flaws(passing_gate: None) -> None:
    # The success override only chooses a screen for a video that already passed.
    response = client.post("/analyze", files=_video(), data={"scenario": "clean"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "no_major_flaws"
    assert body["flaws"] == []
    assert body["reason"] is None


def test_analyze_clean_filename_picks_no_major_flaws(passing_gate: None) -> None:
    files = {"file": ("good-swing.mp4", io.BytesIO(b"data"), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "no_major_flaws"


def test_analyze_scenario_flaws_overrides_clean_filename(passing_gate: None) -> None:
    # An explicit success scenario wins over a filename hint — but only among
    # success screens, for a video that passed validation.
    files = {"file": ("good-swing.mp4", io.BytesIO(b"data"), "video/mp4")}
    response = client.post("/analyze", files=files, data={"scenario": "flaws"})
    assert response.status_code == 200
    assert response.json()["status"] == "analyzed"


def test_analyze_rejected_scenario_is_a_single_reason_dev_lever() -> None:
    # The dev lever forces the rejection screen with one specific reason,
    # consistent with the real gate (no longer the legacy 3-detail payload).
    response = client.post("/analyze", files=_video(), data={"scenario": "rejected"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "rejected"
    assert body["flaws"] == []
    assert len(body["reason"]["details"]) == 1
    assert body["reason"]["details"][0]["code"] in {
        "angle",
        "lighting",
        "no_golfer",
        "unreadable",
        "low_resolution",
        "too_short",
        "framing",
    }


def test_bad_clip_with_clean_filename_is_still_rejected() -> None:
    # Regression for the P1 fix: a CLEAN-hinted filename must NOT mask a bad clip.
    # The real gate runs first, so an undecodable upload named good-swing.mp4 is
    # rejected — a user-controlled filename can never force a success result.
    files = {"file": ("good-swing.mp4", io.BytesIO(b"\x00\x01nope"), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "rejected"
    assert _reason_code(body) == "unreadable"


def test_flaws_filename_cannot_mask_a_bad_clip() -> None:
    # Same regression from the FLAWS-hint side.
    files = {"file": ("sample-flaws.mp4", io.BytesIO(b"\x00\x01nope"), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


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
    # Use the dev-lever rejection so the test doesn't run the slow CV gate; the
    # temp file is drained either way and must be cleaned up.
    response = client.post("/analyze", files=_video(), data={"scenario": "rejected"})
    assert response.status_code == 200
    # Ephemeral handling: no temp artifacts left behind after the request.
    assert list(temp_root.iterdir()) == []
