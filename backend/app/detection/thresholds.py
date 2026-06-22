"""Named thresholds and tuning constants for flaw detection (M6).

Every magnitude that decides *whether* and *how strongly* a flaw fires lives
here, each an isolated knob with a one-line rationale — mirroring
``app.validation.thresholds``. They are **first-pass** values chosen against the
geometry of the prescribed down-the-line view and the synthetic test fixtures;
the real-clip tuning is **deferred to M7** (golden fixtures). Keeping them named
and centralized is what lets M7 retune without touching rule code.

Score model (see ``geometry.ramp``): each rule produces a ``raw`` measure mapped
to ``[0, 1]`` by a per-flaw ``*_MIN`` (raw at score 0) / ``*_MAX`` (raw at score
1). A flaw is reported only when its score reaches its ``*_TRIGGER``.

Units: ``*_MIN`` / ``*_MAX`` are either **fractions of stature** (the nose→ankle
span — so they are zoom/body-size invariant) or **degrees**, as noted per flaw.
``*_TRIGGER`` is a score in ``[0, 1]``.
"""

from __future__ import annotations

# --- Shared engine knobs ----------------------------------------------------

# Minimum MediaPipe visibility for a landmark to be trusted in a measurement.
# Below this the point is treated as missing rather than fed noise into a rule.
MIN_LANDMARK_VISIBILITY = 0.5

# A swing needs at least this many detected frames to be analyzable at all. The
# M5 gate already guarantees ≥50% detection, so this is a defensive floor.
MIN_DETECTED_FRAMES = 6

# Fraction of the (detected) series treated as the "address" baseline window,
# from which every rule measures change. ~15% ≈ the settled setup before motion.
ADDRESS_FRACTION = 0.15

# Fraction of the downswing (top → impact) treated as "early downswing", where
# the over-the-top move reveals itself before the hands recover into the slot.
EARLY_DOWNSWING_FRACTION = 0.4

# Hard cap on reported flaws — the PRD's "top 2–3". We never pad below it, but
# also never exceed it; only the highest-scoring flaws surface.
MAX_REPORTED_FLAWS = 3

# Default score a flaw must reach to be reported. Per-flaw triggers below may
# override this; centralizing the default documents the common case.
DEFAULT_TRIGGER = 0.5

# --- Early Extension (fraction of stature; hips thrust toward the ball) ------
# Peak toward-ball drift of the hip midpoint during the downswing, vs address.
EARLY_EXTENSION_MIN = 0.04  # below ~4% of stature is normal pelvic movement
EARLY_EXTENSION_MAX = 0.15  # ~15% is a pronounced thrust into the ball line
EARLY_EXTENSION_TRIGGER = DEFAULT_TRIGGER

# --- Loss of Posture (degrees; trunk straightens out of the shot) -----------
# Drop in trunk forward-tilt from address to the most-upright downswing frame.
LOSS_OF_POSTURE_MIN = 8.0  # a few degrees of straightening is unremarkable
LOSS_OF_POSTURE_MAX = 30.0  # standing fully out of posture by impact
LOSS_OF_POSTURE_TRIGGER = DEFAULT_TRIGGER

# --- Head Sway (fraction of stature; head leaves its start position) --------
# Peak displacement of the nose from its address position across the swing.
HEAD_SWAY_MIN = 0.05  # small head motion is normal and unavoidable
HEAD_SWAY_MAX = 0.20  # ~20% of stature is a clear, low-point-wrecking drift
HEAD_SWAY_TRIGGER = DEFAULT_TRIGGER

# --- Loss of Knee Flex (degrees; lead/trail knee straightens early) ---------
# Largest increase (either leg) in knee-flex angle from address to downswing.
KNEE_EXTENSION_MIN = 10.0  # knees naturally extend a little into impact
KNEE_EXTENSION_MAX = 35.0  # snapping the leg straight, losing the foundation
KNEE_EXTENSION_TRIGGER = DEFAULT_TRIGGER

# --- Over the Top (fraction of stature; hands jut outside the plane) --------
# How far past the address hand-to-shoulder offset the hands travel toward the
# ball in early downswing. NOTE: a *club-free body proxy* (no shaft landmark),
# so it is intentionally the noisiest rule — flagged for real-clip tuning in M7.
OVER_THE_TOP_MIN = 0.05
OVER_THE_TOP_MAX = 0.18
OVER_THE_TOP_TRIGGER = DEFAULT_TRIGGER
