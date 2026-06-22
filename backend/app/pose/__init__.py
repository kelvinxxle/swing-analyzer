"""Internal pose-extraction pipeline (M4).

Turns a swing video into a typed per-frame body-landmark series — the shared
input for input validation (M5) and flaw detection (M6).

This package is **internal**: it is not wired into the ``/analyze`` endpoint in
M4 (that endpoint keeps returning mock results until M6).
"""

from __future__ import annotations

from app.pose.config import DEFAULT_SAMPLING, SamplingConfig
from app.pose.estimator import MediaPipePoseEstimator, PoseEstimator
from app.pose.pipeline import VideoDecodeError, extract_pose_series
from app.pose.schema import (
    LANDMARK_ORDER,
    Landmark,
    LandmarkName,
    PoseFrame,
    PoseSeries,
)

__all__ = [
    "DEFAULT_SAMPLING",
    "LANDMARK_ORDER",
    "Landmark",
    "LandmarkName",
    "MediaPipePoseEstimator",
    "PoseEstimator",
    "PoseFrame",
    "PoseSeries",
    "SamplingConfig",
    "VideoDecodeError",
    "extract_pose_series",
]
