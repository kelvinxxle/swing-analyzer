"""Per-flaw rule tests (M6).

Each catalog rule is exercised in isolation against constructed landmark series:
a swing engineered to exhibit the flaw must score **high and trigger**, while the
clean baseline must score **low and not trigger**. This is the core correctness
safeguard for detection until the M7 golden fixtures land; thresholds themselves
are tuned against real clips in M7.
"""

from __future__ import annotations

import detection_helpers as H
import pytest

from app.detection.catalog import FlawId
from app.detection.rules import FlawScore, build_context, score_all
from app.pose.schema import PoseSeries

# (fixture flaw key, the FlawId its rule should report)
_CASES = [
    (H.EARLY_EXTENSION, FlawId.EARLY_EXTENSION),
    (H.LOSS_OF_POSTURE, FlawId.LOSS_OF_POSTURE),
    (H.HEAD_SWAY, FlawId.HEAD_SWAY),
    (H.LOSS_OF_KNEE_FLEX, FlawId.LOSS_OF_KNEE_FLEX),
    (H.OVER_THE_TOP, FlawId.OVER_THE_TOP),
]


def _score_for(series: PoseSeries, flaw_id: FlawId) -> FlawScore:
    context = build_context(series)
    assert context is not None
    by_id = {score.id: score for score in score_all(context)}
    return by_id[flaw_id]


@pytest.mark.parametrize(("flaw_key", "flaw_id"), _CASES)
def test_flawed_swing_triggers_its_rule(flaw_key: str, flaw_id: FlawId) -> None:
    score = _score_for(H.make_swing({flaw_key}), flaw_id)
    assert score.triggered
    assert score.score >= 0.8


@pytest.mark.parametrize(("flaw_key", "flaw_id"), _CASES)
def test_clean_swing_does_not_trigger_any_rule(flaw_key: str, flaw_id: FlawId) -> None:
    score = _score_for(H.make_swing(), flaw_id)
    assert not score.triggered
    assert score.score <= 0.2


def test_each_fixture_isolates_its_own_flaw() -> None:
    # A fixture for one flaw must not trip the other rules — keeps the per-rule
    # signal clean and prevents one synthetic perturbation from masking another.
    for flaw_key, flaw_id in _CASES:
        context = build_context(H.make_swing({flaw_key}))
        assert context is not None
        triggered = {score.id for score in score_all(context) if score.triggered}
        assert triggered == {flaw_id}


def test_clean_swing_triggers_nothing() -> None:
    context = build_context(H.make_swing())
    assert context is not None
    assert not any(score.triggered for score in score_all(context))
