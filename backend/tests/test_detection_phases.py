"""Swing-phase segmentation tests (M6).

Exercises ``detect_phases`` on the synthetic down-the-line swing: address / top /
impact land where the hand-height timeline says they should, and a too-short
series returns ``None``.
"""

from __future__ import annotations

import detection_helpers as H

from app.detection.phases import detect_phases
from app.detection.thresholds import MIN_DETECTED_FRAMES
from app.pose.schema import LandmarkName


def _mean_wrist_y(frame: object) -> float:
    landmarks = frame.landmarks  # type: ignore[attr-defined]
    left = landmarks[LandmarkName.LEFT_WRIST]
    right = landmarks[LandmarkName.RIGHT_WRIST]
    return (left.y + right.y) / 2.0


def test_detect_phases_finds_ordered_events() -> None:
    series = H.make_swing()
    phases = detect_phases(series.detected_frames)

    assert phases is not None
    assert phases.address_start == 0
    assert 1 <= phases.address_end < phases.top
    assert phases.top < phases.impact < series.sampled_count


def test_top_is_the_highest_hands_frame() -> None:
    series = H.make_swing()
    frames = series.detected_frames
    phases = detect_phases(frames)
    assert phases is not None

    # The top of the backswing is where the hands are highest (smallest y).
    highest = min(range(len(frames)), key=lambda i: _mean_wrist_y(frames[i]))
    assert phases.top == highest


def test_impact_returns_to_address_height() -> None:
    series = H.make_swing()
    frames = series.detected_frames
    phases = detect_phases(frames)
    assert phases is not None

    n_addr = phases.address_end
    address_y = sum(_mean_wrist_y(frames[i]) for i in range(n_addr)) / n_addr
    # Hands at impact are far nearer address height than they were at the top.
    assert abs(_mean_wrist_y(frames[phases.impact]) - address_y) < abs(
        _mean_wrist_y(frames[phases.top]) - address_y
    )


def test_too_short_series_has_no_phases() -> None:
    series = H.make_swing(n=MIN_DETECTED_FRAMES - 1)
    assert detect_phases(series.detected_frames) is None
