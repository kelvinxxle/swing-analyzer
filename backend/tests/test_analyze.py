"""Tests for the `/analyze` endpoint: demo overrides + the real M5 gate + M6 engine."""

from __future__ import annotations

import io
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import detection_helpers as H
import pytest
from fastapi.testclient import TestClient
from pose_helpers import make_synthetic_clip

from app.main import app
from app.pose.schema import PoseSeries

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
def stub_gate() -> Iterator[Callable[[PoseSeries], None]]:
    """Stub the validation gate to 'passed', returning a chosen pose series.

    A passing *real* video is impossible to synthesize hermetically (a clip with
    no human is correctly rejected as ``no_golfer``), so the success-path tests
    stub the gate to hand the endpoint a constructed series and assert what the
    **real M6 engine** then produces from it.
    """
    import app.main as main
    from app.validation.result import ValidationResult

    original = main.validate_video

    def install(series: PoseSeries) -> None:
        def _passed(*_args: object, **_kwargs: object) -> tuple[ValidationResult, PoseSeries]:
            return ValidationResult(), series

        main.validate_video = _passed  # type: ignore[assignment]

    try:
        yield install
    finally:
        main.validate_video = original  # type: ignore[assignment]


def test_analyze_real_engine_returns_ranked_flaws(
    stub_gate: Callable[[PoseSeries], None],
) -> None:
    # On a passing video the endpoint runs the REAL M6 engine over the gate's
    # series. A swing engineered to exhibit several flaws yields a prioritized,
    # top-3-capped list — no mock involved.
    stub_gate(
        H.make_swing(
            {H.EARLY_EXTENSION, H.LOSS_OF_POSTURE, H.HEAD_SWAY, H.OVER_THE_TOP}
        )
    )
    response = client.post("/analyze", files=_video())
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "analyzed"
    assert body["reason"] is None
    assert 2 <= len(body["flaws"]) <= 3
    assert [flaw["priority"] for flaw in body["flaws"]] == list(
        range(1, len(body["flaws"]) + 1)
    )
    for flaw in body["flaws"]:
        assert flaw["fix"].strip()
        assert flaw["title"].strip()
        assert flaw["description"].strip()


def test_analyze_real_engine_reports_no_major_flaws(
    stub_gate: Callable[[PoseSeries], None],
) -> None:
    # A clean swing through the real engine is a valid zero-flaw result.
    stub_gate(H.make_swing())
    response = client.post("/analyze", files=_video())
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "no_major_flaws"
    assert body["flaws"] == []
    assert body["reason"] is None


def test_analyze_clean_scenario_is_canned_no_major_flaws(
    stub_gate: Callable[[PoseSeries], None],
) -> None:
    # The CLEAN demo override returns a canned success screen, but ONLY after the
    # real gate passes (here stubbed to passing) — it never bypasses validation.
    stub_gate(H.make_swing())
    response = client.post("/analyze", files=_video(), data={"scenario": "clean"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "no_major_flaws"
    assert body["flaws"] == []
    assert body["reason"] is None


def test_analyze_flaws_scenario_is_canned_analyzed(
    stub_gate: Callable[[PoseSeries], None],
) -> None:
    # The FLAWS demo override returns the canned analyzed screen — also only after
    # the gate passes (stubbed). It's a dev lever, never real detection.
    stub_gate(H.make_swing())
    response = client.post("/analyze", files=_video(), data={"scenario": "flaws"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "analyzed"
    assert 2 <= len(body["flaws"]) <= 3


def test_clean_scenario_cannot_mask_a_bad_clip() -> None:
    # P1 regression: scenario=clean must NOT bypass the gate. An undecodable
    # upload is rejected even with the CLEAN demo lever set.
    files = {"file": ("clip.mp4", io.BytesIO(b"\x00\x01nope"), "video/mp4")}
    response = client.post("/analyze", files=files, data={"scenario": "clean"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "rejected"
    assert _reason_code(body) == "unreadable"


def test_flaws_scenario_cannot_mask_a_bad_clip() -> None:
    # Same P1 regression from the FLAWS side: the demo lever can never force a
    # success result on a video that fails validation.
    files = {"file": ("clip.mp4", io.BytesIO(b"\x00\x01nope"), "video/mp4")}
    response = client.post("/analyze", files=files, data={"scenario": "flaws"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "rejected"
    assert _reason_code(body) == "unreadable"


def test_analyze_passing_gate_without_series_fails_loud() -> None:
    # Defensive P? fix: if the gate reports 'passed' but hands back no series
    # (an internal pipeline fault), the endpoint must surface a 500 rather than
    # silently reporting a clean swing.
    import app.main as main
    from app.validation.result import ValidationResult

    original = main.validate_video

    def _passed_no_series(*_a: object, **_k: object) -> tuple[ValidationResult, None]:
        return ValidationResult(), None

    main.validate_video = _passed_no_series  # type: ignore[assignment]
    try:
        response = client.post("/analyze", files=_video())
    finally:
        main.validate_video = original  # type: ignore[assignment]
    assert response.status_code == 500


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


# --- M7 production hardening -------------------------------------------------


def test_analyze_rejects_oversized_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    # A tiny cap makes the size guard fire without generating a real large file.
    import app.main as main

    monkeypatch.setattr(main, "_max_upload_bytes", lambda: 8)
    files = {"file": ("clip.mp4", io.BytesIO(b"way more than eight bytes"), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 413
    # Sub-MB caps must never render as "0MB" (the message shows real bytes).
    detail = response.json()["detail"]
    assert "0MB" not in detail
    assert "8 bytes" in detail


def test_oversized_content_length_rejected_before_body_is_processed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The middleware refuses a too-large Content-Length up front: the handler's
    # drain/gate never run, so the oversized body is never processed. The body
    # must exceed the cap *plus* the multipart-overhead envelope to trip the
    # up-front guard (a file merely over the cap is caught later, while draining).
    import app.main as main

    drained = False

    async def _spy_drain(*_a: object, **_k: object) -> int:
        nonlocal drained
        drained = True
        return 0

    cap = 8
    monkeypatch.setattr(main, "_max_upload_bytes", lambda: cap)
    monkeypatch.setattr(main, "_drain_to_path", _spy_drain)
    oversized = b"x" * (main._content_length_ceiling(cap) + 1)
    files = {"file": ("clip.mp4", io.BytesIO(oversized), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 413
    assert drained is False, "the body was processed despite an oversized Content-Length"


def test_file_at_limit_passes_guard_while_oversized_still_413s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The pre-parse Content-Length guard must not reject a FILE that is exactly at
    # the advertised cap just because multipart framing (boundary + headers + the
    # scenario field) pushes the request body a little over the cap. The true
    # FILE-bytes cap is still enforced precisely by the streaming drain.
    import app.main as main
    from app.validation.reasons import build_rejection
    from app.validation.result import RejectionCode, ValidationResult

    cap = 64 * 1024  # large enough that real multipart overhead is a tiny fraction
    monkeypatch.setattr(main, "_max_upload_bytes", lambda: cap)
    # Isolate the size guard from the CPU-bound gate: a passing file would need
    # real footage, so stub the gate to a deterministic rejection. The 200
    # "rejected" body proves the upload was accepted past the size guard and ran
    # the real handler (not a transport-level 413).
    rejection = build_rejection(RejectionCode.UNREADABLE)
    monkeypatch.setattr(
        main, "validate_video", lambda *a, **k: (ValidationResult(rejection), None)
    )

    # A file at *exactly* the limit, wrapped in multipart framing (Content-Length
    # slightly above the cap), is accepted past both the middleware and the drain.
    at_limit = {"file": ("clip.mp4", io.BytesIO(b"x" * cap), "video/mp4")}
    response = client.post("/analyze", files=at_limit)
    assert response.status_code == 200, "a file exactly at the limit was wrongly rejected"
    body = response.json()
    assert body["status"] == "rejected"
    assert body["reason"]["details"][0]["code"] == RejectionCode.UNREADABLE.value

    # A file within the envelope but genuinely over the FILE cap still 413s — the
    # drain enforces the true file-bytes cap even though the middleware let it by.
    over_cap = {"file": ("clip.mp4", io.BytesIO(b"x" * (cap + 1024)), "video/mp4")}
    response = client.post("/analyze", files=over_cap)
    assert response.status_code == 413

    # A file far over the cap (beyond the whole envelope) is refused up front by
    # the middleware before the body is even read.
    far_over = b"x" * (main._content_length_ceiling(cap) + 1024)
    files = {"file": ("clip.mp4", io.BytesIO(far_over), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 413


def test_analyze_times_out_slow_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    # A near-zero budget + a gate that exceeds it → the request returns a clean
    # 504 rather than pinning the event loop on the CPU-bound path. With
    # abandon_on_cancel=True the 504 is genuinely PROMPT: wait_for stops awaiting
    # the worker at the deadline instead of being shielded until it returns. The
    # worker thread is NOT force-killed, so the already-dispatched, frame-bounded
    # work still finishes in the background. This test pins both halves.
    import threading
    import time

    import app.main as main
    from app.validation.result import ValidationResult

    worker_finished = threading.Event()

    def _slow_gate(*_a: object, **_k: object) -> tuple[ValidationResult, None]:
        time.sleep(0.3)
        worker_finished.set()
        return ValidationResult(), None

    monkeypatch.setattr(main, "_max_analysis_seconds", lambda: 0.05)
    monkeypatch.setattr(main, "validate_video", _slow_gate)
    response = client.post("/analyze", files=_video())
    assert response.status_code == 504
    # The client's 504 arrives before the worker is done (it is not cancelled)...
    assert not worker_finished.is_set()
    # ...but the in-flight, bounded worker still runs to completion afterwards.
    assert worker_finished.wait(timeout=2.0), "the in-flight worker never finished"


def test_analyze_budget_is_shared_across_gate_and_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The gate and the engine share ONE wall-clock budget. Each stage alone is
    # under budget, but together they exceed it → 504. (If each got a fresh budget
    # this would pass, so this test pins the shared-deadline behavior.)
    import time

    import app.main as main
    from app.analysis import AnalysisStatus
    from app.validation.result import ValidationResult

    def _gate(*_a: object, **_k: object) -> tuple[ValidationResult, object]:
        time.sleep(0.07)
        return ValidationResult(), object()  # passes the gate + yields a series

    def _engine(*_a: object, **_k: object) -> tuple[AnalysisStatus, list[object]]:
        time.sleep(0.07)
        return AnalysisStatus.NO_MAJOR_FLAWS, []

    monkeypatch.setattr(main, "_max_analysis_seconds", lambda: 0.1)
    monkeypatch.setattr(main, "validate_video", _gate)
    monkeypatch.setattr(main, "detect_flaws", _engine)
    response = client.post("/analyze", files=_video())
    assert response.status_code == 504


def test_analyze_unexpected_fault_is_a_clean_500(monkeypatch: pytest.MonkeyPatch) -> None:
    # An unexpected error inside the gate must surface as a controlled 500 (no
    # silent wrong-answer, no traceback leak), with the temp upload still cleaned.
    import app.main as main

    def _boom(*_a: object, **_k: object) -> tuple[object, None]:
        raise ValueError("synthetic pipeline fault")

    monkeypatch.setattr(main, "validate_video", _boom)
    response = client.post("/analyze", files=_video())
    assert response.status_code == 500


def test_oversized_upload_leaves_no_temp_files(
    temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An oversized 413 (here via the Content-Length middleware) must leave no
    # ephemeral temp artifacts behind — the handler never runs, so none are made.
    # The body exceeds the cap *plus* the multipart envelope so the up-front guard
    # fires before any temp file could be created.
    import app.main as main

    cap = 8
    monkeypatch.setattr(main, "_max_upload_bytes", lambda: cap)
    oversized = b"x" * (main._content_length_ceiling(cap) + 1)
    files = {"file": ("clip.mp4", io.BytesIO(oversized), "video/mp4")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 413
    assert list(temp_root.iterdir()) == []


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
