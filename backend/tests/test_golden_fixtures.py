"""The golden-fixture harness (M7): real clips → real pipeline → expected output.

This is the milestone's core de-risking investment. A JSON manifest
(``fixtures/golden/manifest.json``) maps each clip — a committed real clip or a
programmatically generated degenerate one — to its expected ``/analyze`` outcome,
expressed in the three result kinds the PRD cares about:

* a **good** swing → ``no_major_flaws``;
* a **per-flaw** clip → that flaw's category appears within the top-3 reported
  flaws (membership + a priority bound, *not* an exact score/order, so threshold
  tuning can't make the suite brittle);
* a **bad-input** clip → ``rejected`` with one specific reason ``code``.

The loader runs each clip through the **real** pipeline (``validate_video`` →
``detect_flaws`` — the same code ``/analyze`` runs) and asserts the expectation.

Partial fixture sets stay green: any entry whose ``file`` is not committed yet is
**skipped with a clear message**, so buckets can be filled incrementally (most
real footage is expected to arrive by the user recording it). Bad-input cases are
generated at test time, so they always run; ``angle`` / ``framing`` need a real
human and remain documented skips (covered by ``test_validation_checks.py``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pose_helpers import build_bad_input_clip

from app.analysis import AnalysisStatus
from app.detection import FLAW_CATALOG, detect_flaws
from app.validation import validate_video

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
MANIFEST_PATH = GOLDEN_DIR / "manifest.json"

# Reported flaws carry the player-facing title; map it back to the stable FlawId
# value the manifest references.
_TITLE_TO_FLAW_ID: dict[str, str] = {copy.title: copy.id.value for copy in FLAW_CATALOG}
_ALL_FLAW_IDS: frozenset[str] = frozenset(copy.id.value for copy in FLAW_CATALOG)


def _load_clips() -> list[dict[str, Any]]:
    data = json.loads(MANIFEST_PATH.read_text())
    return list(data["clips"])


CLIPS: list[dict[str, Any]] = _load_clips()


def _resolve_clip(clip: dict[str, Any], tmp_path: Path) -> Path:
    """Return the on-disk clip, generating it or skipping if not committed yet."""
    generator = clip.get("generator")
    if generator is not None:
        return build_bad_input_clip(generator["kind"], tmp_path)

    relative = clip["file"]
    path = GOLDEN_DIR / relative
    if not path.exists():
        pytest.skip(
            f"golden '{clip['id']}': clip '{relative}' not committed yet — add real "
            f"footage that clears the M5 capture gate (see fixtures/golden/README.md)."
        )
    return path


@pytest.mark.parametrize("clip", CLIPS, ids=[str(c["id"]) for c in CLIPS])
def test_golden_clip_matches_expected_output(clip: dict[str, Any], tmp_path: Path) -> None:
    path = _resolve_clip(clip, tmp_path)
    expect = clip["expect"]
    bucket = clip["bucket"]

    result, series = validate_video(path)

    if bucket == "bad_input":
        assert not result.passed, (
            f"{clip['id']}: expected rejection ({expect['reason_code']}), but the gate passed"
        )
        assert result.rejection is not None
        actual = result.rejection.details[0].code
        assert actual == expect["reason_code"], (
            f"{clip['id']}: expected reason '{expect['reason_code']}', got '{actual}'"
        )
        return

    # good / flaw buckets must clear the gate before detection runs.
    reason = None if result.rejection is None else result.rejection.details[0].code
    assert result.passed, f"{clip['id']}: expected the gate to pass, but it rejected '{reason}'"
    assert series is not None

    status, flaws = detect_flaws(series)

    if bucket == "good":
        assert status == AnalysisStatus.NO_MAJOR_FLAWS, (
            f"{clip['id']}: a good swing should report no major flaws, got '{status.value}' "
            f"with {[f.title for f in flaws]} — tune thresholds if a clean clip trips a rule"
        )
        return

    if bucket == "flaw":
        assert status == AnalysisStatus.ANALYZED, (
            f"{clip['id']}: expected analyzed flaws, got '{status.value}'"
        )
        reported = {_TITLE_TO_FLAW_ID[f.title]: f.priority for f in flaws}
        target = expect["flaw_in_top"]
        assert target in reported, (
            f"{clip['id']}: expected '{target}' among reported flaws {sorted(reported)}"
        )
        max_priority = expect.get("max_priority", 3)
        assert reported[target] <= max_priority, (
            f"{clip['id']}: '{target}' ranked {reported[target]}, "
            f"expected within top {max_priority}"
        )
        return

    pytest.fail(f"{clip['id']}: unknown bucket '{bucket}'")


def test_manifest_is_wellformed() -> None:
    """Guard the manifest itself so a typo can't silently weaken the suite."""
    assert CLIPS, "golden manifest has no clips"

    ids = [c["id"] for c in CLIPS]
    assert len(ids) == len(set(ids)), "duplicate clip ids in the manifest"

    buckets = {c["bucket"] for c in CLIPS}
    assert {"good", "flaw", "bad_input"} <= buckets, f"missing a core bucket: {buckets}"

    flaw_targets = set()
    for clip in CLIPS:
        assert "bucket" in clip and "expect" in clip, f"{clip.get('id')}: missing fields"
        assert ("file" in clip) ^ ("generator" in clip), (
            f"{clip['id']}: needs exactly one of 'file' or 'generator'"
        )
        bucket = clip["bucket"]
        expect = clip["expect"]
        if bucket == "good":
            assert expect["status"] == "no_major_flaws"
        elif bucket == "flaw":
            target = expect["flaw_in_top"]
            assert target in _ALL_FLAW_IDS, f"{clip['id']}: unknown flaw id '{target}'"
            flaw_targets.add(target)
        elif bucket == "bad_input":
            assert expect["status"] == "rejected"
            assert expect.get("reason_code"), f"{clip['id']}: bad_input needs a reason_code"

    # Every catalog flaw has at least one golden entry (filled or a documented skip).
    assert flaw_targets == _ALL_FLAW_IDS, (
        f"every catalog flaw needs a golden entry; missing {_ALL_FLAW_IDS - flaw_targets}"
    )


def test_golden_bad_input_rejection_over_the_wire(tmp_path: Path) -> None:
    """A generated bad-input clip is rejected through the real ``/analyze`` wire.

    The per-clip tests above call the pipeline directly for speed and precise
    assertions; this one drives one generated clip through the HTTP endpoint to
    prove the rejection still serializes into the ``{ status, flaws, reason }``
    contract the frontend parses.
    """
    import io

    from fastapi.testclient import TestClient

    from app.main import app

    clip = build_bad_input_clip("dark", tmp_path)
    with TestClient(app) as client:
        files = {"file": ("clip.mp4", io.BytesIO(clip.read_bytes()), "video/mp4")}
        response = client.post("/analyze", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["flaws"] == []
    assert body["reason"]["details"][0]["code"] == "lighting"

