"""Tests for the validation gate orchestration (M5).

Exercises ``validate_video`` end-to-end on real synthetic clips with an injected
fake pose estimator: cheap-before-pose ordering, the passing path returning a
reusable series, and the decode/pose rejections.
"""

from __future__ import annotations

from pathlib import Path

from pose_helpers import FakePoseEstimator, make_synthetic_clip

from app.validation import RejectionCode, validate_video


def _good_clip(path: Path) -> Path:
    # Big, bright, long enough to clear every cheap check.
    return make_synthetic_clip(
        path, frames=60, fps=30.0, width=720, height=1280, background=128
    )


def test_validate_passes_a_good_clip_and_returns_series(tmp_path: Path) -> None:
    clip = _good_clip(tmp_path / "swing.mp4")
    estimator = FakePoseEstimator(detect=True)

    result, series = validate_video(clip, estimator=estimator)

    assert result.passed
    assert result.rejection is None
    assert series is not None and series.frames
    assert estimator.calls == series.sampled_count


def test_validate_runs_cheap_checks_before_the_pose_pass(tmp_path: Path) -> None:
    # A dark clip is rejected on brightness; the (expensive) pose pass never runs.
    dark = make_synthetic_clip(
        tmp_path / "dark.mp4", frames=60, fps=30.0, width=720, height=1280, background=0
    )
    estimator = FakePoseEstimator(detect=True)

    result, series = validate_video(dark, estimator=estimator)

    assert not result.passed
    assert result.rejection is not None
    assert result.rejection.details[0].code == RejectionCode.LIGHTING.value
    assert series is None
    assert estimator.calls == 0


def test_validate_rejects_low_resolution_before_pose(tmp_path: Path) -> None:
    tiny = make_synthetic_clip(
        tmp_path / "tiny.mp4", frames=60, fps=30.0, width=64, height=48, background=128
    )
    estimator = FakePoseEstimator(detect=True)

    result, series = validate_video(tiny, estimator=estimator)

    assert result.rejection is not None
    assert result.rejection.details[0].code == RejectionCode.LOW_RESOLUTION.value
    assert estimator.calls == 0
    assert series is None


def test_validate_rejects_too_short(tmp_path: Path) -> None:
    short = make_synthetic_clip(
        tmp_path / "short.mp4", frames=10, fps=30.0, width=720, height=1280, background=128
    )
    result, series = validate_video(short, estimator=FakePoseEstimator(detect=True))

    assert result.rejection is not None
    assert result.rejection.details[0].code == RejectionCode.TOO_SHORT.value
    assert series is None


def test_validate_rejects_no_golfer(tmp_path: Path) -> None:
    clip = _good_clip(tmp_path / "empty.mp4")
    # A clip that clears the cheap checks but where the estimator finds no pose.
    result, series = validate_video(clip, estimator=FakePoseEstimator(detect=False))

    assert result.rejection is not None
    assert result.rejection.details[0].code == RejectionCode.NO_GOLFER.value
    assert series is not None  # the pose pass ran


def test_validate_rejects_unreadable_file(tmp_path: Path) -> None:
    not_a_video = tmp_path / "upload"
    not_a_video.write_bytes(b"\x00\x01\x02 not really a video")

    result, series = validate_video(not_a_video, estimator=FakePoseEstimator())

    assert result.rejection is not None
    assert result.rejection.details[0].code == RejectionCode.UNREADABLE.value
    assert series is None
