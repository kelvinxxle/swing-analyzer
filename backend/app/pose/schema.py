"""Typed contract for the per-frame pose-landmark series (M4).

This module defines the **stable data contract** produced by the pose-extraction
pipeline and consumed downstream by input validation (M5) and flaw detection
(M6). It deliberately contains no computer-vision logic — only the shape of the
data — so the contract can be imported and reasoned about without pulling in
MediaPipe or OpenCV.

Coordinate conventions (matching MediaPipe Pose):

* ``x`` / ``y`` are **normalized to the image size**, in ``[0.0, 1.0]`` — ``x``
  grows left→right, ``y`` grows top→bottom. Multiply by ``width`` / ``height``
  for pixel coordinates.
* ``z`` is an approximate depth relative to the hips' midpoint, in the same
  scale as ``x`` (smaller = closer to the camera). It is less reliable than
  ``x`` / ``y`` and should be treated as a rough hint.
* ``visibility`` is MediaPipe's ``[0.0, 1.0]`` confidence that the landmark is
  present and not occluded.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class LandmarkName(str, Enum):
    """The 33 MediaPipe Pose landmarks, exposed as named members.

    Downstream rules should reference landmarks by name (e.g.
    ``LandmarkName.LEFT_HIP``) rather than by raw index, so the contract stays
    readable and decoupled from MediaPipe's ordering.
    """

    NOSE = "nose"
    LEFT_EYE_INNER = "left_eye_inner"
    LEFT_EYE = "left_eye"
    LEFT_EYE_OUTER = "left_eye_outer"
    RIGHT_EYE_INNER = "right_eye_inner"
    RIGHT_EYE = "right_eye"
    RIGHT_EYE_OUTER = "right_eye_outer"
    LEFT_EAR = "left_ear"
    RIGHT_EAR = "right_ear"
    MOUTH_LEFT = "mouth_left"
    MOUTH_RIGHT = "mouth_right"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_ELBOW = "left_elbow"
    RIGHT_ELBOW = "right_elbow"
    LEFT_WRIST = "left_wrist"
    RIGHT_WRIST = "right_wrist"
    LEFT_PINKY = "left_pinky"
    RIGHT_PINKY = "right_pinky"
    LEFT_INDEX = "left_index"
    RIGHT_INDEX = "right_index"
    LEFT_THUMB = "left_thumb"
    RIGHT_THUMB = "right_thumb"
    LEFT_HIP = "left_hip"
    RIGHT_HIP = "right_hip"
    LEFT_KNEE = "left_knee"
    RIGHT_KNEE = "right_knee"
    LEFT_ANKLE = "left_ankle"
    RIGHT_ANKLE = "right_ankle"
    LEFT_HEEL = "left_heel"
    RIGHT_HEEL = "right_heel"
    LEFT_FOOT_INDEX = "left_foot_index"
    RIGHT_FOOT_INDEX = "right_foot_index"


# MediaPipe emits landmarks as a flat list; this fixes the index→name mapping so
# the estimator can build a named dict. Order matches MediaPipe Pose exactly.
LANDMARK_ORDER: tuple[LandmarkName, ...] = (
    LandmarkName.NOSE,
    LandmarkName.LEFT_EYE_INNER,
    LandmarkName.LEFT_EYE,
    LandmarkName.LEFT_EYE_OUTER,
    LandmarkName.RIGHT_EYE_INNER,
    LandmarkName.RIGHT_EYE,
    LandmarkName.RIGHT_EYE_OUTER,
    LandmarkName.LEFT_EAR,
    LandmarkName.RIGHT_EAR,
    LandmarkName.MOUTH_LEFT,
    LandmarkName.MOUTH_RIGHT,
    LandmarkName.LEFT_SHOULDER,
    LandmarkName.RIGHT_SHOULDER,
    LandmarkName.LEFT_ELBOW,
    LandmarkName.RIGHT_ELBOW,
    LandmarkName.LEFT_WRIST,
    LandmarkName.RIGHT_WRIST,
    LandmarkName.LEFT_PINKY,
    LandmarkName.RIGHT_PINKY,
    LandmarkName.LEFT_INDEX,
    LandmarkName.RIGHT_INDEX,
    LandmarkName.LEFT_THUMB,
    LandmarkName.RIGHT_THUMB,
    LandmarkName.LEFT_HIP,
    LandmarkName.RIGHT_HIP,
    LandmarkName.LEFT_KNEE,
    LandmarkName.RIGHT_KNEE,
    LandmarkName.LEFT_ANKLE,
    LandmarkName.RIGHT_ANKLE,
    LandmarkName.LEFT_HEEL,
    LandmarkName.RIGHT_HEEL,
    LandmarkName.LEFT_FOOT_INDEX,
    LandmarkName.RIGHT_FOOT_INDEX,
)


class Landmark(BaseModel):
    """A single body landmark in normalized image coordinates."""

    x: float
    y: float
    z: float
    visibility: float = Field(ge=0.0, le=1.0)


class PoseFrame(BaseModel):
    """Pose landmarks for one sampled frame of the video.

    ``landmarks`` is ``None`` when no pose was detected in the frame (e.g. the
    golfer is out of frame); ``detected`` mirrors that for convenient filtering.
    When present, it maps every :class:`LandmarkName` to its :class:`Landmark`.
    """

    index: int = Field(ge=0, description="Ordinal of this frame within the sampled series.")
    source_frame_index: int = Field(
        ge=0, description="Index of this frame within the original decoded video."
    )
    timestamp_s: float = Field(ge=0.0, description="Presentation time of the frame, in seconds.")
    detected: bool
    landmarks: dict[LandmarkName, Landmark] | None = None


class PoseSeries(BaseModel):
    """The full per-frame landmark series for one analyzed video.

    This is the shared input contract for M5 (validation) and M6 (detection).
    Frames are ordered by ``index`` and cover the video at the effective
    ``sampled_fps`` (see the sampling strategy in ``app.pose.sampling``).
    """

    fps: float = Field(gt=0.0, description="Frame rate of the source video.")
    sampled_fps: float = Field(gt=0.0, description="Effective frame rate after sampling.")
    frame_count: int = Field(ge=0, description="Total frames in the source video.")
    sampled_count: int = Field(ge=0, description="Number of frames in this series.")
    width: int = Field(gt=0, description="Source frame width in pixels.")
    height: int = Field(gt=0, description="Source frame height in pixels.")
    duration_s: float = Field(ge=0.0, description="Source video duration in seconds.")
    frames: list[PoseFrame] = Field(default_factory=list)

    @property
    def detected_frames(self) -> list[PoseFrame]:
        """Frames in which a pose was detected (convenience for downstream rules)."""
        return [frame for frame in self.frames if frame.detected]
