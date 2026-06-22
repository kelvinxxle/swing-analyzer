"""Shared test helpers for the pose pipeline: synthetic clip generation + fakes.

We deliberately generate tiny synthetic clips at test time rather than committing
binary video fixtures. This keeps the repo lightweight, the tests hermetic (no
network, no large assets), and avoids any third-party footage licensing. Real
swing clips for true landmark-detection assertions arrive with the golden
fixtures in M7.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.pose.schema import LANDMARK_ORDER, Landmark, LandmarkName


def make_synthetic_clip(
    path: Path,
    *,
    frames: int,
    fps: float,
    width: int = 64,
    height: int = 48,
) -> Path:
    """Write a short synthetic MP4 with a moving rectangle and return its path.

    The content is meaningless to pose estimation (no real human) — it exists to
    exercise the decode → sample → structure path deterministically.
    """
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not open VideoWriter for synthetic clip")
    try:
        for i in range(frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            x = (i * 3) % max(width - 10, 1)
            cv2.rectangle(frame, (x, 10), (x + 8, 30), (255, 255, 255), -1)
            writer.write(frame)
    finally:
        writer.release()
    return path


def full_landmark_set(visibility: float = 0.9) -> dict[LandmarkName, Landmark]:
    """A complete, deterministic set of all 33 landmarks for fake estimators."""
    return {
        name: Landmark(x=0.5, y=0.5, z=0.0, visibility=visibility)
        for name in LANDMARK_ORDER
    }


class FakePoseEstimator:
    """A deterministic :class:`PoseEstimator` returning a fixed landmark set.

    Records how many frames it was asked about and whether it was closed, so the
    pipeline's per-frame invocation and resource handling can be asserted.
    """

    def __init__(self, *, detect: bool = True) -> None:
        self._detect = detect
        self.calls = 0
        self.closed = False

    def estimate(self, frame_rgb: np.ndarray) -> dict[LandmarkName, Landmark] | None:
        self.calls += 1
        return full_landmark_set() if self._detect else None

    def close(self) -> None:
        self.closed = True
