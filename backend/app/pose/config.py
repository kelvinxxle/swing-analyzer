"""Configuration for frame sampling in the pose-extraction pipeline."""

from __future__ import annotations

import math
import os

from pydantic import BaseModel, Field


def _default_pose_model_complexity() -> int:
    """Resolve the MediaPipe pose ``model_complexity`` from the environment.

    Production runs the *lite* model (``0``) on the Render free tier to stay
    within the analysis budget; local/CI default to the *accurate* model (``1``).
    Any unset, non-integer, or out-of-range value falls back to ``1``.
    """
    raw = os.getenv("POSE_MODEL_COMPLEXITY")
    if raw is None:
        return 1
    try:
        value = int(raw)
    except ValueError:
        return 1
    if value < 0 or value > 2:
        return 1
    return value


def _default_target_fps() -> float:
    """Resolve the frame-sampling ``target_fps`` from the environment.

    Production trims the sampled frame rate via ``POSE_TARGET_FPS`` to fit the
    Render free-tier analysis budget; local/CI default to ``30.0``. Any unset,
    non-float, non-finite, or non-positive value falls back to ``30.0``.
    """
    raw = os.getenv("POSE_TARGET_FPS")
    if raw is None:
        return 30.0
    try:
        value = float(raw)
    except ValueError:
        return 30.0
    if not math.isfinite(value) or value <= 0:
        return 30.0
    return value


def _default_max_frames() -> int:
    """Resolve the frame-sampling ``max_frames`` cap from the environment.

    Production trims the sampled frame count via ``POSE_MAX_FRAMES`` to fit the
    Render free-tier analysis budget; local/CI default to ``150``. Any unset,
    non-integer, or non-positive value falls back to ``150``.
    """
    raw = os.getenv("POSE_MAX_FRAMES")
    if raw is None:
        return 150
    try:
        value = int(raw)
    except ValueError:
        return 150
    if value <= 0:
        return 150
    return value


class SamplingConfig(BaseModel):
    """How densely to sample frames from the source video.

    A golf swing is short but fast, so we do not need to run pose estimation on
    every frame of a 60 fps clip — that would be slow on the Render free tier
    with little benefit. Instead we sample at a fixed target frame rate and cap
    the total number of frames, which keeps latency bounded and predictable.
    """

    target_fps: float = Field(
        default_factory=_default_target_fps,
        gt=0.0,
        description="Desired effective frame rate to sample at. Clips at or below "
        "this rate are processed frame-for-frame. Env-overridable via "
        "POSE_TARGET_FPS so prod can trim frame count for free-tier latency.",
    )
    max_frames: int = Field(
        default_factory=_default_max_frames,
        gt=0,
        description="Hard cap on sampled frames; the stride is widened if a long "
        "or high-fps clip would otherwise exceed it. Env-overridable via "
        "POSE_MAX_FRAMES so prod can fit the 60s free-tier analysis budget.",
    )
    max_inference_frame_dimension: int = Field(
        default=480,
        gt=0,
        description="Longer-edge pixel cap applied to each frame before pose "
        "inference. Frames larger than this are downscaled (never upscaled) with "
        "INTER_AREA; landmarks are normalized [0,1] so this is nearly lossless but "
        "much cheaper on the Render free tier.",
    )
    pose_model_complexity: int = Field(
        default_factory=_default_pose_model_complexity,
        ge=0,
        le=2,
        description="MediaPipe pose model complexity (0=lite, 1=full, 2=heavy). "
        "Env-driven via POSE_MODEL_COMPLEXITY: prod uses 0 for speed, local/CI 1.",
    )


DEFAULT_SAMPLING = SamplingConfig()
