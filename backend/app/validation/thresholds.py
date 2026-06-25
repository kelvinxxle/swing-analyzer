"""Named thresholds for input validation (M5).

Each constant is a deliberate, isolated knob with a one-line rationale. They are
first-pass values chosen from the prescribed down-the-line capture guidelines and
the limits of the M4 pose pipeline; they will be **tuned against real clips in
M7** (golden fixtures), so keeping them named and centralized matters more than
their exact magnitudes today.
"""

from __future__ import annotations

# --- Cheap pre-checks (decoded video, before the pose pass) -----------------

# Shorter side, in pixels. Below ~480p the landmark estimate degrades and visual
# flaw cues (M6) become unreliable, so we reject rather than analyze blind.
MIN_SHORTER_SIDE_PX = 480

# Seconds. A full swing (address → finish) cannot fit in less; a sub-second clip
# is a mis-capture, not a swing.
MIN_DURATION_S = 1.0

# How many frames to sample, evenly spaced, when measuring brightness. A handful
# is enough to judge exposure without decoding the whole clip.
BRIGHTNESS_SAMPLE_FRAMES = 5

# Mean luma on the 0–255 scale. Below this the frame is too dark for reliable
# pose detection and for a human to trust the diagnosis.
MIN_MEAN_LUMA = 40.0

# --- Pose-based checks (consume the M4 PoseSeries) --------------------------

# Fraction of sampled frames in which a pose must be found. Below this the clip
# does not contain a clear, trackable golfer.
MIN_DETECTED_FRAME_RATIO = 0.5

# Mean MediaPipe visibility of the core torso landmarks across detected frames.
# Low confidence means the "detection" is noise rather than a framed golfer.
MIN_MEAN_VISIBILITY = 0.5

# Max normalized horizontal shoulder span (|left.x − right.x|), averaged over
# detected frames. Down-the-line places the shoulders nearly in line with the
# camera, so they overlap in x (small span); a face-on / wide angle spreads them
# wide. Above this we treat the angle as "too wide" (not down-the-line).
MAX_SHOULDER_SPAN_X = 0.22

# How far outside the normalized [0, 1] frame a landmark may sit before it counts
# as out of frame (MediaPipe can predict slightly past the edge).
OUT_OF_FRAME_TOL = 0.02

# Max fraction of detected frames in which a key landmark may leave the frame
# before we reject for framing. Above this the golfer/club is clipped too often
# to analyze the whole swing.
MAX_OUT_OF_FRAME_RATIO = 0.3
