"""Frame-sampling strategy for the pose pipeline.

Pure, OpenCV-free logic so it can be unit-tested in isolation. Given a source
frame rate and frame count, it decides **which** frame indices to run pose
estimation on.

Strategy
--------
1. Pick an integer ``stride`` so the effective rate is about ``target_fps``:
   ``stride = round(source_fps / target_fps)``, clamped to at least ``1``. A clip
   already at or below the target is processed frame-for-frame.
2. If sampling at that stride would exceed ``max_frames``, widen the stride until
   the count fits. This bounds worst-case latency on long or high-fps clips.

Uniform sampling is the defensible v1 default: at ~30 fps a ~0.25 s downswing
still yields ~7–8 frames, enough to capture transition and impact for the
geometric rules in M6, without blindly processing every frame.
"""

from __future__ import annotations

import math

from app.pose.config import SamplingConfig


def compute_stride(source_fps: float, frame_count: int, config: SamplingConfig) -> int:
    """Return the frame stride (take every Nth frame) for the given clip.

    Always ``>= 1``. Widened beyond the target-fps stride if needed to respect
    ``config.max_frames``.
    """
    if source_fps <= 0:
        raise ValueError("source_fps must be positive")
    if frame_count < 0:
        raise ValueError("frame_count must be non-negative")

    # Round half up so ties pick the larger stride (closer to target_fps): e.g.
    # 75fps / 30fps target = 2.5 → stride 3 (~25fps), not banker's-rounded 2.
    stride = max(1, math.floor(source_fps / config.target_fps + 0.5))

    # Widen the stride until the resulting sample count fits the budget.
    if frame_count > 0:
        sampled = _count_for_stride(frame_count, stride)
        while sampled > config.max_frames:
            stride += 1
            sampled = _count_for_stride(frame_count, stride)

    return stride


def sample_indices(source_fps: float, frame_count: int, config: SamplingConfig) -> list[int]:
    """Return the ordered source-frame indices to sample for this clip."""
    if frame_count <= 0:
        return []
    stride = compute_stride(source_fps, frame_count, config)
    return list(range(0, frame_count, stride))


def effective_fps(source_fps: float, stride: int) -> float:
    """The sampled frame rate produced by a given stride."""
    if stride < 1:
        raise ValueError("stride must be >= 1")
    return source_fps / stride


def _count_for_stride(frame_count: int, stride: int) -> int:
    """How many frames ``range(0, frame_count, stride)`` yields."""
    return math.ceil(frame_count / stride)
