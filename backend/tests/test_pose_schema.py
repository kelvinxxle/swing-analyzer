"""Unit tests for the pose-series schema contract."""

from __future__ import annotations

import pytest
from pose_helpers import full_landmark_set
from pydantic import ValidationError

from app.pose.schema import (
    LANDMARK_ORDER,
    Landmark,
    LandmarkName,
    PoseFrame,
    PoseSeries,
)


def test_landmark_order_covers_all_33_names_uniquely() -> None:
    assert len(LANDMARK_ORDER) == 33
    assert set(LANDMARK_ORDER) == set(LandmarkName)
    assert len(set(LANDMARK_ORDER)) == 33


def test_named_landmark_access() -> None:
    landmarks = full_landmark_set()
    # Downstream rules read landmarks by name, not index.
    assert landmarks[LandmarkName.LEFT_HIP].x == 0.5
    assert landmarks[LandmarkName.RIGHT_WRIST].visibility == 0.9


def test_visibility_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Landmark(x=0.1, y=0.2, z=0.0, visibility=1.5)
    with pytest.raises(ValidationError):
        Landmark(x=0.1, y=0.2, z=0.0, visibility=-0.1)


def test_pose_frame_allows_missing_detection() -> None:
    frame = PoseFrame(
        index=0, source_frame_index=0, timestamp_s=0.0, detected=False, landmarks=None
    )
    assert frame.detected is False
    assert frame.landmarks is None


def test_pose_frame_detected_with_landmarks_is_valid() -> None:
    frame = PoseFrame(
        index=0,
        source_frame_index=0,
        timestamp_s=0.0,
        detected=True,
        landmarks=full_landmark_set(),
    )
    assert frame.detected is True
    assert frame.landmarks is not None


def test_pose_frame_rejects_detected_without_landmarks() -> None:
    with pytest.raises(ValidationError):
        PoseFrame(
            index=0, source_frame_index=0, timestamp_s=0.0, detected=True, landmarks=None
        )


def test_pose_frame_rejects_landmarks_without_detected() -> None:
    with pytest.raises(ValidationError):
        PoseFrame(
            index=0,
            source_frame_index=0,
            timestamp_s=0.0,
            detected=False,
            landmarks=full_landmark_set(),
        )


def test_series_round_trip_serialization() -> None:
    frame = PoseFrame(
        index=0,
        source_frame_index=0,
        timestamp_s=0.0,
        detected=True,
        landmarks=full_landmark_set(),
    )
    series = PoseSeries(
        fps=30.0,
        sampled_fps=30.0,
        frame_count=1,
        sampled_count=1,
        width=64,
        height=48,
        duration_s=1 / 30,
        frames=[frame],
    )
    restored = PoseSeries.model_validate_json(series.model_dump_json())
    assert restored == series
    assert restored.frames[0].landmarks is not None
    assert len(restored.frames[0].landmarks) == 33


def test_detected_frames_helper_filters() -> None:
    detected = PoseFrame(
        index=0,
        source_frame_index=0,
        timestamp_s=0.0,
        detected=True,
        landmarks=full_landmark_set(),
    )
    missing = PoseFrame(
        index=1, source_frame_index=2, timestamp_s=0.1, detected=False, landmarks=None
    )
    series = PoseSeries(
        fps=30.0,
        sampled_fps=15.0,
        frame_count=4,
        sampled_count=2,
        width=64,
        height=48,
        duration_s=4 / 30,
        frames=[detected, missing],
    )
    assert series.detected_frames == [detected]
