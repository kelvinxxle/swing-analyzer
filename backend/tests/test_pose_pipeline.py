"""Pipeline tests: real OpenCV decode + an injected fake pose estimator.

These assert the full landmark-series contract (shape, ordering, timestamps,
per-frame detection) deterministically, without running real inference.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pose_helpers import FakePoseEstimator, make_synthetic_clip

from app.pose.config import SamplingConfig
from app.pose.pipeline import VideoDecodeError, extract_pose_series


def test_extract_series_shape_and_contract(tmp_path: Path) -> None:
    clip = make_synthetic_clip(tmp_path / "swing.mp4", frames=30, fps=30.0)
    estimator = FakePoseEstimator(detect=True)

    series = extract_pose_series(clip, SamplingConfig(target_fps=30), estimator)

    assert series.fps == pytest.approx(30.0, abs=0.5)
    assert series.sampled_count == len(series.frames)
    assert series.frames, "expected at least one sampled frame"
    # Target fps == source fps → frame-for-frame.
    assert series.sampled_count == pytest.approx(30, abs=1)
    assert estimator.calls == series.sampled_count
    assert estimator.closed is False  # injected estimator is left to the caller

    for i, frame in enumerate(series.frames):
        assert frame.index == i
        assert frame.detected is True
        assert frame.landmarks is not None
        assert len(frame.landmarks) == 33

    timestamps = [f.timestamp_s for f in series.frames]
    assert timestamps == sorted(timestamps)


def test_downsampling_reduces_frame_count(tmp_path: Path) -> None:
    clip = make_synthetic_clip(tmp_path / "fast.mp4", frames=60, fps=60.0)
    estimator = FakePoseEstimator(detect=True)

    series = extract_pose_series(clip, SamplingConfig(target_fps=30), estimator)

    # 60 fps decoded at a ~30 fps target → roughly half the frames.
    assert series.sampled_count == pytest.approx(30, abs=2)
    assert series.sampled_fps == pytest.approx(30.0, abs=1.0)
    source_indices = [f.source_frame_index for f in series.frames]
    assert source_indices == sorted(source_indices)
    assert len(set(source_indices)) == len(source_indices)


def test_frame_budget_caps_sampled_frames(tmp_path: Path) -> None:
    clip = make_synthetic_clip(tmp_path / "long.mp4", frames=120, fps=30.0)
    estimator = FakePoseEstimator(detect=True)

    series = extract_pose_series(
        clip, SamplingConfig(target_fps=30, max_frames=20), estimator
    )

    assert series.sampled_count <= 20


def test_frame_budget_enforced_without_stride_widening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate missing frame-count metadata: stride can't be widened upstream, so
    # the decode loop's hard cap must still bound the sampled frames.
    monkeypatch.setattr("app.pose.pipeline.compute_stride", lambda *a, **k: 1)
    clip = make_synthetic_clip(tmp_path / "long.mp4", frames=120, fps=30.0)
    estimator = FakePoseEstimator(detect=True)

    series = extract_pose_series(
        clip, SamplingConfig(target_fps=30, max_frames=15), estimator
    )

    assert series.sampled_count == 15
    assert estimator.calls == 15


def test_undetected_frames_marked(tmp_path: Path) -> None:
    clip = make_synthetic_clip(tmp_path / "swing.mp4", frames=10, fps=30.0)
    estimator = FakePoseEstimator(detect=False)

    series = extract_pose_series(clip, SamplingConfig(target_fps=30), estimator)

    assert series.frames
    assert all(not f.detected and f.landmarks is None for f in series.frames)
    assert series.detected_frames == []


def test_owned_estimator_is_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clip = make_synthetic_clip(tmp_path / "swing.mp4", frames=5, fps=30.0)
    created: list[FakePoseEstimator] = []

    def _factory() -> FakePoseEstimator:
        estimator = FakePoseEstimator(detect=True)
        created.append(estimator)
        return estimator

    # When no estimator is injected, the pipeline creates and must close its own.
    monkeypatch.setattr("app.pose.pipeline.MediaPipePoseEstimator", _factory)
    series = extract_pose_series(clip, SamplingConfig(target_fps=30))

    assert series.sampled_count >= 1
    assert len(created) == 1
    assert created[0].closed is True


def test_missing_file_raises(tmp_path: Path) -> None:
    estimator = FakePoseEstimator()
    with pytest.raises(VideoDecodeError):
        extract_pose_series(tmp_path / "does-not-exist.mp4", estimator=estimator)
    # Even on failure the pipeline owns nothing it forgot to clean up; the
    # injected estimator is the caller's to close.
    assert estimator.closed is False
