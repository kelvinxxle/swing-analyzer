"""The closed flaw catalog: identity + player-facing copy (M6).

This is the **single source** of the catalog's named flaws and their text — the
category/title/description and the one actionable fix tip per flaw. Detection
logic (the geometric rules) lives in ``app.detection.rules``; this module is just
the words, so the prose can be edited without touching any math.

Tone follows the design: specific, expert, and encouraging — a prioritized fix,
not a lecture. Each flaw is in the catalog because it is **visibly detectable
from the prescribed down-the-line angle** (see ``rules`` for the geometry and for
why sway / reverse-spine / casting are deliberately excluded).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class FlawId(str, Enum):
    """Stable identifiers for the five catalog flaws (wire-safe string values)."""

    EARLY_EXTENSION = "early_extension"
    LOSS_OF_POSTURE = "loss_of_posture"
    HEAD_SWAY = "head_sway"
    LOSS_OF_KNEE_FLEX = "loss_of_knee_flex"
    OVER_THE_TOP = "over_the_top"


class FlawCopy(BaseModel):
    """Immutable player-facing copy for one catalog flaw."""

    id: FlawId
    category: str
    title: str
    description: str
    fix: str


# Ordered by catalog precedence (also the deterministic tie-break order when two
# flaws score equally). The ranking by score is what actually orders the output.
FLAW_CATALOG: tuple[FlawCopy, ...] = (
    FlawCopy(
        id=FlawId.EARLY_EXTENSION,
        category="Posture Loss",
        title="Early Extension",
        description=(
            "Your hips push toward the ball during the downswing, forcing you to "
            "stand up out of your posture. This crowds your arms and is a common "
            "source of inconsistent strikes and lost power."
        ),
        fix=(
            "Feel your glutes stay back against an imaginary wall as you start down. "
            "Let your lead hip clear behind you instead of thrusting in toward the "
            "ball — your trail pocket should rotate, not move closer to the ball."
        ),
    ),
    FlawCopy(
        id=FlawId.LOSS_OF_POSTURE,
        category="Posture Loss",
        title="Loss of Posture",
        description=(
            "Your spine angle straightens up through the swing, so your chest rises "
            "and you lose the forward tilt you set at address. That moving low point "
            "makes flush contact a timing gamble."
        ),
        fix=(
            "Keep the angle in your spine from address all the way to impact. A good "
            "feel is to keep your chest pointing down at the ball a beat longer as "
            "you rotate through, rather than lifting up to meet it."
        ),
    ),
    FlawCopy(
        id=FlawId.HEAD_SWAY,
        category="Stability",
        title="Head Sway",
        description=(
            "Your head drifts noticeably from where it started during the swing. "
            "Because your head anchors the arc of your swing, that movement shifts "
            "the bottom of your arc and costs you centered, repeatable contact."
        ),
        fix=(
            "Pick a spot on the ground and keep your head quiet over it through the "
            "backswing and into impact. Turn around a stable head — let your body "
            "rotate while your head stays put, then release up into the finish."
        ),
    ),
    FlawCopy(
        id=FlawId.LOSS_OF_KNEE_FLEX,
        category="Lower Body",
        title="Loss of Knee Flex",
        description=(
            "Your knees straighten early in the downswing, so you lose the athletic "
            "flex you started with. That stands you up and pulls the club off its "
            "path, leaking the power your legs should be adding."
        ),
        fix=(
            "Hold the flex you set at address as you transition down — feel your "
            "knees stay 'loaded' and quiet until well after impact. Think squat-and-"
            "rotate, not stand-and-lift, as you deliver the club."
        ),
    ),
    FlawCopy(
        id=FlawId.OVER_THE_TOP,
        category="Path",
        title="Over the Top",
        description=(
            "From the top, your hands move out toward the ball before they drop, "
            "throwing the club onto an out-to-in path. That outside-in delivery is "
            "the classic cause of pulls and the weak slice."
        ),
        fix=(
            "Start the downswing from the ground up and let your hands drop straight "
            "down into the slot before you rotate hard. Feel the club fall behind "
            "you, then swing out toward the ball — not over the top of it."
        ),
    ),
)

# Fast lookup by id; kept in sync with FLAW_CATALOG above.
FLAW_COPY_BY_ID: dict[FlawId, FlawCopy] = {copy.id: copy for copy in FLAW_CATALOG}

# Catalog precedence index, used as the deterministic tie-break when scores match.
CATALOG_ORDER: dict[FlawId, int] = {copy.id: i for i, copy in enumerate(FLAW_CATALOG)}
