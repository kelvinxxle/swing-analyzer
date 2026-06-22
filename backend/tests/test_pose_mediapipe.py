"""Real-MediaPipe smoke test.

Runs the genuine :class:`MediaPipePoseEstimator` end-to-end on a synthetic clip
to prove that MediaPipe + OpenCV install and execute in CI (with the bundled,
offline pose model) and that the pipeline returns a well-formed series.

It does **not** assert that landmarks are detected: a synthetic clip contains no
real human, so ``detected`` may be False for every frame. Real landmark-detection
assertions arrive with the golden swing clips in M7.
"""

from __future__ import annotations

from pathlib import Path

from pose_helpers import make_synthetic_clip

from app.pose.config import SamplingConfig
from app.pose.estimator import MediaPipePoseEstimator
from app.pose.pipeline import extract_pose_series
from app.pose.schema import LandmarkName


def test_real_mediapipe_returns_well_formed_series(tmp_path: Path) -> None:
    clip = make_synthetic_clip(tmp_path / "swing.mp4", frames=12, fps=30.0)

    with MediaPipePoseEstimator() as estimator:
        series = extract_pose_series(clip, SamplingConfig(target_fps=30), estimator)

    assert series.sampled_count == len(series.frames)
    assert series.frames, "expected at least one sampled frame"
    for frame in series.frames:
        # Detection is allowed to be empty on synthetic input; when present it
        # must be the full, named 33-landmark set with bounded coordinates.
        if frame.detected:
            assert frame.landmarks is not None
            assert set(frame.landmarks) == set(LandmarkName)
            sample = frame.landmarks[LandmarkName.NOSE]
            assert 0.0 <= sample.visibility <= 1.0
        else:
            assert frame.landmarks is None
