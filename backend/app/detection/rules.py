"""The geometric flaw rules (M6) — one score per catalog flaw.

Each rule reads the M4 :class:`~app.pose.schema.PoseSeries` (via a precomputed
:class:`SwingContext`) and returns a :class:`FlawScore`: a ``raw`` geometric
measure, its normalized ``[0, 1]`` ``score`` (``geometry.ramp`` over per-flaw
thresholds), and whether it cleared its trigger. The engine ranks these.

Why **these five**, and the down-the-line (DTL) inclusion test
--------------------------------------------------------------
On the prescribed DTL view the image axes map to swing directions as: ``x`` =
toward / away from the ball (reliable), ``y`` = vertical (reliable), ``z`` =
along the target line (an unreliable depth hint). A flaw is in the catalog only
if it is visible on the reliable ``x`` / ``y`` axes:

* **Early Extension** — hips drift toward the ball (``x``).
* **Loss of Posture** — trunk straightens (``x`` / ``y`` angle).
* **Head Sway** — the head leaves its start position (``x`` / ``y``).
* **Loss of Knee Flex** — a knee straightens early (joint angle).
* **Over the Top** — the hands jut outside the plane line (``x``) — a *club-free
  body proxy*, the noisiest rule, flagged for M7 tuning.

Deliberately **excluded**: lateral sway / slide and reverse-spine "hang back"
travel along the target line (``z``) and so are not reliably measurable from DTL;
casting / early release needs the club shaft, which is not a body landmark.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.detection import geometry
from app.detection import thresholds as T
from app.detection.catalog import FlawId
from app.detection.geometry import Point
from app.detection.phases import SwingPhases, detect_phases
from app.pose.schema import LandmarkName, PoseFrame, PoseSeries

_VIS = T.MIN_LANDMARK_VISIBILITY


@dataclass(frozen=True)
class FlawScore:
    """One rule's verdict for a swing."""

    id: FlawId
    raw: float
    score: float
    triggered: bool


@dataclass(frozen=True)
class SwingContext:
    """Everything the rules need, computed once per swing.

    ``ball_dir`` is ``+1`` / ``-1`` so that ``ball_dir * (point.x - reference.x)``
    is positive when a point moves **toward the ball**, regardless of which way
    the golfer faces in the frame. ``scale`` is the address stature used to make
    displacement measures zoom-invariant.
    """

    phases: SwingPhases
    address_frames: list[PoseFrame]
    downswing_frames: list[PoseFrame]
    all_frames: list[PoseFrame]
    scale: float
    ball_dir: float


# --- Landmark getters (per-frame body-center points) ------------------------


def _hip_mid(frame: PoseFrame) -> Point | None:
    return geometry.pair_midpoint(frame, LandmarkName.LEFT_HIP, LandmarkName.RIGHT_HIP, _VIS)


def _shoulder_mid(frame: PoseFrame) -> Point | None:
    return geometry.pair_midpoint(
        frame, LandmarkName.LEFT_SHOULDER, LandmarkName.RIGHT_SHOULDER, _VIS
    )


def _wrist_mid(frame: PoseFrame) -> Point | None:
    return geometry.pair_midpoint(frame, LandmarkName.LEFT_WRIST, LandmarkName.RIGHT_WRIST, _VIS)


def _ankle_mid(frame: PoseFrame) -> Point | None:
    return geometry.pair_midpoint(frame, LandmarkName.LEFT_ANKLE, LandmarkName.RIGHT_ANKLE, _VIS)


def _nose(frame: PoseFrame) -> Point | None:
    return geometry.landmark_point(frame, LandmarkName.NOSE, _VIS)


def _mean_point(
    frames: list[PoseFrame], getter: Callable[[PoseFrame], Point | None]
) -> Point | None:
    points = [p for frame in frames if (p := getter(frame)) is not None]
    if not points:
        return None
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)


# --- Context construction ---------------------------------------------------


def build_context(series: PoseSeries) -> SwingContext | None:
    """Assemble the shared :class:`SwingContext`, or ``None`` if not analyzable."""
    detected = series.detected_frames
    phases = detect_phases(detected)
    if phases is None:
        return None

    address_frames = detected[phases.address_start : phases.address_end]
    downswing_frames = detected[phases.top : phases.impact + 1]
    if not address_frames or not downswing_frames:
        return None

    scale: float | None = None
    for frame in address_frames:
        scale = geometry.stature_scale(frame, _VIS)
        if scale is not None:
            break
    if scale is None or scale <= 1e-6:
        return None

    ball_dir = _ball_direction(address_frames)

    return SwingContext(
        phases=phases,
        address_frames=address_frames,
        downswing_frames=downswing_frames,
        all_frames=detected,
        scale=scale,
        ball_dir=ball_dir,
    )


def _ball_direction(address_frames: list[PoseFrame]) -> float:
    """Sign of the toward-ball ``x`` axis, from the address trunk lean.

    At address the golfer is bent toward the ball, so the shoulders sit on the
    ball side of the hips. The sign of that offset tells us which ``x`` direction
    is "toward the ball". Defaults to ``+1`` if it cannot be measured.
    """
    shoulder = _mean_point(address_frames, _shoulder_mid)
    hip = _mean_point(address_frames, _hip_mid)
    if shoulder is None or hip is None:
        return 1.0
    return 1.0 if shoulder[0] - hip[0] >= 0.0 else -1.0


def _score(flaw: FlawId, raw: float, low: float, high: float, trigger: float) -> FlawScore:
    score = geometry.ramp(raw, low, high)
    return FlawScore(id=flaw, raw=raw, score=score, triggered=score >= trigger)


# --- The five rules ---------------------------------------------------------


def score_early_extension(ctx: SwingContext) -> FlawScore:
    """Hips thrust toward the ball through the downswing.

    Measured as the hips' horizontal position **relative to the ankles** (the
    planted feet), so a whole-body shift isn't mistaken for the pelvis driving in
    toward the ball. Raw = peak toward-ball growth of that hip→ankle offset vs
    address, in fractions of stature.
    """
    address_hip = _mean_point(ctx.address_frames, _hip_mid)
    address_ankle = _mean_point(ctx.address_frames, _ankle_mid)
    raw = 0.0
    if address_hip is not None and address_ankle is not None:
        baseline = address_hip[0] - address_ankle[0]
        drifts = [
            ctx.ball_dir * ((hip[0] - ankle[0]) - baseline) / ctx.scale
            for frame in ctx.downswing_frames
            if (hip := _hip_mid(frame)) is not None and (ankle := _ankle_mid(frame)) is not None
        ]
        if drifts:
            raw = max(0.0, max(drifts))
    return _score(
        FlawId.EARLY_EXTENSION,
        raw,
        T.EARLY_EXTENSION_MIN,
        T.EARLY_EXTENSION_MAX,
        T.EARLY_EXTENSION_TRIGGER,
    )


def score_loss_of_posture(ctx: SwingContext) -> FlawScore:
    """Trunk straightens: drop in forward tilt from address to the most-upright frame."""
    address_shoulder = _mean_point(ctx.address_frames, _shoulder_mid)
    address_hip = _mean_point(ctx.address_frames, _hip_mid)
    raw = 0.0
    if address_shoulder is not None and address_hip is not None:
        address_tilt = geometry.forward_tilt_deg(address_shoulder, address_hip)
        tilts = [
            geometry.forward_tilt_deg(shoulder, hip)
            for frame in ctx.downswing_frames
            if (shoulder := _shoulder_mid(frame)) is not None
            and (hip := _hip_mid(frame)) is not None
        ]
        if tilts:
            raw = max(0.0, address_tilt - min(tilts))
    return _score(
        FlawId.LOSS_OF_POSTURE,
        raw,
        T.LOSS_OF_POSTURE_MIN,
        T.LOSS_OF_POSTURE_MAX,
        T.LOSS_OF_POSTURE_TRIGGER,
    )


def score_head_sway(ctx: SwingContext) -> FlawScore:
    """Head leaves its start position: peak nose displacement over the whole swing."""
    address_nose = _mean_point(ctx.address_frames, _nose)
    raw = 0.0
    if address_nose is not None:
        displacements = [
            geometry.distance(nose, address_nose) / ctx.scale
            for frame in ctx.all_frames
            if (nose := _nose(frame)) is not None
        ]
        if displacements:
            raw = max(displacements)
    return _score(
        FlawId.HEAD_SWAY,
        raw,
        T.HEAD_SWAY_MIN,
        T.HEAD_SWAY_MAX,
        T.HEAD_SWAY_TRIGGER,
    )


def score_loss_of_knee_flex(ctx: SwingContext) -> FlawScore:
    """A knee straightens early: largest address→downswing increase in knee angle."""
    legs = (
        (LandmarkName.LEFT_HIP, LandmarkName.LEFT_KNEE, LandmarkName.LEFT_ANKLE),
        (LandmarkName.RIGHT_HIP, LandmarkName.RIGHT_KNEE, LandmarkName.RIGHT_ANKLE),
    )
    raw = 0.0
    for hip_name, knee_name, ankle_name in legs:
        address_angle = _mean_knee_angle(ctx.address_frames, hip_name, knee_name, ankle_name)
        if address_angle is None:
            continue
        downswing_angles = [
            angle
            for frame in ctx.downswing_frames
            if (angle := _knee_angle(frame, hip_name, knee_name, ankle_name)) is not None
        ]
        if not downswing_angles:
            continue
        raw = max(raw, max(downswing_angles) - address_angle)
    raw = max(0.0, raw)
    return _score(
        FlawId.LOSS_OF_KNEE_FLEX,
        raw,
        T.KNEE_EXTENSION_MIN,
        T.KNEE_EXTENSION_MAX,
        T.KNEE_EXTENSION_TRIGGER,
    )


def score_over_the_top(ctx: SwingContext) -> FlawScore:
    """Hands jut toward the ball past the address plane line in early downswing."""
    address_shoulder = _mean_point(ctx.address_frames, _shoulder_mid)
    address_wrist = _mean_point(ctx.address_frames, _wrist_mid)
    raw = 0.0
    if address_shoulder is not None and address_wrist is not None:
        address_offset = ctx.ball_dir * (address_wrist[0] - address_shoulder[0]) / ctx.scale
        early = _early_downswing(ctx.downswing_frames)
        offsets = [
            ctx.ball_dir * (wrist[0] - shoulder[0]) / ctx.scale
            for frame in early
            if (wrist := _wrist_mid(frame)) is not None
            and (shoulder := _shoulder_mid(frame)) is not None
        ]
        if offsets:
            raw = max(0.0, max(offsets) - address_offset)
    return _score(
        FlawId.OVER_THE_TOP,
        raw,
        T.OVER_THE_TOP_MIN,
        T.OVER_THE_TOP_MAX,
        T.OVER_THE_TOP_TRIGGER,
    )


def _early_downswing(downswing_frames: list[PoseFrame]) -> list[PoseFrame]:
    count = max(1, round(len(downswing_frames) * T.EARLY_DOWNSWING_FRACTION))
    return downswing_frames[:count]


def _knee_angle(
    frame: PoseFrame, hip: LandmarkName, knee: LandmarkName, ankle: LandmarkName
) -> float | None:
    h = geometry.landmark_point(frame, hip, _VIS)
    k = geometry.landmark_point(frame, knee, _VIS)
    a = geometry.landmark_point(frame, ankle, _VIS)
    if h is None or k is None or a is None:
        return None
    return geometry.joint_angle_deg(h, k, a)


def _mean_knee_angle(
    frames: list[PoseFrame], hip: LandmarkName, knee: LandmarkName, ankle: LandmarkName
) -> float | None:
    angles = [a for frame in frames if (a := _knee_angle(frame, hip, knee, ankle)) is not None]
    if not angles:
        return None
    return sum(angles) / len(angles)


# Catalog order (also the deterministic tie-break order in the engine).
RULES: tuple[Callable[[SwingContext], FlawScore], ...] = (
    score_early_extension,
    score_loss_of_posture,
    score_head_sway,
    score_loss_of_knee_flex,
    score_over_the_top,
)


def score_all(ctx: SwingContext) -> list[FlawScore]:
    """Run every rule against the context, in catalog order."""
    return [rule(ctx) for rule in RULES]
