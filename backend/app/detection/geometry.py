"""Pure 2D geometry helpers for flaw detection (M6).

These operate only on the M4 :class:`~app.pose.schema.PoseFrame` /
:class:`~app.pose.schema.Landmark` contract and plain ``(x, y)`` points. They
contain **no** MediaPipe, OpenCV, or rule logic — just the small kit of
measurements the rules compose (midpoints, angles, distances, a stature scale).

Coordinate reminder (matching MediaPipe Pose): ``x`` / ``y`` are normalized to
``[0, 1]``; ``y`` grows **downward**, so a smaller ``y`` is higher in the frame.
``z`` is an unreliable depth hint and is deliberately never used here — every
measurement lives on the reliable ``x`` / ``y`` axes.
"""

from __future__ import annotations

from math import acos, atan2, degrees, hypot

from app.pose.schema import LandmarkName, PoseFrame

# A normalized 2D image point.
Point = tuple[float, float]


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into ``[low, high]``."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def ramp(raw: float, low: float, high: float) -> float:
    """Map ``raw`` onto ``[0, 1]`` by a piecewise-linear ramp between two knees.

    ``raw <= low`` → ``0`` (no flaw), ``raw >= high`` → ``1`` (saturated). This is
    the single normalization used to make every flaw's score comparable.
    """
    if high <= low:
        return 0.0
    return clamp((raw - low) / (high - low), 0.0, 1.0)


def landmark_point(
    frame: PoseFrame, name: LandmarkName, min_visibility: float
) -> Point | None:
    """Return a landmark's ``(x, y)`` if present and confident, else ``None``."""
    landmarks = frame.landmarks
    if landmarks is None:
        return None
    landmark = landmarks.get(name)
    if landmark is None or landmark.visibility < min_visibility:
        return None
    return (landmark.x, landmark.y)


def midpoint(a: Point, b: Point) -> Point:
    """Midpoint of two points."""
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def pair_midpoint(
    frame: PoseFrame,
    left: LandmarkName,
    right: LandmarkName,
    min_visibility: float,
) -> Point | None:
    """Midpoint of a left/right landmark pair, or ``None`` if either is missing.

    Averaging the two sides is what makes a body-center signal (hips, shoulders,
    hands) robust on the down-the-line view, where the near/far landmark of a pair
    can drift in depth.
    """
    a = landmark_point(frame, left, min_visibility)
    b = landmark_point(frame, right, min_visibility)
    if a is None or b is None:
        return None
    return midpoint(a, b)


def distance(a: Point, b: Point) -> float:
    """Euclidean distance between two points."""
    return hypot(a[0] - b[0], a[1] - b[1])


def forward_tilt_deg(top: Point, bottom: Point) -> float:
    """Tilt of the ``bottom → top`` segment away from vertical, in degrees.

    Used as the trunk-lean proxy (``bottom`` = mid-hip, ``top`` = mid-shoulder):
    ``0°`` is perfectly upright, larger means more forward bend. It is
    sign-agnostic (only the magnitude of the lean matters for posture).
    """
    dx = top[0] - bottom[0]
    dy = top[1] - bottom[1]
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return degrees(atan2(abs(dx), abs(dy)))


def joint_angle_deg(a: Point, b: Point, c: Point) -> float:
    """Interior angle at vertex ``b`` of the path ``a → b → c``, in degrees.

    For a leg (``a`` = hip, ``b`` = knee, ``c`` = ankle) this is the knee-flex
    angle: ``180°`` is a straight leg, smaller is more flexed.
    """
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = hypot(*v1)
    n2 = hypot(*v2)
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    cosine = clamp((v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2), -1.0, 1.0)
    return degrees(acos(cosine))


def stature_scale(frame: PoseFrame, min_visibility: float) -> float | None:
    """A body-size scale for one frame, used to normalize displacements.

    Primary: the vertical span from the nose to the mid-ankle — stable on the
    down-the-line view and independent of zoom / distance. Falls back to ~2.5×
    the shoulder→hip distance (an anthropometric estimate of full height) when
    the head or feet are not confidently visible. ``None`` if neither is usable.
    """
    nose = landmark_point(frame, LandmarkName.NOSE, min_visibility)
    ankle = pair_midpoint(
        frame, LandmarkName.LEFT_ANKLE, LandmarkName.RIGHT_ANKLE, min_visibility
    )
    if nose is not None and ankle is not None:
        span = abs(nose[1] - ankle[1])
        if span > 1e-6:
            return span

    shoulder = pair_midpoint(
        frame, LandmarkName.LEFT_SHOULDER, LandmarkName.RIGHT_SHOULDER, min_visibility
    )
    hip = pair_midpoint(
        frame, LandmarkName.LEFT_HIP, LandmarkName.RIGHT_HIP, min_visibility
    )
    if shoulder is not None and hip is not None:
        torso = distance(shoulder, hip)
        if torso > 1e-6:
            return torso * 2.5
    return None
