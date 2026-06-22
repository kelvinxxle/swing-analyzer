"""Unit tests for the pure frame-sampling logic (no OpenCV/MediaPipe)."""

from __future__ import annotations

import pytest

from app.pose.config import SamplingConfig
from app.pose.sampling import (
    compute_stride,
    effective_fps,
    sample_indices,
)


def test_stride_one_when_source_at_or_below_target() -> None:
    config = SamplingConfig(target_fps=30, max_frames=1000)
    assert compute_stride(30.0, 100, config) == 1
    assert compute_stride(24.0, 100, config) == 1


def test_stride_downsamples_high_fps() -> None:
    config = SamplingConfig(target_fps=30, max_frames=1000)
    # 60 fps → take every 2nd frame to approximate 30 fps.
    assert compute_stride(60.0, 300, config) == 2
    assert compute_stride(120.0, 600, config) == 4


def test_stride_rounds_half_up() -> None:
    config = SamplingConfig(target_fps=30, max_frames=1000)
    # 75 / 30 = 2.5 → round half up to stride 3 (~25fps, closer to 30 than 37.5).
    assert compute_stride(75.0, 300, config) == 3


def test_stride_widens_to_respect_max_frames() -> None:
    config = SamplingConfig(target_fps=30, max_frames=50)
    # 30 fps, 300 frames → target stride 1 would give 300 > 50, so widen.
    stride = compute_stride(30.0, 300, config)
    assert stride >= 6
    sampled = len(sample_indices(30.0, 300, config))
    assert sampled <= config.max_frames


def test_sample_indices_are_strided_and_ordered() -> None:
    config = SamplingConfig(target_fps=30, max_frames=1000)
    indices = sample_indices(60.0, 10, config)
    assert indices == [0, 2, 4, 6, 8]
    assert indices == sorted(indices)


def test_sample_indices_empty_for_no_frames() -> None:
    config = SamplingConfig()
    assert sample_indices(30.0, 0, config) == []


def test_single_frame_clip() -> None:
    config = SamplingConfig(target_fps=30, max_frames=150)
    assert compute_stride(30.0, 1, config) == 1
    assert sample_indices(30.0, 1, config) == [0]


def test_effective_fps_reflects_stride() -> None:
    assert effective_fps(60.0, 2) == 30.0
    assert effective_fps(30.0, 1) == 30.0


def test_invalid_inputs_raise() -> None:
    config = SamplingConfig()
    with pytest.raises(ValueError):
        compute_stride(0.0, 10, config)
    with pytest.raises(ValueError):
        compute_stride(30.0, -1, config)
    with pytest.raises(ValueError):
        effective_fps(30.0, 0)
