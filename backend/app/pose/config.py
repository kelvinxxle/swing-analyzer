"""Configuration for frame sampling in the pose-extraction pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SamplingConfig(BaseModel):
    """How densely to sample frames from the source video.

    A golf swing is short but fast, so we do not need to run pose estimation on
    every frame of a 60 fps clip — that would be slow on the Render free tier
    with little benefit. Instead we sample at a fixed target frame rate and cap
    the total number of frames, which keeps latency bounded and predictable.
    """

    target_fps: float = Field(
        default=30.0,
        gt=0.0,
        description="Desired effective frame rate to sample at. Clips at or below "
        "this rate are processed frame-for-frame.",
    )
    max_frames: int = Field(
        default=150,
        gt=0,
        description="Hard cap on sampled frames; the stride is widened if a long "
        "or high-fps clip would otherwise exceed it.",
    )


DEFAULT_SAMPLING = SamplingConfig()
